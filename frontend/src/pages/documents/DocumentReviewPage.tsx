import React from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { documentsApi } from '../../api/documents';
import { masterApi } from '../../api/master';
import { projectsApi } from '../../api/projects';
import { DocumentReviewForm } from '../../components/documents/DocumentReviewForm';
import { useToast } from '../../components/feedback/Toast';
import {
  formatDocumentActionError,
  getDocumentReviewLookupRequirements,
  getDocumentReviewTransactionType,
  isPaymentAccountRequired,
} from '../../utils/documentReview';

export const DocumentReviewPage: React.FC = () => {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();
  const queryClient = useQueryClient();

  const query = useQuery({ queryKey: ['document', id], queryFn: () => documentsApi.get(id), enabled: !!id });
  const content = useQuery({ queryKey: ['document-content', id], queryFn: () => documentsApi.content(id), enabled: !!id });
  const projects = useQuery({ queryKey: ['document-review-projects'], queryFn: () => projectsApi.list() });
  const customers = useQuery({ queryKey: ['document-review-customers'], queryFn: masterApi.getCustomers });
  const vendors = useQuery({ queryKey: ['document-review-vendors'], queryFn: masterApi.getVendors });
  const paymentAccounts = useQuery({ queryKey: ['document-review-payment-accounts'], queryFn: masterApi.getPaymentAccounts });

  const correction = useMutation({
    mutationFn: ({ changes, reason }: { changes: Record<string, unknown>; reason: string }) =>
      documentsApi.correct(id, changes, reason),
    onSuccess: (data) => queryClient.setQueryData(['document', id], data),
  });

  const approval = useMutation({
    mutationFn: () => documentsApi.approve(id),
    onSuccess: (data) => queryClient.setQueryData(['document', id], data),
  });

  const rejection = useMutation({
    mutationFn: (reason: string) => documentsApi.reject(id, reason),
    onSuccess: (data) => queryClient.setQueryData(['document', id], data),
  });

  const actionError = [correction, approval, rejection].find((mutation) => mutation.isError)?.error;
  const actionErrorMessage = actionError ? formatDocumentActionError(actionError) : undefined;

  const getReturnPath = (): string => {
    const stateReturnTo = (location.state as { returnTo?: string } | null)?.returnTo;
    if (stateReturnTo && typeof stateReturnTo === 'string' && stateReturnTo.startsWith('/documents')) {
      return stateReturnTo;
    }
    if (location.search) {
      return `/documents${location.search}`;
    }
    return '/documents';
  };

  if (query.isLoading) return <div role="status" className="p-8">Memuat dokumen…</div>;
  if (!query.data) return <div role="alert" className="p-8">Dokumen tidak ditemukan.</div>;

  const document = query.data;
  const contentUrl = content.data ? URL.createObjectURL(content.data) : '';
  const transactionType = getDocumentReviewTransactionType(document);
  const lookupRequirements = getDocumentReviewLookupRequirements(document);
  const requiresPaymentAccount = isPaymentAccountRequired(transactionType, document.document_type);

  const activeProjects = (projects.data ?? []).filter(({ project_status }) =>
    ['PLANNED', 'ACTIVE', 'ON_HOLD'].includes(project_status),
  );
  const activePaymentAccounts = (paymentAccounts.data ?? []).filter((account) => account.is_active);

  const counterparties = lookupRequirements.customer && !lookupRequirements.vendor
    ? (customers.data ?? [])
    : lookupRequirements.vendor && !lookupRequirements.customer
      ? (vendors.data ?? [])
      : [...(vendors.data ?? []), ...(customers.data ?? [])].filter(
          (counterparty, index, all) => all.findIndex(({ id: otherId }) => otherId === counterparty.id) === index,
        );

  const counterpartyLookupLoading = lookupRequirements.customer && !lookupRequirements.vendor
    ? customers.isLoading
    : lookupRequirements.vendor && !lookupRequirements.customer
      ? vendors.isLoading
      : customers.isLoading || vendors.isLoading;

  const counterpartyLookupError = lookupRequirements.customer && !lookupRequirements.vendor
    ? customers.isError
    : lookupRequirements.vendor && !lookupRequirements.customer
      ? vendors.isError
      : customers.isError || vendors.isError;

  const paymentAccountLookupLoading = requiresPaymentAccount && paymentAccounts.isLoading;
  const paymentAccountLookupError = requiresPaymentAccount && paymentAccounts.isError
    ? 'Daftar rekening pembayaran tidak dapat dimuat.'
    : undefined;

  const approvalLookupLoading =
    (lookupRequirements.project && projects.isLoading) ||
    (lookupRequirements.customer && customers.isLoading) ||
    (lookupRequirements.vendor && vendors.isLoading) ||
    paymentAccountLookupLoading;

  let approvalLookupError: string | undefined;
  if (lookupRequirements.project && projects.isError) {
    approvalLookupError = 'Daftar proyek yang diperlukan untuk persetujuan tidak dapat dimuat.';
  } else if (lookupRequirements.customer && customers.isError) {
    approvalLookupError = 'Daftar pelanggan yang diperlukan untuk persetujuan tidak dapat dimuat.';
  } else if (lookupRequirements.vendor && vendors.isError) {
    approvalLookupError = 'Daftar vendor yang diperlukan untuk persetujuan tidak dapat dimuat.';
  } else if (requiresPaymentAccount && paymentAccounts.isError) {
    approvalLookupError = 'Daftar rekening pembayaran yang diperlukan untuk persetujuan tidak dapat dimuat.';
  }

  const handleSave = async (changes: Record<string, unknown>, reason: string, options?: { silent?: boolean }) => {
    const updated = await correction.mutateAsync({ changes, reason });
    if (!options?.silent) {
      toast.success('Koreksi berhasil disimpan');
      navigate(getReturnPath());
    }
    return updated;
  };

  const handleApprove = async () => {
    await approval.mutateAsync();
    toast.success('Dokumen berhasil disetujui');
    navigate(getReturnPath());
  };

  const handleReject = async (reason: string) => {
    await rejection.mutateAsync(reason);
    toast.info('Kandidat dokumen ditolak');
    navigate(getReturnPath());
  };

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="min-h-[70vh] rounded-xl border bg-slate-100 p-3 flex flex-col justify-between" aria-label="Dokumen sumber immutable">
        <div className="flex-1 flex items-center justify-center">
          {!contentUrl ? (
            <div role="status" className="p-8">Memuat bukti sumber…</div>
          ) : document.mime_type.startsWith('image/') ? (
            <img className="mx-auto max-h-[68vh]" src={contentUrl} alt={document.file_name} />
          ) : (
            <iframe className="h-[68vh] w-full" src={contentUrl} title={document.file_name} />
          )}
        </div>
        {contentUrl && (
          <div className="mt-2 flex items-center justify-between border-t border-slate-200 pt-2 px-1 text-xs text-slate-600">
            <span className="truncate max-w-[200px]">{document.file_name}</span>
            <a
              href={contentUrl}
              target="_blank"
              rel="noopener noreferrer"
              download={document.file_name}
              className="text-blue-600 hover:underline font-medium ml-2"
            >
              Buka / Unduh Dokumen Asli
            </a>
          </div>
        )}
      </section>
      <DocumentReviewForm
        document={document}
        projects={activeProjects}
        counterparties={counterparties}
        paymentAccounts={activePaymentAccounts}
        projectLookupLoading={projects.isLoading}
        counterpartyLookupLoading={counterpartyLookupLoading}
        paymentAccountLookupLoading={paymentAccountLookupLoading}
        projectLookupError={projects.isError ? 'Daftar proyek tidak dapat dimuat.' : undefined}
        counterpartyLookupError={counterpartyLookupError ? 'Daftar vendor atau pelanggan tidak dapat dimuat.' : undefined}
        paymentAccountLookupError={paymentAccountLookupError}
        approvalLookupLoading={approvalLookupLoading}
        approvalLookupError={approvalLookupError}
        actionError={actionErrorMessage}
        onSave={(changes, reason, options) => handleSave(changes, reason, options).then(() => undefined)}
        onApprove={handleApprove}
        onReject={handleReject}
      />
    </div>
  );
};
