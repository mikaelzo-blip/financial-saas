import type { Insight } from '../../api/insights';
import { FactVsInterpretationBadge } from './FactVsInterpretationBadge';

export function InsightContent({ insight }: { insight: Insight }) {
  return <div className="space-y-3">
    <h3 className="font-semibold">{insight.headline}</h3>
    <p className="text-xs text-slate-500">{insight.period_label} · As of {insight.data_as_of} · Keyakinan {insight.confidence_score}</p>
    <p className="text-xs">{insight.provider_metadata.provider === 'DETERMINISTIC_FALLBACK' ? 'Fallback deterministik' : 'Mock AI — offline'}{insight.provider_metadata.cached ? ' · Cache' : ''}</p>
    <FactVsInterpretationBadge facts />
    <dl className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm">
      {Object.entries(insight.factual_metrics).map(([key, value]) => <div key={key}>
        <dt className="text-slate-500">{key.replaceAll('_', ' ')}</dt>
        {/* Never coerce exact Decimal strings through JavaScript Number. */}
        <dd className="font-mono break-all">{value ?? 'Data tidak tersedia'}</dd>
      </div>)}
    </dl>
    <FactVsInterpretationBadge />
    <p className="text-sm">{insight.analytical_narrative}</p>
    <ul className="list-disc pl-5 text-sm">{insight.actionable_recommendations.map(item => <li key={item}>{item}</li>)}</ul>
    {insight.anomalies_detected.map(item => <p key={item.code + item.metric_reference} className="text-sm text-amber-800">{item.severity}: {item.description}</p>)}
    <details className="text-xs"><summary>Sumber dan bukti metrik</summary>
      <ul>{insight.source_references.map(source => <li key={source}>{source}</li>)}</ul>
      <ul>{Object.entries(insight.metric_sources).map(([key, source]) => <li key={key}>{key}: {source}</li>)}</ul>
      <p>Dibuat: {insight.generated_at}</p>
    </details>
    <p className="text-xs text-slate-500">Advisory saja. Tidak membuat jurnal, menyetujui, atau memposting transaksi.</p>
  </div>;
}
