export interface SourceMoney {
  amount: string;
  currency_code: string;
  evidence: string;
}

export interface TransferDetails {
  foreign?: SourceMoney | null;
  principal?: SourceMoney | null;
  fee?: SourceMoney | null;
  debit?: SourceMoney | null;
  purpose?: string | null;
  execution_status?: string;
  execution_evidence?: string | null;
}

export const transferExecutionLabels: Record<string, string> = {
  UNKNOWN: 'Belum terbukti terlaksana',
  REQUESTED: 'Aplikasi / instruksi, belum bukti pelaksanaan',
  EXECUTED: 'Terlaksana menurut bukti sumber',
};

export function sameDecimalValue(left: unknown, right: unknown): boolean {
  const normalize = (value: unknown) => {
    const text = String(value ?? '');
    if (!/^\d+(\.\d+)?$/.test(text)) return null;
    return text.replace(/^0+(?=\d)/, '').replace(/(\.\d*?)0+$/, '$1').replace(/\.$/, '');
  };
  const first = normalize(left);
  return first !== null && first === normalize(right);
}
