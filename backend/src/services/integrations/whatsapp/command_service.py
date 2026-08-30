"""Safe operational commands; never interpret accounting instructions."""


class WhatsAppCommandService:
    HELP = "Kirim foto nota/PDF atau ketik STATUS, RINGKASAN, HELP. Persetujuan dan koreksi finansial tetap melalui aplikasi SaaS."

    async def reply(self, text, sender, client):
        command = " ".join(text.upper().split())
        if command in {"STATUS", "RINGKASAN", "STATUS PROYEK", "ANTREAN NOTA"}:
            if sender.role_in_org not in {"PROJECT_MANAGER", "FINANCE_MANAGER"}:
                return "Anda tidak memiliki izin untuk ringkasan organisasi. Hubungi administrator."
            result = await client.channel_request("status", {"phone_number": sender.phone_number})
            return f"Dokumen: {result['documents']}. Menunggu review: {result['pending_review']}. Proyek aktif: {result['active_projects']}. Persetujuan melalui SaaS."
        return self.HELP
