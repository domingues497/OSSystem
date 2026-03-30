def extract_approver_from_text(text_upper, tecnicos_ti):
    """
    Extrai o nome do aprovador de um texto no formato 'APROVADA POR [NOME]'.
    """
    if "APROVADA POR" not in text_upper:
        return None
        
    try:
        parts = text_upper.split("APROVADA POR")
        if len(parts) > 1:
            nome_cru = parts[1].split(".")[0].split("\r")[0].split("\n")[0].strip()
            nome_sem_sufixo = nome_cru.split(" - ")[0].split(" -")[0].strip()
            
            # Se bater com alguém da TI
            for tec in tecnicos_ti:
                if nome_sem_sufixo in tec.upper():
                    return tec
            
            # Se contiver TI no nome extraído
            if "TI" in nome_cru or "T.I" in nome_cru:
                return nome_cru
    except:
        pass
    return None
