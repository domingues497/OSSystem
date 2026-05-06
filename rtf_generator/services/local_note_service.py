class LocalNoteService:
    def __init__(self, local_repo):
        self.local_repo = local_repo

    def salvar(self, payload):
        cod_solicitacao = payload.get('cod_solicitacao')
        note = payload.get('note')
        
        if not cod_solicitacao or not note:
            return {"error": "Dados incompletos"}
            
        self.local_repo.insert_note(cod_solicitacao, note)
        return {"success": True}

    def listar_por_chamado(self, cod_solicitacao):
        return self.local_repo.get_notes_by_ticket(cod_solicitacao)

    def listar_ids_com_notas(self, ticket_ids):
        return self.local_repo.get_ticket_ids_with_notes(ticket_ids)

    def salvar_atendente(self, payload):
        cod_solicitacao = payload.get('cod_solicitacao')
        atendente = (payload.get('atendente') or '').strip()

        if not cod_solicitacao:
            return {"error": "Chamado não informado"}

        if atendente:
            self.local_repo.upsert_assignee(cod_solicitacao, atendente)
        else:
            self.local_repo.delete_assignee(cod_solicitacao)

        return {"success": True, "atendente": atendente}

    def obter_atendente(self, cod_solicitacao):
        return {"atendente": self.local_repo.get_assignee_by_ticket(cod_solicitacao)}

    def listar_atendentes(self):
        return self.local_repo.get_distinct_assignees()
