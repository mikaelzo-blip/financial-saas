import shared from '../../../shared/recording-categories.json';
import type { CostCategory, ExpenseCategory, RecordingCategoryOption } from '../types/api';

interface SharedRecordingCategory {
  value: string;
  kind: 'cost' | 'expense';
  requiresProject: boolean;
}

// UI labels live here (presentation only). The backend never needs them, so they
// stay out of the shared catalog.
const LABELS: Record<string, string> = {
  MAT: 'Beli Barang / Material',
  SUB: 'Jasa / Subkontraktor',
  TRN: 'Bensin & Transport (proyek)',
  EQP: 'Peralatan / Sewa Alat',
  LOG: 'Jasa Angkut / Ekspedisi (proyek)',
  TRAVEL_OFFICE: 'Bensin / Kendaraan (kantor)',
  OFFICE_ADMIN: 'ATK / Operasional Kantor',
  OTHER_OPERATIONAL: 'Lain-lain',
};

const SHARED = shared as SharedRecordingCategory[];

// Derived from the single source of truth so this list can never drift from the
// backend's enforcement rule (see shared/recording-categories.json).
export const RECORDING_CATEGORIES: RecordingCategoryOption[] = SHARED.map((entry) => ({
  value: entry.value,
  label: LABELS[entry.value] ?? entry.value,
  ...(entry.kind === 'cost'
    ? { costCategory: entry.value as CostCategory }
    : { expenseCategory: entry.value as ExpenseCategory }),
  requiresProject: entry.requiresProject,
}));

export const PROJECT_REQUIRED_COST_CATEGORIES: readonly string[] = SHARED.filter(
  (entry) => entry.kind === 'cost' && entry.requiresProject,
).map((entry) => entry.value);
