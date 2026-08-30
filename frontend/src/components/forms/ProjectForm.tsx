import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { masterApi } from '../../api/master';
import { ProjectCreateInput } from '../../api/projects';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { Select } from '../ui/Select';

export interface ProjectFormProps {
  initialValues?: Partial<ProjectCreateInput>;
  onSubmit: (data: ProjectCreateInput) => Promise<void>;
  isLoading?: boolean;
  onCancel?: () => void;
}

export const ProjectForm: React.FC<ProjectFormProps> = ({
  initialValues,
  onSubmit,
  isLoading = false,
  onCancel,
}) => {
  const [projectName, setProjectName] = useState(initialValues?.project_name || '');
  const [customerId, setCustomerId] = useState(initialValues?.customer_id || '');
  const [poSpkNo, setPoSpkNo] = useState(initialValues?.po_spk_no || '');
  const [poSpkDate, setPoSpkDate] = useState(initialValues?.po_spk_date || '');
  const [contractValue, setContractValue] = useState(
    initialValues?.original_contract_value?.toString() || ''
  );
  const [startDate, setStartDate] = useState(
    initialValues?.start_date || new Date().toISOString().split('T')[0]
  );
  const [targetEndDate, setTargetEndDate] = useState(initialValues?.target_end_date || '');
  const [errors, setErrors] = useState<Record<string, string>>({});

  const { data: customers = [] } = useQuery({
    queryKey: ['customers'],
    queryFn: masterApi.getCustomers,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const newErrors: Record<string, string> = {};

    if (!projectName.trim()) newErrors.projectName = 'Nama proyek wajib diisi';
    if (!customerId) newErrors.customerId = 'Pilih pelanggan/customer';
    if (!contractValue || isNaN(Number(contractValue)) || Number(contractValue) <= 0) {
      newErrors.contractValue = 'Nilai kontrak harus berupa angka positif';
    }
    if (!startDate) newErrors.startDate = 'Tanggal mulai proyek wajib diisi';

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setErrors({});
    await onSubmit({
      project_name: projectName,
      customer_id: customerId,
      po_spk_no: poSpkNo || undefined,
      po_spk_date: poSpkDate || undefined,
      original_contract_value: Number(contractValue),
      start_date: startDate,
      target_end_date: targetEndDate || undefined,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="md:col-span-2">
          <Input
            label="Nama Proyek *"
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            placeholder="Contoh: Pembangunan Gedung Olahraga Kampus"
            error={errors.projectName}
            required
          />
        </div>

        <div>
          <Select
            label="Pelanggan (Customer / Pemberi Tugas) *"
            value={customerId}
            onChange={(e) => setCustomerId(e.target.value)}
            error={errors.customerId}
            required
          >
            <option value="">-- Pilih Pelanggan --</option>
            {customers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </Select>
        </div>

        <div>
          <Input
            label="Nilai Kontrak Awal (Rp) *"
            type="number"
            value={contractValue}
            onChange={(e) => setContractValue(e.target.value)}
            placeholder="Contoh: 500000000"
            error={errors.contractValue}
            required
          />
        </div>

        <div>
          <Input
            label="Nomor PO / SPK / Kontrak"
            value={poSpkNo}
            onChange={(e) => setPoSpkNo(e.target.value)}
            placeholder="Contoh: SPK/2026/PROJ-01"
          />
        </div>

        <div>
          <Input
            label="Tanggal PO / SPK"
            type="date"
            value={poSpkDate}
            onChange={(e) => setPoSpkDate(e.target.value)}
          />
        </div>

        <div>
          <Input
            label="Tanggal Mulai Proyek *"
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            error={errors.startDate}
            required
          />
        </div>

        <div>
          <Input
            label="Target Selesai (Opsional)"
            type="date"
            value={targetEndDate}
            onChange={(e) => setTargetEndDate(e.target.value)}
          />
        </div>
      </div>

      <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-200">
        {onCancel && (
          <Button type="button" variant="outline" onClick={onCancel} disabled={isLoading}>
            Batal
          </Button>
        )}
        <Button type="submit" isLoading={isLoading}>
          Simpan Proyek
        </Button>
      </div>
    </form>
  );
};
