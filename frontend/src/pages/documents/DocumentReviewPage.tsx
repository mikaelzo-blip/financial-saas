import React from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { documentsApi } from '../../api/documents';
import { DocumentReviewForm } from '../../components/documents/DocumentReviewForm';

export const DocumentReviewPage: React.FC = () => {
  const { id = '' } = useParams(); const navigate = useNavigate(); const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ['document', id], queryFn: () => documentsApi.get(id), enabled: !!id });
  const content = useQuery({ queryKey: ['document-content', id], queryFn: () => documentsApi.content(id), enabled: !!id });
  const correction = useMutation({ mutationFn: ({changes, reason}: {changes: Record<string, unknown>; reason: string}) => documentsApi.correct(id, changes, reason), onSuccess: data => queryClient.setQueryData(['document', id], data) });
  const approval = useMutation({ mutationFn: () => documentsApi.approve(id), onSuccess: () => navigate('/transactions') });
  const rejection = useMutation({ mutationFn: (reason: string) => documentsApi.reject(id, reason), onSuccess: data => queryClient.setQueryData(['document', id], data) });
  if (query.isLoading) return <div role="status" className="p-8">Memuat dokumen…</div>;
  if (!query.data) return <div role="alert" className="p-8">Dokumen tidak ditemukan.</div>;
  const document = query.data;
  const contentUrl = content.data ? URL.createObjectURL(content.data) : '';
  return <div className="grid gap-6 lg:grid-cols-2">
    <section className="min-h-[70vh] rounded-xl border bg-slate-100 p-3" aria-label="Dokumen sumber immutable">
      {!contentUrl ? <div role="status" className="p-8">Memuat bukti sumber…</div> : document.mime_type.startsWith('image/') ? <img className="mx-auto max-h-[68vh]" src={contentUrl} alt={document.file_name} /> : <iframe className="h-[68vh] w-full" src={contentUrl} title={document.file_name} />}
    </section>
    <DocumentReviewForm document={document} onSave={(changes, reason) => correction.mutateAsync({changes, reason}).then(() => undefined)} onApprove={() => approval.mutateAsync().then(() => undefined)} onReject={(reason) => rejection.mutateAsync(reason).then(() => undefined)} />
  </div>;
};
