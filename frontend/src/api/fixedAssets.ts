import { apiClient } from './client';

export type AssetStatus = 'DRAFT' | 'ACTIVE' | 'FULLY_DEPRECIATED' | 'DISPOSED' | 'WRITTEN_OFF';

export interface FixedAssetDepreciationRecord {
  id: string;
  period_date: string;
  depreciation_amount: string;
  accumulated_after: string;
  book_value_after: string;
  transaction_id?: string;
  journal_entry_id?: string;
  created_at: string;
}

export interface FixedAsset {
  id: string;
  organization_id: string;
  asset_code: string;
  asset_name: string;
  asset_category: string;
  purchase_date: string;
  available_for_use_date?: string;
  effective_available_date: string;
  purchase_cost: string;
  salvage_value: string;
  useful_life_months: number;
  depreciation_method: string;
  accumulated_depreciation: string;
  net_book_value: string;
  depreciable_amount: string;
  remaining_depreciable_amount: string;
  monthly_depreciation_rate: string;
  status: AssetStatus;
  vendor_id?: string;
  document_id?: string;
  fiscal_asset_group?: string;
  fiscal_depreciation_method?: string;
  fiscal_useful_life_months?: number;
  created_at: string;
  depreciations: FixedAssetDepreciationRecord[];
}

export interface FixedAssetCreateInput {
  asset_code: string;
  asset_name: string;
  asset_category: string;
  purchase_date: string;
  available_for_use_date?: string;
  purchase_cost: string;
  salvage_value?: string;
  useful_life_months?: number;
  override_reason?: string;
}

export interface DepreciationRunResult {
  asset_id: string;
  asset_code: string;
  asset_name: string;
  period_date: string;
  depreciation_amount: string;
  accumulated_depreciation: string;
  net_book_value: string;
  journal_entry_number?: string;
  status: AssetStatus;
}

export interface BatchDepreciationResponse {
  period_date: string;
  total_assets_processed: number;
  total_depreciation_amount: string;
  results: DepreciationRunResult[];
}

export interface CapitalizationGuidanceResponse {
  amount: string;
  benefit_months: number;
  threshold: string;
  qualifies_as_fixed_asset: boolean;
  recommendation: 'FIXED_ASSET_CANDIDATE' | 'EXPENSE_DEFAULT' | 'REVIEW_REQUIRED';
  notes: string;
}

export const fixedAssetsApi = {
  getAssets: async (params?: { status?: AssetStatus; category?: string }): Promise<FixedAsset[]> => {
    const res = await apiClient.get<FixedAsset[]>('/fixed-assets', { params });
    return res.data;
  },

  getAsset: async (id: string): Promise<FixedAsset> => {
    const res = await apiClient.get<FixedAsset>(`/fixed-assets/${id}`);
    return res.data;
  },

  createAsset: async (data: FixedAssetCreateInput): Promise<FixedAsset> => {
    const res = await apiClient.post<FixedAsset>('/fixed-assets', data);
    return res.data;
  },

  depreciateSingleAsset: async (id: string, periodDate: string): Promise<DepreciationRunResult> => {
    const res = await apiClient.post<DepreciationRunResult>(`/fixed-assets/${id}/depreciate`, {
      period_date: periodDate,
    });
    return res.data;
  },

  depreciateBatch: async (periodDate: string): Promise<BatchDepreciationResponse> => {
    const res = await apiClient.post<BatchDepreciationResponse>('/fixed-assets/depreciate-batch', {
      period_date: periodDate,
    });
    return res.data;
  },

  disposeAsset: async (id: string): Promise<FixedAsset> => {
    const res = await apiClient.post<FixedAsset>(`/fixed-assets/${id}/dispose`);
    return res.data;
  },

  getCapitalizationGuidance: async (
    amount: number,
    benefitMonths: number = 12
  ): Promise<CapitalizationGuidanceResponse> => {
    const res = await apiClient.get<CapitalizationGuidanceResponse>(
      '/fixed-assets/guidance/capitalization',
      {
        params: { amount, benefit_months: benefitMonths },
      }
    );
    return res.data;
  },
};
