"""Multi-signal deterministic document classification engine.

Combines header prominence, body keywords, document number patterns,
and structural field combinations across Indonesian contractor document types:
TRANSFER_PROOF, VENDOR_INVOICE, CUSTOMER_INVOICE, RECEIPT, PURCHASE_ORDER,
PO_CUSTOMER, SPK, BAST, SURAT_JALAN, BANK_STATEMENT, TAX_INVOICE, CONTRACT, and UNKNOWN.
"""
from dataclasses import dataclass
from decimal import Decimal
import re
from typing import Dict, List, Tuple

from src.models.enums import DocumentType


@dataclass(frozen=True)
class ClassificationResult:
    document_type: DocumentType
    confidence: Decimal
    reasons: tuple[str, ...]
    needs_review: bool


# Header regex rules checked preferentially in the first 25 lines of text
_HEADER_RULES: List[Tuple[DocumentType, str, int, str]] = [
    (DocumentType.TRANSFER_PROOF, r"\b(?:bukti\s+transfer|bukti\s+transaksi|transfer\s+berhasil|transfer\s+sukses|m-transfer|m-banking|internet\s+banking|transaksi\s+berhasil)\b", 70, "header: transfer-proof"),
    (DocumentType.BANK_STATEMENT, r"\b(?:rekening\s+koran|bank\s+statement|mutasi\s+rekening|account\s+statement)\b", 70, "header: bank-statement"),
    (DocumentType.TAX_INVOICE, r"\b(?:faktur\s+pajak|e-faktur)\b", 70, "header: tax-invoice"),
    (DocumentType.CUSTOMER_INVOICE, r"\b(?:customer\s+invoice|invoice\s+pelanggan|faktur\s+penjualan|tagihan\s+proyek|progress\s+billing)\b", 65, "header: customer-invoice"),
    (DocumentType.VENDOR_INVOICE, r"\b(?:tax\s+invoice|vendor\s+invoice|invoice\s+vendor|faktur\s+pembelian|tagihan\s+vendor|tagihan\s+pembelian|commercial\s+invoice)\b", 70, "header: vendor-invoice"),
    (DocumentType.SURAT_JALAN, r"\b(?:surat\s+jalan|delivery\s+order|surat\s+pengantar\s+barang)\b", 65, "header: delivery-order"),
    (DocumentType.BAST, r"\b(?:berita\s+acara\s+serah\s+terima|serah\s+terima\s+pekerjaan|dokumen\s+bast|^\s*bast\b)\b", 65, "header: BAST"),
    (DocumentType.SPK, r"\b(?:surat\s+perintah\s+kerja|work\s+order|dokumen\s+spk|^\s*spk\b)\b", 65, "header: SPK"),
    (DocumentType.PO_CUSTOMER, r"\b(?:customer\s+po|po\s+customer|po\s+pelanggan|customer\s+order\s+ref)\b", 65, "header: customer-PO"),
    (DocumentType.PURCHASE_ORDER, r"\b(?:purchase\s+order|pesanan\s+pembelian|order\s+pembelian)\b", 65, "header: purchase-order"),
    (DocumentType.RECEIPT, r"\b(?:struk\s+pembelian|purchase\s+receipt|kuitansi|kwitansi|nota\s+kontan|nota\s+pembelian|nota\s+toko)\b", 60, "header: purchase-receipt"),
    (DocumentType.CONTRACT, r"\b(?:perjanjian\s+kontrak|surat\s+perjanjian|kontrak\s+kerja|perjanjian\s+pemborongan)\b", 60, "header: contract"),
]

