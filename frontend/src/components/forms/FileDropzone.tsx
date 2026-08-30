import React, { useState, useRef } from 'react';
import { UploadCloud, CheckCircle2, AlertCircle } from 'lucide-react';
import { documentsApi } from '../../api/documents';
import { DocumentResponse } from '../../types/api';
import { DuplicateDocumentModal } from '../documents/DuplicateDocumentModal';

export interface FileDropzoneProps {
  onUploaded: (doc: DocumentResponse) => void;
  documentType?: string;
}

export const FileDropzone: React.FC<FileDropzoneProps> = ({
  onUploaded,
  documentType = 'OTHER',
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);
  const [uploadedDoc, setUploadedDoc] = useState<DocumentResponse | null>(null);
  const [duplicateModalOpen, setDuplicateModalOpen] = useState(false);
  const [duplicateMessage, setDuplicateMessage] = useState('');
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleFile = async (file: File) => {
    setIsUploading(true);
    setErrorMsg(null);
    setUploadProgress(`Mengunggah ${file.name}...`);

    try {
      const doc = await documentsApi.upload(file, documentType);
      setUploadedDoc(doc);
      setUploadProgress(null);
      onUploaded(doc);
    } catch (err: any) {
      setUploadProgress(null);
      if (err.response?.status === 409) {
        setDuplicateMessage(
          err.response.data?.detail || 'Dokumen fisik ini sudah pernah diunggah sebelumnya (SHA-256 identik).'
        );
        setDuplicateModalOpen(true);
      } else {
        setErrorMsg(err.response?.data?.detail || 'Gagal mengunggah dokumen.');
      }
    } finally {
      setIsUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 bg-slate-50/50 p-6 text-center hover:border-blue-500 hover:bg-blue-50/20 transition-all cursor-pointer"
      >
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          accept=".pdf,.jpg,.jpeg,.png"
          onChange={(e) => {
            if (e.target.files && e.target.files[0]) {
              handleFile(e.target.files[0]);
            }
          }}
        />

        {uploadedDoc ? (
          <div className="flex items-center gap-3 text-emerald-700 bg-emerald-50 px-4 py-2 rounded-lg border border-emerald-200">
            <CheckCircle2 className="h-5 w-5 shrink-0" />
            <div className="text-left">
              <p className="text-xs font-semibold">{uploadedDoc.file_name}</p>
              <p className="text-[10px] text-emerald-600 font-mono">
                {uploadedDoc.document_code} • {(uploadedDoc.file_size_bytes / 1024).toFixed(1)} KB
              </p>
            </div>
          </div>
        ) : (
          <>
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100 text-blue-600 mb-2">
              <UploadCloud className="h-5 w-5" />
            </div>
            <p className="text-xs font-semibold text-slate-700">
              {isUploading ? uploadProgress : 'Klik atau seret file nota/SPK ke sini'}
            </p>
            <p className="text-[10px] text-slate-400 mt-1">Mendukung format PDF, JPG, PNG (Maks 15MB)</p>
          </>
        )}
      </div>

      {errorMsg && (
        <div className="flex items-center gap-2 rounded-lg bg-rose-50 p-2.5 text-xs text-rose-700 border border-rose-200">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}

      <DuplicateDocumentModal
        isOpen={duplicateModalOpen}
        onClose={() => setDuplicateModalOpen(false)}
        message={duplicateMessage}
      />
    </div>
  );
};
