"""Safe operational commands; never interpret accounting instructions."""


class WhatsAppCommandService:
    HELP = "Kirim foto nota/PDF atau ketik STATUS, RINGKASAN, HELP. Persetujuan dan koreksi finansial tetap melalui aplikasi SaaS."
    _HELP_COMMANDS = {"HELP", "BANTUAN", "MENU", "?"}
    _GUARDED_VERBS = {
        "POST", "APPROVE", "SETUJUI", "DELETE", "HAPUS", "DROP",
        "DEBIT", "CREDIT", "KREDIT", "JURNAL", "POSTING", "BATAL", "TOLAK",
    }

    async def reply(self, text, sender, client):
        command = " ".join(text.upper().split())
        if not command:
            return None

        if command in {"STATUS", "RINGKASAN", "STATUS PROYEK", "ANTREAN NOTA"}:
            if sender.role_in_org not in {"PROJECT_MANAGER", "FINANCE_MANAGER"}:
                return "Anda tidak memiliki izin untuk ringkasan organisasi. Hubungi administrator."
            result = await client.channel_request("status", {"phone_number": sender.phone_number})
            return f"Dokumen: {result['documents']}. Menunggu review: {result['pending_review']}. Proyek aktif: {result['active_projects']}. Persetujuan melalui SaaS."

        if command in self._HELP_COMMANDS:
            return self.HELP

        # If user explicitly tries an accounting/database verb, remind them about SaaS authority
        words = set(command.replace(";", " ").replace(",", " ").split())
        if words & self._GUARDED_VERBS or any(verb in command for verb in ("DROP TABLE", "DELETE HISTORY")):
            return self.HELP

        # Non-command natural language is candidate session caption/description context; record silently
        return None
