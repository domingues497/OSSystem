from flask import Blueprint, jsonify, request
import os
import shutil
from datetime import datetime

from repositories.erp_repository import ERPRepository
from repositories.local_alert_repository import LocalAlertRepository
from repositories.local_access_repository import LocalAccessRepository
from services.telegram_service import TelegramService
from services.produtividade_service import ProdutividadeService
from config import Config
from utils.datetime_utils import erp_to_datetime, add_business_minutes, business_minutes_between

notify_bp = Blueprint('notify', __name__)

def _build_daily_productivity_block(day_date=None, max_tecnicos=30):
    day_date = day_date or datetime.now()
    start_erp = int(day_date.strftime('%Y%m%d'))
    end_erp = start_erp
    try:
        erp_repo = ERPRepository()
        svc = ProdutividadeService(erp_repo)
        eventos = erp_repo.buscar_produtividade_por_tecnico(start_erp, end_erp, access_scope=None)
    except Exception:
        return ""

    by_tec = {}
    seen_unique_ticket = set()
    unknown_key = svc._unknown if hasattr(svc, "_unknown") else "NÃO IDENTIFICADO"
    for ev in eventos:
        tipo = ev.get("tipo")
        cod = ev.get("cod_solicitacao")
        texto = ev.get("texto") or ""
        tecnico_raw = svc._extract_tecnico(tipo, texto) if hasattr(svc, "_extract_tecnico") else "---"
        tecnico_raw = tecnico_raw or "---"
        tecnico = svc._normalize_tecnico_alias(tecnico_raw) if hasattr(svc, "_normalize_tecnico_alias") else tecnico_raw

        if tipo in {"enviado", "andamento"} and cod is not None:
            key = (tipo, cod)
            if key in seen_unique_ticket:
                continue
            seen_unique_ticket.add(key)
        if tecnico not in by_tec:
            by_tec[tecnico] = {"enviados": 0, "andamento": 0, "finalizados": 0, "encerrados": 0}
        if tipo == "enviado":
            by_tec[tecnico]["enviados"] += 1
        elif tipo == "andamento":
            by_tec[tecnico]["andamento"] += 1
        elif tipo == "finalizado":
            by_tec[tecnico]["finalizados"] += 1
        elif tipo == "encerrado":
            by_tec[tecnico]["encerrados"] += 1

    if not by_tec:
        return ""

    ranked = []
    for tec, v in by_tec.items():
        total = (v.get("andamento") or 0) + (v.get("finalizados") or 0) + (v.get("encerrados") or 0)
        enviados = v.get("enviados") or 0
        ranked.append((tec, total, enviados, v.get("andamento") or 0, v.get("finalizados") or 0, v.get("encerrados") or 0))
    ranked.sort(key=lambda x: (-x[1], -x[2], x[0]))

    total_geral = sum(x[1] for x in ranked)
    total_enviados_geral = sum(x[2] for x in ranked)

    lines = []
    lines.append("")
    lines.append("Chamados por colaborador (hoje)")
    lines.append(f"Total interações: {total_geral} | Criados: {total_enviados_geral}")

    show = ranked[:max_tecnicos]
    for tec, total, enviados, andamento, finalizados, encerrados in show:
        label = tec if tec and tec != "---" else unknown_key
        parts = []
        if enviados:
            parts.append(f"+{enviados}")
        if andamento:
            parts.append(f"and {andamento}")
        if finalizados:
            parts.append(f"fim {finalizados}")
        if encerrados:
            parts.append(f"enc {encerrados}")
        detail = f" [{', '.join(parts)}]" if parts else ""
        lines.append(f"- {label}: {total}{detail}")

    if len(ranked) > max_tecnicos:
        lines.append(f"... +{len(ranked) - max_tecnicos} colaboradores")

    return "\n".join(lines)

def _format_br_dt_hhmm(dt_str):
    try:
        dt = datetime.strptime((dt_str or "").strip(), "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return ""


def _clean_log_user(raw_user):
    value = str(raw_user or "").strip()
    if not value or value == "-":
        return ""
    return value.replace("|", "/")

def _access_log_path():
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "access.log")

def _claim_access_log(original_path):
    original_path = (original_path or "").strip()
    if not original_path:
        return None
    if not os.path.exists(original_path):
        return None
    candidate = original_path + ".sending"
    try:
        os.replace(original_path, candidate)
        return candidate
    except Exception:
        try:
            if os.path.exists(candidate):
                return None
            os.replace(original_path, candidate)
            return candidate
        except Exception:
            return None

def _restore_access_log(claimed_path, original_path):
    try:
        if not claimed_path or not original_path:
            return
        if not os.path.exists(claimed_path):
            return
        if not os.path.exists(original_path):
            os.replace(claimed_path, original_path)
            return
        merged_path = original_path + ".merge"
        with open(merged_path, "wb") as out:
            with open(claimed_path, "rb") as f1:
                shutil.copyfileobj(f1, out)
            with open(original_path, "rb") as f2:
                shutil.copyfileobj(f2, out)
        os.replace(merged_path, original_path)
        try:
            os.remove(claimed_path)
        except Exception:
            pass
    except Exception:
        pass

