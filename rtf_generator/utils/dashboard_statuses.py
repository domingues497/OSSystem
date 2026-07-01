STATUS_DEFINITIONS = [
    {"code": "AA", "label": "Aguardando autorizacao", "chart_label": "Aguardando autorizacao"},
    {"code": "IM", "label": "Aberta", "chart_label": "Aberta"},
    {"code": "AB", "label": "Aberta", "chart_label": "Aberta"},
    {"code": "EA", "label": "Em andamento", "chart_label": "Em andamento"},
    {"code": "AN", "label": "Em andamento", "chart_label": "Em andamento"},
    {"code": "AV", "label": "Aguardando avaliacao", "chart_label": "Aguardando avaliacao"},
    {"code": "PL", "label": "Programada", "chart_label": "Programada"},
    {"code": "RT", "label": "Retrabalho", "chart_label": "Retrabalho"},
    {"code": "BA", "label": "Encerrada", "chart_label": "Encerrada"},
    {"code": "RJ", "label": "Rejeitada", "chart_label": "Rejeitada"},
]

STATUS_BY_CODE = {item["code"]: item for item in STATUS_DEFINITIONS}
KANBAN_GROUP_DEFINITIONS = [
    {
        "id": "aguardando",
        "label": "Aguardando autorizacao",
        "status_codes": ["AA"],
        "organizer": "aguardando",
    },
    {
        "id": "aberta",
        "label": "Aberta",
        "status_codes": ["IM", "AB"],
        "organizer": "",
    },
    {
        "id": "andamento",
        "label": "Em andamento",
        "status_codes": ["EA", "AN"],
        "organizer": "andamento",
    },
    {
        "id": "avaliacao",
        "label": "Aguardando avaliacao",
        "status_codes": ["AV"],
        "organizer": "",
    },
    {
        "id": "programada",
        "label": "Programada",
        "status_codes": ["PL"],
        "organizer": "",
    },
    {
        "id": "retrabalho",
        "label": "Retrabalho",
        "status_codes": ["RT"],
        "organizer": "",
    },
    {
        "id": "encerrada",
        "label": "Encerrada",
        "status_codes": ["BA"],
        "organizer": "",
    },
    {
        "id": "rejeitada",
        "label": "Rejeitada",
        "status_codes": ["RJ"],
        "organizer": "",
    },
]


def get_dashboard_status_definitions():
    return [dict(item) for item in STATUS_DEFINITIONS]


def get_default_dashboard_status_codes():
    return [item["code"] for item in STATUS_DEFINITIONS]


def get_default_kanban_status_codes():
    return [item["code"] for item in STATUS_DEFINITIONS]


def get_kanban_group_definitions(selected_codes=None):
    selected = set(normalize_dashboard_status_codes(selected_codes) or get_default_kanban_status_codes())
    groups = []
    for group in KANBAN_GROUP_DEFINITIONS:
        group_status_codes = [code for code in group["status_codes"] if code in selected]
        if not group_status_codes:
            continue
        groups.append(
            {
                "id": group["id"],
                "label": group["label"],
                "organizer": group["organizer"],
                "status_codes": group_status_codes,
            }
        )
    return groups


def get_kanban_column_ids(selected_codes=None):
    return [item["id"] for item in get_kanban_group_definitions(selected_codes)]


def normalize_kanban_column_order(column_ids, selected_codes=None):
    allowed = get_kanban_column_ids(selected_codes)
    ordered = []
    for raw in column_ids or []:
        column_id = str(raw or "").strip().lower()
        if not column_id or column_id not in allowed or column_id in ordered:
            continue
        ordered.append(column_id)
    for column_id in allowed:
        if column_id not in ordered:
            ordered.append(column_id)
    return ordered


def normalize_dashboard_status_codes(values):
    codes = []
    for raw in values or []:
        code = str(raw or "").strip().upper()
        if not code or code not in STATUS_BY_CODE or code in codes:
            continue
        codes.append(code)
    return codes
