import re

def classify_ticket(titulo, descricao=""):
    """
    Classificação usando Processamento de Linguagem Natural (Heurística).
    Classifica entre 'Incidente', 'Requisição' e 'BI'.
    """
    text = (str(titulo) + " " + str(descricao)).upper()
    
    bi_patterns = [
        r'\bBI\b', r'\bB\.I\b', r'\bQLIK\b', r'\bQLIKVIEW\b', r'\bQLIKSENSE\b', 
        r'\bDASHBOARD\b', r'\bPOWER BI\b', r'\bPOWERBI\b', r'\bDATASET\b'
    ]
    if any(re.search(p, text) for p in bi_patterns):
        return "BI"
    
    incident_keywords = [
        'ERRO', 'FALHA', 'NÃO FUNCIONA', 'NAO FUNCIONA', 'BUG', 'PAROU', 'PROBLEMA', 
        'LENTIDÃO', 'LENTIDAO', 'TRAVANDO', 'FORA DO AR', 'QUEDAS', 'INTERROMPIDO',
        'MENSAGEM DE ERRO', 'INCORRETO', 'DIVERGÊNCIA', 'DIVERGENCIA', 'ESTORNO', 'RETRABALHO'
    ]
    
    request_keywords = [
        'SOLICITO', 'LIBERAÇÃO', 'LIBERACAO', 'ACESSO', 'INSTALAÇÃO', 'INSTALACAO', 
        'CONFIGURAÇÃO', 'CONFIGURACAO', 'NOVO USUÁRIO', 'NOVO USUARIO', 'TROCA DE SENHA', 
        'RELATÓRIO', 'RELATORIO', 'EXTRAÇÃO', 'EXTRACAO', 'CADASTRO', 'CRIAR', 'CRIACAO',
        'ALTERAR', 'MUDANÇA', 'MUDANCA', 'DÚVIDA', 'DUVIDA', 'PEDIDO', 'SOLICITAÇÃO'
    ]
    
    inc_score = sum(1 for word in incident_keywords if re.search(rf'\b{word}\b', text))
    req_score = sum(1 for word in request_keywords if re.search(rf'\b{word}\b', text))
    
    if inc_score > req_score:
        return "Incidente"
    elif req_score > inc_score:
        return "Requisição"
    else:
        if inc_score > 0:
            return "Incidente"
        return "Requisição"