def run_access_report_job(force=False, dry_run=False):
    tg_targets = [t.strip() for t in (os.getenv("TELEGRAM_CHAT_IDS", "") or "").split(",") if t.strip()]
    has_tg = bool(os.getenv("TELEGRAM_BOT_TOKEN")) and bool(tg_targets)
    if not dry_run and not has_tg:
        return {"status": 400, "payload": {"error": "Configure TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_IDS"}}

    now = datetime.now()
    if not force:
        if (now.hour < 18) or (now.hour == 18 and now.minute < 30):
            return {"status": 400, "payload": {"error": "Aguarde 18:30 ou use force=1"}}

    log_path = _access_log_path()
    claimed = _claim_access_log(log_path)
    if not claimed:
        return {"status": 200, "payload": {"message": "Nenhum acesso registrado ou log já apagado"}}

    ips_data = {}
    total_requests = 0
    last_access_raw = ""

    try:
        with open(claimed, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("|")
                if len(parts) >= 4:
                    dt_str, ip = parts[0], parts[1]
                    if not ip:
                        continue
                    total_requests += 1
                    if not last_access_raw or dt_str > last_access_raw:
                        last_access_raw = dt_str
                    user_label = _clean_log_user(parts[4] if len(parts) >= 5 else "")
                    if ip not in ips_data:
                        ips_data[ip] = {"count": 0, "last_seen": "", "users": []}
                    ips_data[ip]["count"] += 1
                    ips_data[ip]["last_seen"] = dt_str
                    if user_label and user_label not in ips_data[ip]["users"]:
                        ips_data[ip]["users"].append(user_label)

        uniq = len(ips_data)
        if uniq == 0:
            if not dry_run:
                _restore_access_log(claimed, log_path)
            return {"status": 200, "payload": {"message": "Nenhum acesso válido no log"}}

        d_label = now.strftime("%d/%m/%Y")
        last_access_br = _format_br_dt_hhmm(last_access_raw)
        lines = [
            f"Acessos ({d_label})",
            f"Último acesso: {last_access_br}" if last_access_br else "Último acesso: -",
            f"IPs únicos: {uniq} | Requisições: {total_requests}",
        ]

        productivity_block = _build_daily_productivity_block(day_date=now)
        if productivity_block:
            lines.append(productivity_block)
            lines.append("")
            lines.append("---")
            lines.append("Acessos detalhados (IPs)")
        else:
            lines.append("")
            lines.append("Chamados por colaborador (hoje): sem dados.")
            lines.append("")
            lines.append("---")
            lines.append("Acessos detalhados (IPs)")

        sorted_ips = sorted(ips_data.items(), key=lambda x: x[1]["count"], reverse=True)
        max_ips = 60
        for ip, data in sorted_ips[:max_ips]:
            cnt = data["count"]
            last_seen = data["last_seen"]
            last_hhmm = last_seen[11:16] if len(last_seen) >= 16 else ""
            users = ", ".join(data.get("users") or [])
            user_suffix = f" | Usuario: {users}" if users else ""
            lines.append(f"- {ip} ({cnt}) {last_hhmm}{user_suffix}".rstrip())

        if uniq > max_ips:
            lines.append(f"... +{uniq - max_ips} IPs")

        msg = "\n".join(lines)
        if dry_run:
            _restore_access_log(claimed, log_path)
            return {
                "status": 200,
                "payload": {
                    "dry_run": True,
                    "unique_ips": uniq,
                    "total_requests": total_requests,
                    "last_access_raw": last_access_raw,
                    "last_access_br": last_access_br,
                    "message": msg,
                },
            }

        tg = TelegramService()
        ok = False
        for chat_id in tg_targets:
            if tg.send(chat_id, msg):
                ok = True

        if ok:
            try:
                os.remove(claimed)
            except Exception:
                pass
            return {
                "status": 200,
                "payload": {
                    "sent": True,
                    "unique_ips": uniq,
                    "total_requests": total_requests,
                    "last_access_raw": last_access_raw,
                    "last_access_br": last_access_br,
                },
            }

        extra = {}
        if getattr(tg, "last_error", None):
            extra["telegram_error"] = tg.last_error
        _restore_access_log(claimed, log_path)
        return {"status": 500, "payload": {"sent": False, "error": "Falha ao enviar Telegram", **extra}}
    except Exception as e:
        if not dry_run:
            _restore_access_log(claimed, log_path)
        raise e

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
        force = str(request.args.get('force', '')).strip().lower() in {'1', 'true', 'yes'}
        dry_run = str(request.args.get('dry_run', '')).strip().lower() in {'1', 'true', 'yes'}
        result = run_access_report_job(force=force, dry_run=dry_run)
        return jsonify(result["payload"]), int(result["status"])
    except Exception as e:
        return jsonify({"error": str(e)}), 500
