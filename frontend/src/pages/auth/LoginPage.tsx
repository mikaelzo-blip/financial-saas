import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { ShieldCheck, Lock, Mail, AlertCircle } from 'lucide-react';
import { useAuth } from '../../store/AuthContext';
import { authApi } from '../../api/auth';
import { Button } from '../../components/ui/Button';
import { Input } from '../../components/ui/Input';

export const LoginPage: React.FC = () => {
  const location = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(
    (location.state as { sessionError?: string } | null)?.sessionError || null,
  );

  const { login } = useAuth();
  const navigate = useNavigate();

  const from = (location.state as any)?.from?.pathname || '/dashboard';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const session = await authApi.login({ email, password });
      login(session);
      navigate(from, { replace: true });
    } catch (err: any) {
      setError(err.message || 'Email atau kata sandi tidak valid.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4 py-12">
      <div className="w-full max-w-md space-y-8 rounded-2xl border border-slate-800 bg-slate-900 p-8 shadow-2xl">
        {/* Brand Header */}
        <div className="text-center">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-blue-600 font-bold text-white shadow-lg mb-3">
            FS
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-white">Financial SaaS</h2>
          <p className="mt-1 text-xs text-slate-400">
            Sistem Operasional Keuangan Kontraktor Indonesia
          </p>
        </div>

        {error && (
          <div className="flex items-center gap-2.5 rounded-lg border border-rose-800/60 bg-rose-950/40 p-3 text-xs text-rose-300">
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
            <span>{error}</span>
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="mt-8 space-y-5">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">
              Alamat Email
            </label>
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="nama@kontraktor.co.id"
              leftAddon={<Mail className="h-4 w-4 text-slate-500" />}
              className="bg-slate-950 border-slate-800 text-white placeholder:text-slate-600 focus:border-blue-500"
              required
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5">
              Kata Sandi
            </label>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              leftAddon={<Lock className="h-4 w-4 text-slate-500" />}
              className="bg-slate-950 border-slate-800 text-white placeholder:text-slate-600 focus:border-blue-500"
              required
            />
          </div>

          <Button
            type="submit"
            className="w-full mt-2"
            isLoading={isLoading}
            leftIcon={<ShieldCheck className="h-4 w-4" />}
          >
            Masuk ke Aplikasi
          </Button>
        </form>

      </div>
    </div>
  );
};
