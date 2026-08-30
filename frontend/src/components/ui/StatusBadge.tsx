import React from 'react';
import { Badge, BadgeProps } from './Badge';

export interface StatusBadgeProps {
  status: string;
  type?: 'workflow' | 'project' | 'collection' | 'flag' | 'payable' | 'role';
  size?: 'sm' | 'md';
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  size = 'md',
}) => {
  let label = status;
  let variant: BadgeProps['variant'] = 'neutral';

  switch (status) {
    // Workflow Statuses
    case 'STAGED':
      label = 'Siap Posting';
      variant = 'info';
      break;
    case 'POSTED':
      label = 'Terposting';
      variant = 'success';
      break;
    case 'REVIEW_REQUIRED':
      label = 'Perlu Review';
      variant = 'warning';
      break;
    case 'REVERSED':
      label = 'Dibatalkan';
      variant = 'neutral';
      break;
    case 'REJECTED':
      label = 'Ditolak';
      variant = 'danger';
      break;

    // Project Statuses
    case 'PLANNED':
      label = 'Direncanakan';
      variant = 'info';
      break;
    case 'ACTIVE':
      label = 'Aktif';
      variant = 'success';
      break;
    case 'ON_HOLD':
      label = 'Ditunda';
      variant = 'warning';
      break;
    case 'COMPLETED':
      label = 'Selesai';
      variant = 'purple';
      break;
    case 'CLOSED':
      label = 'Ditutup';
      variant = 'neutral';
      break;
    case 'CANCELLED':
      label = 'Dibatalkan';
      variant = 'danger';
      break;

    // Collection / Billing Statuses
    case 'NOT_DUE':
      label = 'Belum Jatuh Tempo';
      variant = 'info';
      break;
    case 'DUE':
      label = 'Jatuh Tempo Hari Ini';
      variant = 'warning';
      break;
    case 'OVERDUE':
      label = 'Lewat Jatuh Tempo';
      variant = 'danger';
      break;
    case 'COLLECTED':
    case 'PAID':
      label = 'Lunas';
      variant = 'success';
      break;
    case 'PARTIALLY_PAID':
      label = 'Sebagian';
      variant = 'info';
      break;

    // Review Flags
    case 'AMOUNT_MISMATCH':
      label = 'Selisih Nominal';
      variant = 'danger';
      break;
    case 'DUPLICATE_SUSPECTED':
      label = 'Duplikasi Diduga';
      variant = 'warning';
      break;
    case 'PROJECT_UNKNOWN':
      label = 'Proyek Tidak Dikenal';
      variant = 'warning';
      break;
    case 'VENDOR_UNKNOWN':
      label = 'Vendor Tidak Dikenal';
      variant = 'warning';
      break;
    case 'CUSTOMER_UNKNOWN':
      label = 'Pelanggan Tidak Dikenal';
      variant = 'warning';
      break;
    case 'MISSING_DOCUMENT':
      label = 'Bukti Belum Ada';
      variant = 'warning';
      break;
    case 'ACCOUNT_REVIEW':
      label = 'Review Akun';
      variant = 'info';
      break;
    case 'TAX_REVIEW':
      label = 'Review Pajak';
      variant = 'info';
      break;

    // User Roles
    case 'ADMIN':
      label = 'Administrator';
      variant = 'purple';
      break;
    case 'MANAGER':
      label = 'Manajer';
      variant = 'info';
      break;
    case 'OPERATOR':
      label = 'Operator';
      variant = 'neutral';
      break;
    case 'VIEWER':
      label = 'Pengamat';
      variant = 'neutral';
      break;

    default:
      label = status;
      variant = 'neutral';
  }

  return (
    <Badge variant={variant} size={size}>
      {label}
    </Badge>
  );
};
