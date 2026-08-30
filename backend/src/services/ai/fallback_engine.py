"""Deterministic advisory wording, with metric names bound to their exact values."""
from src.schemas.ai_insight import NarrativeOutput
from src.services.ai.grounding_service import GroundedPayload


LABELS = {'revenue': 'Pendapatan', 'net_profit': 'Laba bersih', 'gross_margin_percentage': 'Margin kotor (%)', 'cash_balance': 'Saldo kas', 'project_profit': 'Laba proyek (akrual)', 'project_cash_position': 'Posisi kas proyek (likuiditas)', 'revenue_recognized': 'Pendapatan diakui', 'cash_received': 'Kas diterima', 'ar_total': 'Piutang outstanding', 'ap_total': 'Utang outstanding'}


class DeterministicFallbackEngine:
    @staticmethod
    def generate(payload: GroundedPayload) -> NarrativeOutput:
        facts = payload.factual_metrics
        headline = 'Ringkasan keuangan berbasis laporan terverifikasi'
        sentences = []
        primary = [key for key in LABELS if key in facts]
        for key in primary:
            value = facts[key]
            sentences.append(f'{LABELS[key]}: {value if value is not None else "Data tidak tersedia"}.')
        recommendations = ['Tinjau laporan sumber sebelum mengambil keputusan.']
        margin = facts.get('project_margin', facts.get('gross_margin_percentage'))
        if margin is not None:
            sentences.append('Margin rendah; perlu perhatian manajemen.' if margin < 10 else 'Margin moderat; pantau biaya.' if margin < 20 else 'Margin berada pada rentang sehat menurut indikator advisory.')
        cash = facts.get('project_cash_position', facts.get('cash_balance'))
        profit = facts.get('project_profit', facts.get('net_profit'))
        if cash is not None and profit is not None and profit > 0 and cash < 0:
            headline = 'Laba positif, posisi kas defisit'
            sentences.append('Laba akrual berbeda dengan kas. Penyebab spesifik memerlukan pemeriksaan transaksi sumber.')
            recommendations.append('Tinjau piutang dan jadwal penagihan; jangan menyamakan laba dengan kas tersedia.')
        if facts.get('ar_over_90', 0):
            sentences.append(f'Piutang lewat jatuh tempo lebih dari sembilan puluh hari: {facts["ar_over_90"]}.')
            recommendations.append('Prioritaskan peninjauan penagihan piutang yang paling lama jatuh tempo.')
        if facts.get('ap_over_90', 0):
            sentences.append(f'Utang lewat jatuh tempo lebih dari sembilan puluh hari: {facts["ap_over_90"]}.')
            recommendations.append('Tinjau jatuh tempo vendor dan ketersediaan kas; pembayaran tetap memerlukan persetujuan.')
        if not payload.integrity_valid:
            headline = 'Integritas laporan perlu ditinjau'
            recommendations = ['Tinjau diagnostik integritas; jangan gunakan ringkasan sebagai dasar posting.']
        return NarrativeOutput(headline=headline, factual_metrics=facts.copy(), analytical_narrative=' '.join(sentences) or 'Data tidak tersedia.', actionable_recommendations=recommendations)
