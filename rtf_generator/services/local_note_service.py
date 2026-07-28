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

    def salvar_contato_usuario_chamado(self, payload):
        cod_usuario = payload.get('cod_usuario')
        if not cod_usuario:
            return {"error": "Usuario do chamado nao informado"}

        teams_user = (payload.get('teams_user') or '').strip() or None
        whatsapp_user = (payload.get('whatsapp_user') or '').strip() or None
        raw_cod_gestor = (payload.get('cod_gestor') or '').strip()

        cod_gestor = None
        if raw_cod_gestor:
            if not raw_cod_gestor.isdigit():
                return {"error": "Codigo do gestor deve ser numerico"}
            cod_gestor = int(raw_cod_gestor)

        self.local_repo.upsert_chamados_usuario_contato(
            cod_usuario=cod_usuario,
            teams_user=teams_user,
            whatsapp_user=whatsapp_user,
            cod_gestor=cod_gestor,
        )
        return {
            "success": True,
            "cod_usuario": int(cod_usuario),
            "teams_user": teams_user or "",
            "whatsapp_user": whatsapp_user or "",
            "cod_gestor": cod_gestor or "",
        }
