import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Users, Phone, Mail } from 'lucide-react';
import { masterApi, CounterpartyCreateInput } from '../../api/master';
import { CounterpartyResponse } from '../../types/api';
import { Button } from '../../components/ui/Button';
import { Modal } from '../../components/ui/Modal';
import { DataTable, Column } from '../../components/tables/DataTable';
import { CounterpartyForm } from '../../components/forms/CounterpartyForm';
import { useToast } from '../../components/feedback/Toast';

export const CustomerListPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { success, error } = useToast();
  const [isModalOpen, setIsModalOpen] = useState(false);

  const { data: customers = [], isLoading } = useQuery({
    queryKey: ['customers'],
    queryFn: masterApi.getCustomers,
  });

  const createMutation = useMutation({
    mutationFn: (data: CounterpartyCreateInput) => masterApi.createCounterparty(data),
    onSuccess: (newCust) => {
      queryClient.invalidateQueries({ queryKey: ['customers'] });
      success(`Pelanggan ${newCust.name} berhasil ditambahkan.`);
      setIsModalOpen(false);
    },
    onError: (err: any) => {
      error(err.response?.data?.detail || 'Gagal menambahkan pelanggan.');
    },
  });

  const columns: Column<CounterpartyResponse>[] = [
    {
      key: 'name',
      header: 'Nama Pelanggan',
      sortable: true,
      render: (c) => <span className="font-semibold text-slate-900">{c.name}</span>,
    },
    {
      key: 'phone',
      header: 'Telepon',
      render: (c) =>
        c.phone ? (
          <span className="inline-flex items-center gap-1 text-slate-600">
            <Phone className="h-3.5 w-3.5 text-slate-400" /> {c.phone}
          </span>
        ) : (
          '-'
        ),
    },
    {
      key: 'email',
      header: 'Email',
      render: (c) =>
        c.email ? (
          <span className="inline-flex items-center gap-1 text-slate-600">
            <Mail className="h-3.5 w-3.5 text-slate-400" /> {c.email}
          </span>
        ) : (
          '-'
        ),
    },
    {
      key: 'npwp',
      header: 'NPWP',
      render: (c) => (c.npwp ? <span className="font-mono text-xs text-slate-600">{c.npwp}</span> : '-'),
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">
            Pelanggan (Customers)
          </h2>
          <p className="text-xs text-slate-500 mt-1">
            Daftar pemilik proyek / pemberi tugas konstruksi dan informasi kontak.
          </p>
        </div>
        <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setIsModalOpen(true)}>
          Tambah Pelanggan
        </Button>
      </div>

      <DataTable
        columns={columns}
        data={customers}
        keyExtractor={(c) => c.id}
        isLoading={isLoading}
        searchPlaceholder="Cari nama pelanggan..."
        searchKeys={['name', 'email', 'phone']}
        emptyTitle="Belum ada pelanggan terdaftar"
        emptyDescription="Tambahkan pelanggan pertama Anda untuk membuat proyek dan tagihan termin."
        emptyAction={
          <Button size="sm" leftIcon={<Users className="h-4 w-4" />} onClick={() => setIsModalOpen(true)}>
            Tambah Pelanggan Baru
          </Button>
        }
      />

      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Tambah Pelanggan Baru"
      >
        <CounterpartyForm
          isCustomer={true}
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
