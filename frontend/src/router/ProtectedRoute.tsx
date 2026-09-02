import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../store/AuthContext';
import { UserRole } from '../types/api';
import { SkeletonLoader } from '../components/feedback/SkeletonLoader';

export interface ProtectedRouteProps {
  children: React.ReactNode;
  allowedRoles?: UserRole[];
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  allowedRoles,
}) => {
  const { isAuthenticated, isLoading, sessionError, user } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex h-screen w-full items-center justify-center p-8 bg-slate-50">
        <div className="w-64 space-y-4 text-center">
          <div className="flex h-12 w-12 mx-auto items-center justify-center rounded-xl bg-blue-600 font-bold text-white shadow-md animate-pulse">
            FS
          </div>
          <p className="text-xs font-semibold text-slate-600">Memuat sesi pengguna...</p>
          <SkeletonLoader count={2} />
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location, sessionError }} replace />;
  }

  if (allowedRoles && user && !allowedRoles.includes(user.role)) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-center p-8">
        <h2 className="text-xl font-bold text-slate-900">Akses Dibatasi</h2>
        <p className="mt-2 max-w-md text-sm text-slate-600">
          Peran pengguna Anda ({user.role}) tidak memiliki izin untuk mengakses halaman ini.
        </p>
      </div>
    );
  }

  return <>{children}</>;
};
