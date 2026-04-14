from flask import Blueprint, jsonify, request
import os
from datetime import datetime

from repositories.erp_repository import ERPRepository
from repositories.local_alert_repository import LocalAlertRepository
from repositories.local_access_repository import LocalAccessRepository
from services.telegram_service import TelegramService
from config import Config
from utils.datetime_utils import erp_to_datetime, add_business_minutes, business_minutes_between

notify_bp = Blueprint('notify', __name__)

@notify_bp.route('/pending', methods=['POST'])
def notify_pending_first_attendance():
    try:
        tg_targets = [t.strip() for t in (os.getenv("TELEGRAM_CHAT_IDS", "") or "").split(",") if t.strip()]
        has_tg = bool(os.getenv("TELEGRAM_BOT_TOKEN")) and bool(tg_targets)
        if not has_tg:
            return jsonify({"error": "Configure TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_IDS"}), 400
        try:
            sla_minutes = int(request.args.get('sla_minutes', '30'))
        except Exception:
            sla_minutes = 30
        try:
            pre_minutes = int(request.args.get('pre_minutes', '10'))
        except Exception:
            pre_minutes = 10
        try:
            open_window_minutes = int(request.args.get('open_window_minutes', '2'))
        except Exception:
            open_window_minutes = 2
        dry_run = str(request.args.get('dry_run', '')).strip().lower() in {'1', 'true', 'yes'}
        ignore_sent = str(request.args.get('ignore_sent', '')).strip().lower() in {'1', 'true', 'yes'}

        erp = ERPRepository()
        alerts = LocalAlertRepository(Config.LOCAL_DB)
        tg = TelegramService()

        pendentes = erp.buscar_chamados_pendentes_base()
        sent_open = []
        sent_pre = []
        candidates_open = []
        candidates_pre = []

        for d in pendentes:
            cod = int(d['cod_solicitacao'])
            dt_open = erp_to_datetime(d.get('data_cad'), d.get('hora_cad'))
            if not dt_open:
                continue
            now = datetime.now()
            deadline = add_business_minutes(dt_open, sla_minutes)
            warn_at = add_business_minutes(dt_open, max(0, sla_minutes - pre_minutes))
            elapsed_bus = business_minutes_between(dt_open, now)
            remaining_bus = max(0, sla_minutes - elapsed_bus)
            diff_min = elapsed_bus
            remaining = remaining_bus
            real_diff_min = int((now - dt_open).total_seconds() // 60)
            should_open = real_diff_min >= 0 and real_diff_min <= open_window_minutes
            should_pre = (warn_at is not None) and (deadline is not None) and (now >= warn_at) and (now < deadline)
            already_open = (not ignore_sent) and alerts.was_sent(cod, "sla_open")
            already_pre = (not ignore_sent) and alerts.was_sent(cod, "sla_pre")
            if should_open and already_open:
                should_open = False
            if should_pre and already_pre:
                should_pre = False
            if not should_open and not should_pre:
                continue

            item = {
                "cod_solicitacao": cod,
                "minutos": diff_min,
                "faltam": remaining,
                "solicitante": d.get('solicitante', ''),
                "titulo": d.get('titulo_solicitacao', '')
            }
            if should_open:
                candidates_open.append(item)
            if should_pre:
                candidates_pre.append(item)
            if dry_run:
                continue
            data_iso = dt_open.strftime('%Y-%m-%d')
            hora_fmt = dt_open.strftime('%H:%M:%S')
            base_url = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
            link = f"{base_url}/chamados?id={cod}" if base_url else ""

            def send_msg(msg_text):
                ok = False
                for chat_id in tg_targets:
                    if tg.send(chat_id, msg_text):
                        ok = True
                return ok

            if should_open:
                msg = f"Novo chamado #{cod} aguardando 1º atendimento\nSLA: {sla_minutes} min (faltam {max(0, remaining)} min)\nSolicitante: {d.get('solicitante','')}\nTítulo: {d.get('titulo_solicitacao','')}\nAbertura: {data_iso} {hora_fmt}"
                if link:
                    msg = msg + f"\n{link}"
                if send_msg(msg):
                    alerts.mark_sent(cod, "sla_open")
                    sent_open.append(cod)

            if should_pre:
                msg = f"Alerta SLA: faltam {max(0, remaining)} min para o 1º atendimento\nChamado #{cod}\nSolicitante: {d.get('solicitante','')}\nTítulo: {d.get('titulo_solicitacao','')}\nAbertura: {data_iso} {hora_fmt}"
                if link:
                    msg = msg + f"\n{link}"
                if send_msg(msg):
                    alerts.mark_sent(cod, "sla_pre")
                    sent_pre.append(cod)

        if dry_run:
            return jsonify({
                "dry_run": True,
                "sla_minutes": sla_minutes,
                "pre_minutes": pre_minutes,
                "open_window_minutes": open_window_minutes,
                "candidates_open": candidates_open,
                "candidates_pre": candidates_pre
            })
        return jsonify({"sent_open": sent_open, "sent_pre": sent_pre})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@notify_bp.route('/opened', methods=['POST'])
def notify_opened_tickets():
    try:
        tg_targets = [t.strip() for t in (os.getenv("TELEGRAM_CHAT_IDS", "") or "").split(",") if t.strip()]
        has_tg = bool(os.getenv("TELEGRAM_BOT_TOKEN")) and bool(tg_targets)
        if not has_tg:
            return jsonify({"error": "Configure TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_IDS"}), 400
        try:
            window_minutes = int(request.args.get('window_minutes', '3'))
        except Exception:
            window_minutes = 3
        dry_run = str(request.args.get('dry_run', '')).strip().lower() in {'1', 'true', 'yes'}

        erp = ERPRepository()
        alerts = LocalAlertRepository(Config.LOCAL_DB)
        tg = TelegramService()

        now = datetime.now()
        start_erp = int(now.strftime('%Y%m%d')) - 1
        rows = erp.buscar_chamados_abertos_recentes_base(start_erp, limit=120)

        sent = []
        candidates = []
        for d in rows:
            cod = int(d.get('cod_solicitacao') or 0)
            if cod <= 0:
                continue
            if alerts.was_sent(cod, "opened"):
                continue
            data_val = d.get('data_cad')
            hora_val = d.get('hora_cad')
            try:
                hh = int(float(hora_val))
                mm = int((float(hora_val) - hh) * 100)
                ss = int((((float(hora_val) - hh) * 100) - mm) * 100)
            except Exception:
                hh, mm, ss = 0, 0, 0
            s_date = str(int(data_val or 0)).zfill(8)
            dt_open = datetime.strptime(f"{s_date}{hh:02d}{mm:02d}{ss:02d}", "%Y%m%d%H%M%S")
            diff_min = int((now - dt_open).total_seconds() // 60)
            if diff_min < 0 or diff_min > window_minutes:
                continue

            item = {
                "cod_solicitacao": cod,
                "minutos": diff_min,
                "solicitante": d.get('solicitante', ''),
                "titulo": d.get('titulo_solicitacao', ''),
                "status": d.get('cod_status_doc', '')
            }
            candidates.append(item)
            if dry_run:
                continue

            base_url = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
            link = f"{base_url}/chamados?id={cod}" if base_url else ""
            msg = f"Novo chamado aberto #{cod}\nSolicitante: {d.get('solicitante','')}\nTítulo: {d.get('titulo_solicitacao','')}"
            if link:
                msg = msg + f"\n{link}"
            ok = False
            for chat_id in tg_targets:
                if tg.send(chat_id, msg):
                    ok = True
            if ok:
                alerts.mark_sent(cod, "opened")
                sent.append(cod)

        if dry_run:
            return jsonify({"dry_run": True, "window_minutes": window_minutes, "candidates": candidates})
        return jsonify({"sent": sent})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@notify_bp.route('/access_report', methods=['POST'])
def notify_access_report():
    try:
        tg_targets = [t.strip() for t in (os.getenv("TELEGRAM_CHAT_IDS", "") or "").split(",") if t.strip()]
        has_tg = bool(os.getenv("TELEGRAM_BOT_TOKEN")) and bool(tg_targets)
        force = str(request.args.get('force', '')).strip().lower() in {'1', 'true', 'yes'}
        dry_run = str(request.args.get('dry_run', '')).strip().lower() in {'1', 'true', 'yes'}
        
        if not dry_run and not has_tg:
            return jsonify({"error": "Configure TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_IDS"}), 400

        now = datetime.now()
        if not force:
            if (now.hour < 18) or (now.hour == 18 and now.minute < 30):
                return jsonify({"error": "Aguarde 18:30 ou use force=1"}), 400

        # O log agora fica em rtf_generator/access.log
        log_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "access.log")
        
        if not os.path.exists(log_path):
            return jsonify({"message": "Nenhum acesso registrado ou log já apagado"}), 200

        ips_data = {}
        total_requests = 0
        
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("|")
                if len(parts) >= 4:
                    dt_str, ip, path, ua = parts[0], parts[1], parts[2], parts[3]
                    if not ip: continue
                    total_requests += 1
                    if ip not in ips_data:
                        ips_data[ip] = {"count": 0, "last_seen": ""}
                    ips_data[ip]["count"] += 1
                    ips_data[ip]["last_seen"] = dt_str

        uniq = len(ips_data)
        if uniq == 0:
            return jsonify({"message": "Nenhum acesso válido no log"}), 200

        d_label = now.strftime('%d/%m/%Y')
        lines = [f"Acessos ({d_label})", f"IPs únicos: {uniq} | Requisições: {total_requests}"]

        sorted_ips = sorted(ips_data.items(), key=lambda x: x[1]["count"], reverse=True)
        max_ips = 60
        for ip, data in sorted_ips[:max_ips]:
            cnt = data["count"]
            last_seen = data["last_seen"]
            last_hhmm = last_seen[11:16] if len(last_seen) >= 16 else ""
            lines.append(f"- {ip} ({cnt}) {last_hhmm}".rstrip())
            
        if uniq > max_ips:
            lines.append(f"... +{uniq - max_ips} IPs")

        msg = "\n".join(lines)
        if dry_run:
            return jsonify({"dry_run": True, "unique_ips": uniq, "total_requests": total_requests, "message": msg})

        tg = TelegramService()
        ok = False
        for chat_id in tg_targets:
            if tg.send(chat_id, msg):
                ok = True
                
        if ok:
            # Apaga o log após o envio bem-sucedido
            try:
                os.remove(log_path)
            except Exception as e:
                pass
            return jsonify({"sent": True, "unique_ips": uniq, "total_requests": total_requests})
            
        return jsonify({"sent": False, "error": "Falha ao enviar Telegram"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500