# Body signals: (pattern, score, signal_name) per document type
_BODY_SIGNALS: Dict[DocumentType, List[Tuple[str, int, str]]] = {
    DocumentType.TRANSFER_PROOF: [
        (r"\b(?:rekening\s+tujuan|nama\s+tujuan|penerima|tujuan\s+transfer)\b", 25, "transfer-target"),
        (r"\b(?:rekening\s+pengirim|sumber\s+dana|pengirim)\b", 20, "transfer-source"),
        (r"\b(?:no\s+referensi|ref\s*#?|nomor\s+transaksi|reference\s+no)\b", 20, "transfer-ref"),
        (r"\b(?:bi-fast|realtime\s+online|skn|rtgs|kliring)\b", 20, "transfer-network"),
        (r"\b(?:bca|bank\s+central\s+asia|mandiri|bri|bni|bsi|cimb|permata|danamon|jago|jenius)\b", 15, "bank-identity"),
        (r"\b(?:nominal|jumlah\s+transfer)\b", 20, "transfer-amount-label"),
    ],
    DocumentType.BANK_STATEMENT: [
        (r"\b(?:saldo\s+awal|saldo\s+akhir)\b", 40, "statement-balance"),
        (r"\b(?:mutasi\s+debit|mutasi\s+kredit|total\s+debit|total\s+kredit)\b", 35, "statement-mutations"),
        (r"\b(?:periode|tgl\s+valuta|tgl\s+posting)\b", 20, "statement-period"),
    ],
    DocumentType.VENDOR_INVOICE: [
        (r"\b(?:jatuh\s+tempo|due\s+date)\b", 20, "invoice-duedate"),
        (r"\b(?:subtotal|sub\s+total|dpp)\b", 20, "invoice-subtotal"),
        (r"\b(?:ppn\s*1[12]%|vat\s*1[12]%|pajak\s+pertambahan\s+nilai)\b", 20, "invoice-vat"),
        (r"\b(?:termin|termin\s+ke|syarat\s+pembayaran)\b", 15, "invoice-payment-terms"),
        (r"\b(?:INV|FAK|BILL)[-/][A-Z0-9-/]+", 25, "invoice-number-pattern"),
        (r"\b(?:faktur|invoice)\b", 10, "invoice-keyword"),
    ],
    DocumentType.CUSTOMER_INVOICE: [
        (r"\b(?:bill\s+to|tagihan\s+kepada|kepada\s+yth)\b", 20, "customer-recipient"),
        (r"\b(?:proyek|project\s+name|nama\s+proyek)\b", 20, "customer-project"),
        (r"\b(?:progress\s+pekerjaan|prestasi\s+pekerjaan|termin\s+ke)\b", 25, "customer-progress"),
        (r"\b(?:retensi|retention)\b", 20, "customer-retention"),
    ],
    DocumentType.RECEIPT: [
        (r"\b(?:tunai|cash|kembali|kembalian)\b", 30, "receipt-cash"),
        (r"\b(?:tanda\s+terima|sudah\s+terima\s+dari)\b", 25, "receipt-received-from"),
        (r"\b(?:untuk\s+pembayaran|guna\s+membayar)\b", 25, "receipt-payment-for"),
    ],
    DocumentType.PURCHASE_ORDER: [
        (r"\b(?:po\s*no|nomor\s+po|po\s+number)\s*[:#]?\s*[A-Za-z0-9\-\/]+", 35, "po-number-pattern"),
        (r"\b(?:harap\s+kirim|deliver\s+to|kirim\s+ke)\b", 20, "po-delivery"),
        (r"\b(?:syarat\s+penyerahan|delivery\s+terms)\b", 20, "po-terms"),
    ],
    DocumentType.SURAT_JALAN: [
        (r"\b(?:no(?:mor)?\s*polisi|nopol|kendaraan)\b", 30, "sj-vehicle"),
        (r"\b(?:nama\s+supir|driver|pengemudi)\b", 25, "sj-driver"),
        (r"\b(?:diterima\s+oleh|tanda\s+tangan\s+penerima|penerima\s+barang)\b", 25, "sj-receiver"),
        (r"\b(?:koli|colli|unit|batang|sak|lembar)\b", 15, "sj-goods"),
    ],
    DocumentType.BAST: [
        (r"\b(?:pihak\s+pertama|pihak\s+kedua)\b", 30, "bast-parties"),
        (r"\b(?:telah\s+selesai|pekerjaan\s+telah|serah\s+terima)\b", 30, "bast-completion"),
        (r"\b(?:prestasi\s+100%|progress\s+100%)\b", 25, "bast-progress"),
    ],
    DocumentType.SPK: [
        (r"\b(?:pemberi\s+tugas|pelaksana\s+tugas|pelaksana\s+pekerjaan)\b", 30, "spk-parties"),
        (r"\b(?:lingkup\s+pekerjaan|scope\s+of\s+work)\b", 25, "spk-scope"),
        (r"\b(?:jangka\s+waktu|masa\s+pelaksanaan)\b", 20, "spk-duration"),
        (r"\b(?:nilai\s+pekerjaan|nilai\s+kontrak)\b", 20, "spk-value"),
    ],
    DocumentType.TAX_INVOICE: [
        (r"\b(?:kode\s+dan\s+nomor\s+seri\s+faktur\s+pajak|pengusaha\s+kena\s+pajak|npwp)\b", 40, "tax-identifiers"),
        (r"\b\d{3}\.\d{3}-\d{2}\.\d{8}\b", 40, "tax-invoice-number-pattern"),
    ],
    DocumentType.CONTRACT: [
        (r"\b(?:pasal\s+\d+|ayat\s+\d+)\b", 30, "contract-clauses"),
        (r"\b(?:perjanjian\s+ini|kedua\s+belah\s+pihak)\b", 25, "contract-agreement"),
    ],
}


