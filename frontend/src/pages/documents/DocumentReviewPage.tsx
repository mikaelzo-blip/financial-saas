import React from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { documentsApi } from '../../api/documents';
import { masterApi } from '../../api/master';
import { projectsApi } from '../../api/projects';
import { DocumentReviewForm } from '../../components/documents/DocumentReviewForm';
import {
  PROJECT_REQUIRED_TRANSACTION_TYPES,
  getDocumentReviewLookupRequirements,
  getDocumentReviewTransactionType,
} from '../../utils/documentReview';

export const DocumentReviewPage: React.FC = () => {
  const { id = '' } = useParams(); const navigate = useNavigate(); const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ['document', id], queryFn: () => documentsApi.get(id), enabled: !!id });
  const content = useQuery({ queryKey: ['document-content', id], queryFn: () => documentsApi.content(id), enabled: !!id });
  const projects = useQuery({ queryKey: ['document-review-projects'], queryFn: () => projectsApi.list() });
  const customers = useQuery({ queryKey: ['document-review-customers'], queryFn: masterApi.getCustomers });
  const vendors = useQuery({ queryKey: ['document-review-vendors'], queryFn: masterApi.getVendors });
  const correction = useMutation({ mutationFn: ({changes, reason}: {changes: Record<string, unknown>; reason: string}) => documentsApi.correct(id, changes, reason), onSuccess: data => queryClient.setQueryData(['document', id], data) });
  const approval = useMutation({ mutationFn: () => documentsApi.approve(id), onSuccess: () => navigate('/transactions') });
  const rejection = useMutation({ mutationFn: (reason: string) => documentsApi.reject(id, reason), onSuccess: data => queryClient.setQueryData(['document', id], data) });
  if (query.isLoading) return <div role="status" className="p-8">Memuat dokumen…</div>;
  if (!query.data) return <div role="alert" className="p-8">Dokumen tidak ditemukan.</div>;
  const document = query.data;
  const contentUrl = content.data ? URL.createObjectURL(content.data) : '';
  const transactionType = getDocumentReviewTransactionType(document);
  const lookupRequirements = getDocumentReviewLookupRequirements(document);
  const activeProjects = (projects.data ?? []).filter(({ project_status }) =>
    ['PLANNED', 'ACTIVE', 'ON_HOLD'].includes(project_status),
  );
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
  const approvalLookupLoading =
    (lookupRequirements.project && projects.isLoading) ||
    (lookupRequirements.customer && customers.isLoading) ||
    (lookupRequirements.vendor && vendors.isLoading);
  const projectId = String(document.candidate_transaction.project_id ?? '');
  const counterpartyId = String(document.candidate_transaction.counterparty_id ?? '');
  let approvalLookupError: string | undefined;
  if (lookupRequirements.project && projects.isError) {
    approvalLookupError = 'Daftar proyek yang diperlukan untuk persetujuan tidak dapat dimuat.';
  } else if (
    transactionType &&
    PROJECT_REQUIRED_TRANSACTION_TYPES.has(transactionType) &&
    !projectId
  ) {
    approvalLookupError = 'Proyek wajib dipilih sebelum dokumen dapat disetujui.';
  } else if (
    projectId &&
    !projects.isLoading &&
    !projects.isError &&
    !activeProjects.some(({ id: existingId }) => existingId === projectId)
  ) {
    approvalLookupError = 'Proyek pada kandidat tidak aktif atau tidak tersedia.';
  } else if (lookupRequirements.customer && customers.isError) {
    approvalLookupError = 'Daftar pelanggan yang diperlukan untuk persetujuan tidak dapat dimuat.';
  } else if (lookupRequirements.vendor && vendors.isError) {
    approvalLookupError = 'Daftar vendor yang diperlukan untuk persetujuan tidak dapat dimuat.';
  } else if (
    lookupRequirements.customer &&
    !counterpartyId
  ) {
    approvalLookupError = 'Pelanggan wajib dipilih sebelum dokumen dapat disetujui.';
  } else if (
    lookupRequirements.vendor &&
    !counterpartyId
  ) {
    approvalLookupError = 'Vendor wajib dipilih sebelum dokumen dapat disetujui.';
  } else if (
    counterpartyId &&
    !counterpartyLookupLoading &&
    !counterpartyLookupError &&
    !counterparties.some(({ id: existingId }) => existingId === counterpartyId)
  ) {
    approvalLookupError = 'Vendor atau pelanggan pada kandidat tidak aktif atau tidak tersedia.';
  }
  return <div className="grid gap-6 lg:grid-cols-2">
    <section className="min-h-[70vh] rounded-xl border bg-slate-100 p-3" aria-label="Dokumen sumber immutable">
      {!contentUrl ? <div role="status" className="p-8">Memuat bukti sumber…</div> : document.mime_type.startsWith('image/') ? <img className="mx-auto max-h-[68vh]" src={contentUrl} alt={document.file_name} /> : <iframe className="h-[68vh] w-full" src={contentUrl} title={document.file_name} />}
    </section>
    <DocumentReviewForm
      document={document}
      projects={activeProjects}
      counterparties={counterparties}
      projectLookupLoading={projects.isLoading}
      counterpartyLookupLoading={counterpartyLookupLoading}
      projectLookupError={projects.isError ? 'Daftar proyek tidak dapat dimuat.' : undefined}
      counterpartyLookupError={counterpartyLookupError ? 'Daftar vendor atau pelanggan tidak dapat dimuat.' : undefined}
      approvalLookupLoading={approvalLookupLoading}
      approvalLookupError={approvalLookupError}
      onSave={(changes, reason) => correction.mutateAsync({changes, reason}).then(() => undefined)}
      onApprove={() => approval.mutateAsync().then(() => undefined)}
      onReject={(reason) => rejection.mutateAsync(reason).then(() => undefined)}
    />
  </div>;
};
