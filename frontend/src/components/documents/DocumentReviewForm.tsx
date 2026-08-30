import React, { useState } from 'react';
import { Button } from '../ui/Button';
import { DocumentResponse } from '../../types/api';

interface Props { document: DocumentResponse; onSave: (changes: Record<string, unknown>, reason: string) => Promise<void>; onApprove: () => Promise<void>; }

export const DocumentReviewForm: React.FC<Props> = ({ document, onSave, onApprove }) => {
  const candidate = document.candidate_transaction;
  const [projectId, setProjectId] = useState(String(candidate.project_id ?? ''));
  const [counterpartyId, setCounterpartyId] = useState(String(candidate.counterparty_id ?? ''));
  const [reason, setReason] = useState('Verifikasi dokumen sumber');
  const [busy, setBusy] = useState(false);
  const save = async () => { setBusy(true); try { await onSave({ project_id: projectId || null, counterparty_id: counterpartyId || null }, reason); } finally { setBusy(false); } };
  return <section className="space-y-4" aria-label="Form koreksi hasil ekstraksi">
    <div><h3 className="font-semibold text-slate-900">Kandidat Transaksi</h3><p className="text-xs text-slate-500">Tidak ada pilihan debit atau kredit. Backend accounting rules tetap otoritatif.</p></div>
    <div className="rounded-lg bg-amber-50 p-3"><strong className="text-xs">Flag review</strong><div className="mt-1 flex flex-wrap gap-1">{document.review_flags.map(flag => <span key={flag} className="rounded bg-amber-200 px-2 py-1 text-xs">{flag}</span>)}</div></div>
    <label className="block text-sm">Project ID<input className="mt-1 w-full rounded border p-2" value={projectId} onChange={e => setProjectId(e.target.value)} /></label>
    <label className="block text-sm">Counterparty ID<input className="mt-1 w-full rounded border p-2" value={counterpartyId} onChange={e => setCounterpartyId(e.target.value)} /></label>
    <label className="block text-sm">Alasan koreksi<input className="mt-1 w-full rounded border p-2" value={reason} onChange={e => setReason(e.target.value)} /></label>
    <pre className="max-h-56 overflow-auto rounded bg-slate-950 p-3 text-xs text-slate-100">{JSON.stringify(document.extracted_data, null, 2)}</pre>
    <div className="flex gap-2"><Button onClick={save} isLoading={busy}>Simpan Koreksi</Button><Button variant="secondary" onClick={onApprove} disabled={document.review_flags.length > 0}>Setujui & Buat Transaksi</Button></div>
  </section>;
};
