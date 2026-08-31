export function FactVsInterpretationBadge({ facts = false }: { facts?: boolean }) {
  return <span className="inline-block rounded bg-slate-100 px-2 py-1 text-xs font-semibold">{facts ? 'Fakta laporan' : 'Interpretasi advisory'}</span>;
}
