/**
 * Safe API error formatter for consistent and user-friendly error reporting in Indonesian.
 * Handles Axios errors, FastAPI 422 validation lists, strings, and standard Error instances.
 * Guarantees a string output so React toast rendering never encounters an object-as-child error.
 */
export const formatApiError = (err: unknown, defaultMessage = 'Terjadi kesalahan sistem.'): string => {
  if (!err) return defaultMessage;

  if (typeof err === 'string') return err;

  let detail: unknown;
  if (typeof err === 'object' && err !== null) {
    if ('response' in err) {
      const axiosResponse = (err as { response?: { data?: { detail?: unknown; message?: unknown } } }).response;
      detail = axiosResponse?.data?.detail ?? axiosResponse?.data?.message;
    } else if ('detail' in err) {
      detail = (err as { detail?: unknown }).detail;
    } else if ('message' in err && typeof (err as { message?: unknown }).message === 'string') {
      detail = (err as { message: string }).message;
    }
  }

  if (typeof detail === 'string') {
    if (detail.includes('Field required') && detail.includes('status')) {
      return 'Format status proyek tidak valid atau status wajib diisi.';
    }
    if (detail.includes('Project is not found')) {
      return 'Proyek tidak ditemukan.';
    }
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === 'string') return item;
        if (item && typeof item === 'object' && 'msg' in item) {
          const rawItem = item as { loc?: unknown[]; msg: unknown };
          const loc = Array.isArray(rawItem.loc)
            ? rawItem.loc.filter((l) => l !== 'body').join('.')
            : '';
          const msg = typeof rawItem.msg === 'string' ? rawItem.msg : JSON.stringify(rawItem.msg);
          if (loc === 'status' && msg.toLowerCase().includes('required')) {
            return 'Status proyek wajib diisi.';
          }
          return loc ? `${loc}: ${msg}` : msg;
        }
        return JSON.stringify(item);
      })
      .filter(Boolean);
    if (messages.length > 0) return messages.join('; ');
  }

  if (typeof detail === 'object' && detail !== null) {
    try {
      return JSON.stringify(detail);
    } catch {
      return defaultMessage;
    }
  }

  if (err instanceof Error) {
    if (err.message.includes('status code 422')) {
      return 'Permintaan tidak valid (data tidak lengkap atau format salah).';
    }
    if (err.message.includes('status code 404')) {
      return 'Data tidak ditemukan.';
    }
    if (err.message.includes('Network Error')) {
      return 'Gagal terhubung ke server backend.';
    }
    return err.message;
  }

  return defaultMessage;
};
