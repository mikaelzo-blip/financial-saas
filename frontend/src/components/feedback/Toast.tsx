import React, { createContext, useContext, useState, useCallback } from 'react';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';

export type ToastType = 'success' | 'error' | 'info' | 'warning';

export interface Toast {
  id: string;
  type: ToastType;
  message: string;
  duration?: number;
}

interface ToastContextValue {
  showToast: (message: string, type?: ToastType, duration?: number) => void;
  success: (message: string) => void;
  error: (message: string) => void;
  info: (message: string) => void;
  warning: (message: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

function formatToastMessage(message: unknown): string {
  if (typeof message === 'string') return message;
  if (!message) return '';
  if (Array.isArray(message)) {
    return message
      .map((item) => {
        if (typeof item === 'object' && item !== null) {
          const loc = (item as any).loc ? `[${(item as any).loc.join('.')}] ` : '';
          const msg = (item as any).msg || (item as any).message || JSON.stringify(item);
          return `${loc}${msg}`;
        }
        return String(item);
      })
      .join('; ');
  }
  if (typeof message === 'object') {
    const obj = message as Record<string, any>;
    return obj.message || obj.detail || obj.msg || JSON.stringify(message);
  }
  return String(message);
}

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const showToast = useCallback(
    (message: string | unknown, type: ToastType = 'info', duration: number = 4000) => {
      const id = Math.random().toString(36).substring(2, 9);
      const safeMessage = formatToastMessage(message);
      const newToast: Toast = { id, type, message: safeMessage, duration };
      setToasts((prev) => [...prev, newToast]);

      if (duration > 0) {
        setTimeout(() => {
          removeToast(id);
        }, duration);
      }
    },
    [removeToast]
  );

  const success = useCallback((msg: string | unknown) => showToast(msg, 'success'), [showToast]);
  const error = useCallback((msg: string | unknown) => showToast(msg, 'error', 6000), [showToast]);
  const info = useCallback((msg: string | unknown) => showToast(msg, 'info'), [showToast]);
  const warning = useCallback((msg: string | unknown) => showToast(msg, 'warning', 5000), [showToast]);

  return (
    <ToastContext.Provider value={{ showToast, success, error, info, warning }}>
      {children}
      <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2 pointer-events-none max-w-md w-full px-4">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`pointer-events-auto flex items-start gap-3 rounded-xl border p-4 shadow-xl transition-all animate-slide-in ${
              toast.type === 'success'
                ? 'border-emerald-200 bg-white text-emerald-900'
                : toast.type === 'error'
                ? 'border-rose-200 bg-white text-rose-900'
                : toast.type === 'warning'
                ? 'border-amber-200 bg-white text-amber-900'
                : 'border-blue-200 bg-white text-blue-900'
            }`}
          >
            <div className="shrink-0 pt-0.5">
              {toast.type === 'success' && <CheckCircle2 className="h-5 w-5 text-emerald-600" />}
              {toast.type === 'error' && <AlertCircle className="h-5 w-5 text-rose-600" />}
              {toast.type === 'warning' && <AlertCircle className="h-5 w-5 text-amber-600" />}
              {toast.type === 'info' && <Info className="h-5 w-5 text-blue-600" />}
            </div>
            <div className="flex-1 text-xs font-medium leading-relaxed">{toast.message}</div>
            <button
              onClick={() => removeToast(toast.id)}
              className="shrink-0 p-1 text-slate-400 hover:text-slate-600 cursor-pointer"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
};

export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};
