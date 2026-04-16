from datetime import datetime, timedelta
import re

class ProdutividadeService:
    def __init__(self, erp_repo):
        self.erp_repo = erp_repo
        self._unknown = "NÃO IDENTIFICADO"

    def _normalize_spaces(self, s):
        s = (s or "").replace("\u00a0", " ").replace("\r", " ").replace("\n", " ")
        return " ".join(s.split()).strip()

    def _canonicalize_tecnico(self, tecnico):
        t = self._normalize_spaces(tecnico).upper()
        if not t:
            return self._unknown

        t = (
            t.replace("–", "-")
            .replace("—", "-")
            .replace("−", "-")
            .replace("‐", "-")
        )
        t = t.strip().strip(".")
        t = re.sub(r"\s*-\s*", " - ", t)
        if t.endswith(" TI") and not t.endswith(" - TI"):
            t = t[:-3] + " - TI"
        t = self._normalize_spaces(t)

        if t in {"TI", "T.I", "T.I.", "- TI", "-TI", "T I", "T I."}:
            return self._unknown
        return t

    def _normalize_tecnico_alias(self, tecnico):
        t = self._canonicalize_tecnico(tecnico)
        if t == self._unknown:
            return self._unknown

        # Consolidar aliases do mesmo técnico para não dividir contagem.
        if t in {"RAFAEL - TI", "RAFAEL SIMAO - TI"} or ("SIMAO" in t and "RAFAEL" in t):
            return "RAFAEL SIMAO - TI"
        if "WECKERLIN" in t or re.search(r"\bRAFAEL\s+W\b", t):
            return "RAFAEL WECKERLIN - TI"
        return t

    def _extract_between(self, text, marker):
        idx = text.lower().find(marker.lower())
        if idx < 0:
            return ""
        rest = text[idx + len(marker):]
        rest = rest.split(".")[0]
        return self._normalize_spaces(rest)

    def _extract_tecnico(self, tipo, texto):
        texto = texto or ""
        if tipo == "finalizado":
            m = re.search(r"Solicitação finalizada por\s+(.*?)\.\s*Aguardando", texto, flags=re.IGNORECASE | re.DOTALL)
            if m:
                return self._normalize_spaces(m.group(1))
            m = re.search(r"Solicitação finalizada por\s+(.*?)\.\s*$", texto, flags=re.IGNORECASE | re.DOTALL)
            if m:
                return self._normalize_spaces(m.group(1))
            return self._extract_between(texto, "Solicitação finalizada por")
        if tipo == "encerrado":
            m = re.search(r"Solicitação encerrada por\s+(.*?)\.\s*$", texto, flags=re.IGNORECASE | re.DOTALL)
            if m:
                return self._normalize_spaces(m.group(1))
            return self._extract_between(texto, "Solicitação encerrada por")
        if tipo == "andamento":
            m = re.search(r"Solicitação aprovada por\s+(.*?)\.\s*Solicitação atualizada", texto, flags=re.IGNORECASE | re.DOTALL)
            if m:
                return self._normalize_spaces(m.group(1))
            return self._extract_between(texto, "Solicitação aprovada por")
        if tipo == "enviado":
            m = re.search(r"o usu[aá]rio\s+(.*?)\s+solicitou", texto, flags=re.IGNORECASE | re.DOTALL)
            if m:
                return self._normalize_spaces(m.group(1))
        return "---"

    def obter_produtividade(self, start_date_str=None, end_date_str=None):
        if start_date_str and end_date_str:
            start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_dt = datetime.strptime(end_date_str, '%Y-%m-%d')
        else:
            now = datetime.now()
            end_dt = now
            start_dt = now - timedelta(days=6)

        start_erp = int(start_dt.strftime('%Y%m%d'))
        end_erp = int(end_dt.strftime('%Y%m%d'))

        eventos = self.erp_repo.buscar_produtividade_por_tecnico(start_erp, end_erp)

        by_day = {}
        seen_unique_ticket = set()
        for ev in eventos:
            d = ev["data_grav"]
            tipo = ev["tipo"]
            cod = ev.get("cod_solicitacao")
            tecnico_raw = self._extract_tecnico(tipo, ev["texto"]) or "---"
            tecnico = self._normalize_tecnico_alias(tecnico_raw)
            if tipo in {"enviado", "andamento"} and cod is not None:
                key = (tipo, d, cod)
                if key in seen_unique_ticket:
                    continue
                seen_unique_ticket.add(key)
            if d not in by_day:
                by_day[d] = {}
            if tecnico not in by_day[d]:
                by_day[d][tecnico] = {"enviados": 0, "andamento": 0, "finalizados": 0, "encerrados": 0}
            if tipo == "enviado":
                by_day[d][tecnico]["enviados"] += 1
            elif tipo == "andamento":
                by_day[d][tecnico]["andamento"] += 1
            elif tipo == "finalizado":
                by_day[d][tecnico]["finalizados"] += 1
            elif tipo == "encerrado":
                by_day[d][tecnico]["encerrados"] += 1

        results = []
        for d in sorted(by_day.keys()):
            d_str = str(d)
            dow_map = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
            try:
                dow = dow_map[datetime.strptime(f"{d_str[0:4]}-{d_str[4:6]}-{d_str[6:8]}", "%Y-%m-%d").weekday()]
            except Exception:
                dow = ""
            tecnicos = []
            for tech, vals in sorted(by_day[d].items(), key=lambda x: x[0]):
                total = vals["andamento"] + vals["finalizados"]
                tecnicos.append({
                    "tecnico": tech,
                    "enviados": vals["enviados"],
                    "andamento": vals["andamento"],
                    "finalizados": vals["finalizados"],
                    "encerrados": vals["encerrados"],
                    "total": total
                })
            results.append({
                "data": f"{d_str[6:8]}/{d_str[4:6]}/{d_str[0:4]} ({dow})" if dow else f"{d_str[6:8]}/{d_str[4:6]}/{d_str[0:4]}",
                "tecnicos": tecnicos
            })

        return results
