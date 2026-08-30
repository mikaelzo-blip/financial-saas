import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Truck, Phone, Mail } from 'lucide-react';
import { masterApi, CounterpartyCreateInput } from '../../api/master';
import { CounterpartyResponse } from '../../types/api';
import { Button } from '../../components/ui/Button';
import { Modal } from '../../components/ui/Modal';
import { DataTable, Column } from '../../components/tables/DataTable';
import { CounterpartyForm } from '../../components/forms/CounterpartyForm';
import { useToast } from '../../components/feedback/Toast';

export const VendorListPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { success, error } = useToast();
  const [isModalOpen, setIsModalOpen] = useState(false);

  const { data: vendors = [], isLoading } = useQuery({
    queryKey: ['vendors'],
    queryFn: masterApi.getVendors,
  });

  const createMutation = useMutation({
    mutationFn: (data: CounterpartyCreateInput) => masterApi.createCounterparty(data),
    onSuccess: (newVend) => {
      queryClient.invalidateQueries({ queryKey: ['vendors'] });
      success(`Vendor ${newVend.name} berhasil ditambahkan.`);
      setIsModalOpen(false);
    },
    onError: (err: any) => {
      error(err.response?.data?.detail || 'Gagal menambahkan vendor.');
    },
  });

  const columns: Column<CounterpartyResponse>[] = [
    {
      key: 'name',
      header: 'Nama Vendor / Subkon',
      sortable: true,
      render: (v) => <span className="font-semibold text-slate-900">{v.name}</span>,
    },
    {
      key: 'phone',
      header: 'Telepon',
      render: (v) =>
        v.phone ? (
          <span className="inline-flex items-center gap-1 text-slate-600">
            <Phone className="h-3.5 w-3.5 text-slate-400" /> {v.phone}
          </span>
        ) : (
          '-'
        ),
    },
    {
      key: 'email',
      header: 'Email',
      render: (v) =>
        v.email ? (
          <span className="inline-flex items-center gap-1 text-slate-600">
            <Mail className="h-3.5 w-3.5 text-slate-400" /> {v.email}
          </span>
        ) : (
          '-'
        ),
    },
    {
      key: 'npwp',
      header: 'NPWP',
      render: (v) => (v.npwp ? <span className="font-mono text-xs text-slate-600">{v.npwp}</span> : '-'),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">
            Vendor & Subkontraktor
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Daftar pemasok material, mandor, dan subkontraktor spesialis.
          </p>
        </div>
        <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setIsModalOpen(true)}>
          Tambah Vendor
        </Button>
      </div>

      <DataTable
        columns={columns}
        data={vendors}
        keyExtractor={(v) => v.id}
        isLoading={isLoading}
        searchPlaceholder="Cari nama vendor atau subkon..."
        searchKeys={['name', 'email', 'phone']}
        emptyTitle="Belum ada vendor terdaftar"
        emptyDescription="Daftarkan vendor atau subkontraktor untuk mencatat tagihan dan kasbon."
        emptyAction={
          <Button size="sm" leftIcon={<Truck className="h-4 w-4" />} onClick={() => setIsModalOpen(true)}>
            Tambah Vendor Baru
          </Button>
        }
      />

      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Tambah Vendor Baru"
      >
        <CounterpartyForm
          isCustomer={false}
          onSubmit={async (data) => {
            await createMutation.mutateAsync(data);
          }}
          isLoading={createMutation.isPending}
          onCancel={() => setIsModalOpen(false)}
        />
      </Modal>
    </div>
  );
};
