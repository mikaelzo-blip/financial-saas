import { FormEvent, useState } from 'react';
import { insightsApi } from '../../api/insights';

export function FinancialQABox() {
  const [question, setQuestion] = useState(''); const [answer, setAnswer] = useState(''); const [session, setSession] = useState<string>(); const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const submit = async (event: FormEvent) => { event.preventDefault(); if (!question.trim()) return; setBusy(true); setError(''); try { const result = await insightsApi.ask(question, session); setSession(result.session_id); setAnswer(result.answer_text); } catch { setError('Jawaban tidak tersedia.'); } finally { setBusy(false); } };
  return <section aria-label="Tanya jawab keuangan" className="rounded-lg border bg-white p-4 space-y-3"><h2 className="font-semibold">Tanya jawab keuangan</h2><form onSubmit={submit} className="flex gap-2"><input aria-label="Pertanyaan keuangan" value={question} onChange={event => setQuestion(event.target.value)} maxLength={1000} className="flex-1 border rounded p-2" placeholder="Contoh: Piutang mana yang paling mendesak ditagih?" /><button disabled={busy} type="submit">{busy ? 'Memuat…' : 'Tanya'}</button></form>{error && <p role="alert">{error}</p>}{answer && <div className="text-sm" role="status">{answer}</div>}<p className="text-xs text-slate-500">Pertanyaan di luar data keuangan akan ditolak.</p></section>;
}