def classify_text(text: str) -> ClassificationResult:
    """Classifies document text using multi-signal weighted scoring."""
    if not text or not text.strip():
        return ClassificationResult(DocumentType.UNKNOWN, Decimal("0.00"), ("empty text",), True)

    lines = text.splitlines()
    header_region = "\n".join(lines[:25])

    scores: Dict[DocumentType, int] = {t: 0 for t in DocumentType}
    signals: Dict[DocumentType, List[str]] = {t: [] for t in DocumentType}

    # 1. Header rules (high weight)
    for doc_type, pattern, weight, reason in _HEADER_RULES:
        if re.search(pattern, header_region, re.I):
            scores[doc_type] += weight
            signals[doc_type].append(reason)

    # 2. General invoice vs PO disambiguation
    # If the document prominently displays "INVOICE" or "FAKTUR" at the top,
    # secondary references like "PO Ref:" should not cause it to become a PO.
    has_invoice_title = bool(re.search(r"\b(?:invoice|faktur(?!\s+pajak)|tagihan)\b", header_region, re.I))
    has_po_title = bool(re.search(r"\b(?:purchase\s+order|order\s+pembelian)\b", header_region, re.I))
    has_bast_title = bool(re.search(r"\b(?:berita\s+acara\s+serah\s+terima|\bbast\b)\b", header_region, re.I))
    has_sj_title = bool(re.search(r"\b(?:surat\s+jalan|delivery\s+order)\b", header_region, re.I))
    has_transfer_title = bool(re.search(r"\b(?:bukti\s+transfer|bukti\s+transaksi|transfer\s+berhasil|transfer\s+sukses|m-transfer)\b", header_region, re.I))

    if has_invoice_title and not has_po_title:
        scores[DocumentType.VENDOR_INVOICE] += 30
        signals[DocumentType.VENDOR_INVOICE].append("header: explicit invoice title")

    if has_transfer_title:
        scores[DocumentType.TRANSFER_PROOF] += 30
        signals[DocumentType.TRANSFER_PROOF].append("header: explicit transfer title")

    # 3. Body signals
    for doc_type, signal_list in _BODY_SIGNALS.items():
        for pattern, weight, sig_name in signal_list:
            if re.search(pattern, text, re.I):
                scores[doc_type] += weight
                signals[doc_type].append(sig_name)

    # Disambiguate VENDOR_INVOICE vs CUSTOMER_INVOICE
    # If Customer Invoice specific signals (progress billing, retention, project billing to client) are prominent
    if scores[DocumentType.CUSTOMER_INVOICE] > 40 and scores[DocumentType.CUSTOMER_INVOICE] > scores[DocumentType.VENDOR_INVOICE]:
        pass
    elif scores[DocumentType.VENDOR_INVOICE] > 0 and scores[DocumentType.CUSTOMER_INVOICE] > 0:
        # Default invoices in contractor domain to VENDOR_INVOICE unless customer invoice is explicitly declared
        if not re.search(r"customer\s+invoice|invoice\s+pelanggan|faktur\s+penjualan", header_region, re.I):
            scores[DocumentType.VENDOR_INVOICE] += 15

    # Find highest scoring type
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_type, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0

    if top_score < 35:
        reasons = tuple(signals[top_type]) or ("no supported deterministic signal",)
        return ClassificationResult(DocumentType.UNKNOWN, Decimal("0.30") if top_score > 0 else Decimal("0.00"), reasons, True)

    # Check for ambiguous tie (top 2 candidates within 5 points and both above 45)
    if (top_score - second_score) <= 5 and second_score >= 45:
        combined_reasons = tuple(signals[top_type] + signals[ranked[1][0]])
        return ClassificationResult(DocumentType.UNKNOWN, Decimal("0.45"), combined_reasons, True)

    # Assign confidence based on score
    if top_score >= 70:
        conf = Decimal("0.95")
    elif top_score >= 50:
        conf = Decimal("0.85")
    else:
        conf = Decimal("0.75")

    return ClassificationResult(
        document_type=top_type,
        confidence=conf,
        reasons=tuple(signals[top_type]),
        needs_review=False,
    )
