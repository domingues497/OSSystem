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
