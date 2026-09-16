import { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Button } from '../ui/Button';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught React ErrorBoundary catch:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center p-6 bg-slate-50">
          <div className="max-w-md w-full bg-white rounded-xl shadow-lg border border-slate-200 p-6 text-center space-y-4">
            <div className="mx-auto w-12 h-12 bg-rose-100 rounded-full flex items-center justify-center text-rose-600">
              <AlertTriangle className="h-6 w-6" />
            </div>
            <h2 className="text-lg font-bold text-slate-900">Terjadi Kesalahan Tampilan</h2>
            <p className="text-xs text-slate-600 leading-relaxed">
              {this.state.error?.message || 'Aplikasi mendeteksi error tak terduga pada halaman ini.'}
            </p>
            <div className="pt-2">
              <Button
                variant="primary"
                size="sm"
                leftIcon={<RefreshCw className="h-4 w-4" />}
                onClick={() => window.location.reload()}
              >
                Muat Ulang Halaman
              </Button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
