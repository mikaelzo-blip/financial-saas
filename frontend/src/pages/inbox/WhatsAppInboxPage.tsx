import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import {
  MessageSquare,
  RefreshCw,
  Clock,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  Phone,
  Paperclip,
  Eye,
} from 'lucide-react';
import { inboxApi } from '../../api/inbox';
import { InboxMessage, InboxMessageStatus } from '../../types/api';
import { formatDate } from '../../utils/formatters';
import { Button } from '../../components/ui/Button';
import { Card } from '../../components/ui/Card';
import { SkeletonLoader } from '../../components/feedback/SkeletonLoader';
import { useToast } from '../../components/feedback/Toast';

type FilterTab = 'ALL' | 'RECEIVED' | 'SYNCED' | 'PROCESSED' | 'FAILED';

export const WhatsAppInboxPage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { success, error } = useToast();
  const [selectedTab, setSelectedTab] = useState<FilterTab>('ALL');

  const { data: messages, isLoading, isFetching } = useQuery({
    queryKey: ['inbox-messages', selectedTab],
    queryFn: () => {
      const filter = selectedTab === 'ALL' ? undefined : (selectedTab as InboxMessageStatus);
      return inboxApi.listMessages(filter);
    },
  });

  const syncMutation = useMutation({
    mutationFn: () => inboxApi.syncBacklog(),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['inbox-messages'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard-financial-summary'] });
      success(`Berhasil menarik ${data.length} pesan backlog dari Remote Capture.`);
    },
    onError: (err: any) => {
      error(err.response?.data?.detail || 'Gagal melakukan sinkronisasi backlog.');
    },
  });

  const getStatusBadge = (status: InboxMessageStatus) => {
    switch (status) {
      case 'RECEIVED':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <Clock className="w-3 h-3 mr-1" />
            Belum Sinkron
          </span>
        );
      case 'SYNCED':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
            <RefreshCw className="w-3 h-3 mr-1" />
            Menunggu Analisis
          </span>
        );
      case 'PROCESSED':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3 h-3 mr-1" />
            Selesai Diproses
          </span>
        );
      case 'FAILED':
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-200">
            <AlertCircle className="w-3 h-3 mr-1" />
            Gagal
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-600 text-white">
              <MessageSquare className="h-4 w-4" />
            </div>
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">
              WhatsApp Durable Inbox
            </h2>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Capture bukti transaksi offline via WhatsApp. Saat PC menyala, sinkronkan backlog untuk dianalisis Hermes.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => navigate('/review-queue')}
            leftIcon={<Eye className="w-4 h-4" />}
          >
            Buka Antrean Review
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => syncMutation.mutate()}
            isLoading={syncMutation.isPending || isFetching}
            leftIcon={<RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />}
          >
            Tarik & Sinkronkan Backlog
          </Button>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex border-b border-slate-200 gap-6">
        {(
          [
            { key: 'ALL', label: 'Semua Pesan' },
            { key: 'RECEIVED', label: 'Belum Sinkron' },
            { key: 'SYNCED', label: 'Menunggu Analisis' },
            { key: 'PROCESSED', label: 'Selesai' },
            { key: 'FAILED', label: 'Gagal' },
          ] as const
        ).map((tab) => (
          <button
            key={tab.key}
            onClick={() => setSelectedTab(tab.key)}
            className={`pb-3 text-xs font-semibold tracking-wide transition-colors cursor-pointer ${
              selectedTab === tab.key
                ? 'border-b-2 border-emerald-600 text-emerald-700 font-bold'
                : 'text-slate-500 hover:text-slate-900'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Message List */}
      {isLoading ? (
        <div className="space-y-3">
          <SkeletonLoader count={4} className="h-24 w-full" />
        </div>
      ) : !messages || messages.length === 0 ? (
        <Card className="p-12 text-center">
          <MessageSquare className="w-12 h-12 text-slate-300 mx-auto mb-3" />
          <p className="text-sm font-semibold text-slate-700">Tidak ada pesan WhatsApp</p>
          <p className="text-xs text-slate-500 mt-1">
            Belum ada bukti transaksi yang diterima untuk filter status ini.
          </p>
        </Card>
      ) : (
        <div className="space-y-3">
          {messages.map((msg: InboxMessage) => (
            <Card key={msg.id} className="p-4 hover:border-slate-300 transition-colors">
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                <div className="space-y-2 flex-1">
                  <div className="flex items-center gap-3">
                    {getStatusBadge(msg.status)}
                    <span className="text-xs font-medium text-slate-500 flex items-center gap-1">
                      <Phone className="w-3 h-3 text-slate-400" />
                      {msg.sender_name ? `${msg.sender_name} (${msg.sender_phone})` : msg.sender_phone}
                    </span>
                    <span className="text-[11px] text-slate-400">
                      Diterima: {formatDate(msg.received_at)}
                    </span>
                  </div>

                  <p className="text-sm font-medium text-slate-800">
                    {msg.caption || <span className="italic text-slate-400">Tanpa keterangan / caption</span>}
                  </p>

                  {/* Attachments */}
                  {msg.attachments && msg.attachments.length > 0 && (
                    <div className="flex flex-wrap gap-2 pt-1">
                      {msg.attachments.map((att) => (
                        <div
                          key={att.id}
                          className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-100 rounded text-xs text-slate-700 border border-slate-200"
                        >
                          <Paperclip className="w-3.5 h-3.5 text-slate-500" />
                          <span className="truncate max-w-xs">{att.file_name}</span>
                          <span className="text-[10px] text-slate-400">
                            ({(att.size_bytes / 1024).toFixed(0)} KB)
                          </span>
                          {att.document_id && (
                            <button
                              onClick={() => navigate(`/documents`)}
                              className="ml-1 text-blue-600 hover:text-blue-800"
                              title="Buka dokumen"
                            >
                              <ExternalLink className="w-3 h-3" />
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {msg.error_message && (
                    <p className="text-xs text-rose-600 bg-rose-50 px-2.5 py-1 rounded border border-rose-200 inline-block">
                      Error: {msg.error_message}
                    </p>
                  )}
                </div>

                <div className="flex sm:flex-col items-end gap-2 shrink-0">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => navigate('/review-queue')}
                  >
                    Periksa di Review
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};
