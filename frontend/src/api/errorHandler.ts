import { AxiosError } from 'axios';

export interface ApiError {
  message: string;
  statusCode?: number;
  fieldErrors?: Record<string, string>;
  isDuplicate?: boolean;
}

export function parseApiError(error: unknown): ApiError {
  if (error instanceof AxiosError) {
    const status = error.response?.status;
    const data = error.response?.data;

    // 409 Duplicate Entity
    if (status === 409) {
      return {
        message: data?.detail || 'Dokumen atau entitas ini sudah ada di sistem.',
        statusCode: 409,
        isDuplicate: true,
      };
    }

    // 422 Unprocessable Entity (FastAPI validation error)
    if (status === 422 && Array.isArray(data?.detail)) {
      const fieldErrors: Record<string, string> = {};
      data.detail.forEach((err: any) => {
        const fieldName = err.loc ? err.loc[err.loc.length - 1] : 'general';
        fieldErrors[fieldName] = err.msg || 'Format input tidak valid';
      });
      return {
        message: 'Mohon periksa kembali input formulir.',
        statusCode: 422,
        fieldErrors,
      };
    }

    // 403 Forbidden
    if (status === 403) {
      return {
        message: data?.detail || 'Anda tidak memiliki hak akses untuk aksi ini.',
        statusCode: 403,
      };
    }

    // 401 Unauthorized
    if (status === 401) {
      return {
        message: 'Sesi login telah berakhir. Silakan login kembali.',
        statusCode: 401,
      };
    }

    return {
      message: data?.detail || error.message || 'Terjadi kesalahan pada sistem backend.',
      statusCode: status,
    };
  }

  return {
    message: error instanceof Error ? error.message : 'Terjadi kesalahan tidak terduga.',
  };
}
