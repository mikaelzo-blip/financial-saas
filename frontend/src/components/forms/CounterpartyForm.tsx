import React, { useState } from 'react';
import { CounterpartyCreateInput } from '../../api/master';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';

export interface CounterpartyFormProps {
  isCustomer: boolean;
  onSubmit: (data: CounterpartyCreateInput) => Promise<void>;
  isLoading?: boolean;
  onCancel?: () => void;
}

export const CounterpartyForm: React.FC<CounterpartyFormProps> = ({
  isCustomer,
  onSubmit,
  isLoading = false,
  onCancel,
}) => {
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [address, setAddress] = useState('');
  const [npwp, setNpwp] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Nama wajib diisi');
      return;
    }
    setError(null);
    await onSubmit({
      name,
      is_customer: isCustomer,
      is_vendor: !isCustomer,
      phone: phone || undefined,
      email: email || undefined,
      address: address || undefined,
      npwp: npwp || undefined,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <Input
        label={`Nama ${isCustomer ? 'Pelanggan / Customer' : 'Vendor / Subkontraktor'} *`}
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder={isCustomer ? 'Contoh: PT Properti Nusantara' : 'Contoh: PT Supplier Baja Mandiri'}
        error={error || undefined}
        required
      />

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="Nomor Telepon"
          value={phone}
          onChange={(e) => setPhone(e.target.value)}
          placeholder="08123456789"
        />
        <Input
          label="Alamat Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="kontak@perusahaan.co.id"
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Input
          label="Nomor NPWP"
          value={npwp}
          onChange={(e) => setNpwp(e.target.value)}
          placeholder="01.234.567.8-901.000"
        />
        <Input
          label="Alamat Kantor"
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          placeholder="Jl. Sudirman No. 45, Jakarta"
        />
      </div>

      <div className="flex justify-end gap-3 pt-4 border-t border-slate-100">
        {onCancel && (
          <Button type="button" variant="outline" size="sm" onClick={onCancel} disabled={isLoading}>
            Batal
          </Button>
        )}
        <Button type="submit" size="sm" isLoading={isLoading}>
          Simpan {isCustomer ? 'Pelanggan' : 'Vendor'}
        </Button>
      </div>
    </form>
  );
};
