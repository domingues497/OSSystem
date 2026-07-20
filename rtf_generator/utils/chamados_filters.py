CHAMADOS_FILTER_DEFINITIONS = [
    {
        "id": "id",
        "label": "Chamado",
        "description": "Busca pelo numero do chamado.",
        "default_visible": True,
    },
    {
        "id": "solicitante",
        "label": "Solicitante",
        "description": "Busca pelo nome do solicitante.",
        "default_visible": False,
    },
    {
        "id": "ultima_iteracao",
        "label": "Ult. Iteracao",
        "description": "Filtra pelo responsavel da ultima iteracao.",
        "default_visible": False,
    },
    {
        "id": "conteudo",
        "label": "Conteudo",
        "description": "Busca por texto livre no chamado.",
        "default_visible": True,
    },
    {
        "id": "tipo",
        "label": "Tipo",
        "description": "Filtra por categoria do chamado.",
        "default_visible": True,
    },
    {
        "id": "assunto_busca",
        "label": "Busca de Assunto",
        "description": "Campo de busca para localizar assunto/setor.",
        "default_visible": True,
    },
    {
        "id": "assunto",
        "label": "Assunto / Setor",
        "description": "Seleciona o assunto ou setor desejado.",
        "default_visible": True,
    },
]


def get_chamados_filter_definitions():
    return [dict(item) for item in CHAMADOS_FILTER_DEFINITIONS]


def get_default_chamados_filter_ids(is_admin=False):
    filter_ids = []
    for item in CHAMADOS_FILTER_DEFINITIONS:
        if item["default_visible"] or (is_admin and item["id"] in {"solicitante", "ultima_iteracao"}):
            filter_ids.append(item["id"])
    return filter_ids


def normalize_chamados_filter_ids(filter_ids=None, is_admin=False):
    allowed_ids = [item["id"] for item in CHAMADOS_FILTER_DEFINITIONS]
    normalized = []
    for raw in filter_ids or []:
        value = str(raw or "").strip()
        if not value or value not in allowed_ids or value in normalized:
            continue
        normalized.append(value)
    return normalized or get_default_chamados_filter_ids(is_admin=is_admin)
