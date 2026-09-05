import React, { useState } from 'react';
import { NavLink, Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Building2,
  Receipt,
  FileText,
  Users,
  Truck,
  ArrowDownLeft,
  ArrowUpRight,
  AlertTriangle,
  Wallet,
  BookOpen,
  Settings,
  LogOut,
  Menu,
  X,
  ShieldCheck,
  TrendingUp,
  Landmark,
  Scale,
  MessageSquare,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';
import { useAuth } from '../../store/AuthContext';
import { StatusBadge } from '../ui/StatusBadge';

export const AppLayout: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [reportsOpen, setReportsOpen] = useState(false);
  const [masterOpen, setMasterOpen] = useState(false);

  // PRD §26.1 Information Architecture for Contractor Owner:
  // 1. Dashboard, 2. WhatsApp Inbox, 3. Proyek, 4. Kas & Bank, 5. Rekonsiliasi Bank,
  // 6. Perlu Review, 7. Transaksi, 8. Dokumen, 9. Piutang, 10. Utang,
  // 11. Laporan (collapsible), 12. Data Master (collapsible), 13. Pengaturan
  const primaryNavItems = [
    { label: '1. Dashboard', path: '/dashboard', icon: LayoutDashboard },
    { label: '2. WhatsApp Inbox', path: '/whatsapp-inbox', icon: MessageSquare },
    { label: '3. Proyek', path: '/projects', icon: Building2 },
    { label: '4. Kas & Bank', path: '/payment-accounts', icon: Wallet },
    { label: '5. Rekonsiliasi Bank', path: '/bank-reconciliation', icon: Landmark },
    { label: '6. Perlu Review', path: '/review-queue', icon: AlertTriangle, badge: true },
    { label: '7. Transaksi', path: '/transactions', icon: Receipt },
    { label: '8. Dokumen Bukti', path: '/documents', icon: FileText },
    { label: '9. Piutang Usaha (AR)', path: '/receivables', icon: ArrowDownLeft },
    { label: '10. Utang Usaha (AP)', path: '/payables', icon: ArrowUpRight },
  ];

  const reportItems = [
    { label: 'Laba Rugi (P&L)', path: '/reports/profit-loss', icon: TrendingUp },
    { label: 'Neraca (Balance Sheet)', path: '/reports/balance-sheet', icon: Landmark },
    { label: 'Arus Kas (Cash Flow)', path: '/reports/cash-flow', icon: ArrowUpRight },
    { label: 'Profitabilitas Proyek', path: '/reports/project-profitability', icon: Building2 },
    { label: 'Posisi Kas Proyek', path: '/reports/project-cash', icon: Wallet },
    { label: 'Anggaran vs Realisasi', path: '/reports/budget-vs-actual', icon: FileText },
    { label: 'Neraca Saldo', path: '/reports/trial-balance', icon: Scale },
    { label: 'Buku Besar (GL)', path: '/reports/general-ledger', icon: BookOpen },
    { label: 'Umur Piutang (AR Aging)', path: '/reports/receivables', icon: ArrowDownLeft },
    { label: 'Umur Utang (AP Aging)', path: '/reports/payables', icon: ArrowUpRight },
  ];

  const masterItems = [
    { label: 'Pelanggan (Customer)', path: '/customers', icon: Users },
    { label: 'Vendor & Subkon', path: '/vendors', icon: Truck },
    { label: 'Bagan Akun (COA)', path: '/chart-of-accounts', icon: BookOpen },
  ];

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const isReportsActive = reportItems.some((item) => location.pathname.startsWith(item.path));
  const isMasterActive = masterItems.some((item) => location.pathname.startsWith(item.path));

  const getPageTitle = () => {
    const all = [...primaryNavItems, ...reportItems, ...masterItems, { label: 'Pengaturan & Sistem', path: '/settings' }];
    const current = all.find((item) => location.pathname.startsWith(item.path));
    return current ? current.label : 'Sistem Keuangan Kontraktor';
  };

  return (
    <div className="flex h-screen bg-slate-50 text-slate-900 overflow-hidden font-sans">
      {/* Mobile Drawer Overlay */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-40 bg-slate-900/60 backdrop-blur-xs md:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar Navigation */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-64 flex-col bg-slate-900 text-slate-300 transition-transform duration-200 ease-in-out md:static md:translate-x-0 ${
          mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Brand Header */}
        <div className="flex h-16 shrink-0 items-center justify-between border-b border-slate-800 px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-600 font-bold text-white shadow-md">
              FS
            </div>
            <div>
              <h1 className="text-sm font-bold text-white leading-none">Financial SaaS</h1>
              <p className="text-[10px] text-slate-400 mt-0.5">Kontraktor Indonesia</p>
            </div>
          </div>
          <button
            onClick={() => setMobileMenuOpen(false)}
            className="md:hidden text-slate-400 hover:text-white"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Tenant Indicator */}
        <div className="border-b border-slate-800/80 bg-slate-950/40 px-6 py-3">
          <p className="text-[10px] font-semibold tracking-wider uppercase text-slate-400">
            Perusahaan Aktif
          </p>
          <p className="truncate text-xs font-semibold text-white mt-0.5">
            {user?.organizationName}
          </p>
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
          {/* Primary Operations (1-10) */}
          {primaryNavItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={() => setMobileMenuOpen(false)}
                className={({ isActive }) =>
                  `flex items-center justify-between rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                    isActive
                      ? 'bg-blue-600 text-white shadow-xs font-semibold'
                      : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                  }`
                }
              >
                <div className="flex items-center gap-3">
                  <Icon className="h-4 w-4 shrink-0" />
                  <span>{item.label}</span>
                </div>
              </NavLink>
            );
          })}

          {/* Group 11: Laporan (Collapsible) */}
          <div className="pt-2">
            <button
              onClick={() => setReportsOpen(!reportsOpen)}
              className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-xs font-semibold transition-colors cursor-pointer ${
                isReportsActive ? 'text-white' : 'text-slate-400 hover:bg-slate-800/60 hover:text-white'
              }`}
            >
              <div className="flex items-center gap-3">
                <BookOpen className="h-4 w-4 shrink-0 text-blue-400" />
                <span>11. Laporan Keuangan</span>
              </div>
              {reportsOpen || isReportsActive ? (
                <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5 text-slate-400" />
              )}
            </button>
            {(reportsOpen || isReportsActive) && (
              <div className="ml-4 pl-3 border-l border-slate-800 space-y-1 mt-1">
                {reportItems.map((item) => {
                  const Icon = item.icon;
                  return (
                    <NavLink
                      key={item.path}
                      to={item.path}
                      onClick={() => setMobileMenuOpen(false)}
                      className={({ isActive }) =>
                        `flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[11px] font-medium transition-colors ${
                          isActive
                            ? 'bg-blue-600/80 text-white font-semibold'
                            : 'text-slate-400 hover:bg-slate-800/40 hover:text-slate-200'
                        }`
                      }
                    >
                      <Icon className="h-3.5 w-3.5 shrink-0" />
                      <span>{item.label}</span>
                    </NavLink>
                  );
                })}
              </div>
            )}
          </div>

          {/* Group 12: Data Master (Collapsible) */}
          <div className="pt-1">
            <button
              onClick={() => setMasterOpen(!masterOpen)}
              className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-xs font-semibold transition-colors cursor-pointer ${
                isMasterActive ? 'text-white' : 'text-slate-400 hover:bg-slate-800/60 hover:text-white'
              }`}
            >
              <div className="flex items-center gap-3">
                <Users className="h-4 w-4 shrink-0 text-emerald-400" />
                <span>12. Data Master</span>
              </div>
              {masterOpen || isMasterActive ? (
                <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5 text-slate-400" />
              )}
            </button>
            {(masterOpen || isMasterActive) && (
              <div className="ml-4 pl-3 border-l border-slate-800 space-y-1 mt-1">
                {masterItems.map((item) => {
                  const Icon = item.icon;
                  return (
                    <NavLink
                      key={item.path}
                      to={item.path}
                      onClick={() => setMobileMenuOpen(false)}
                      className={({ isActive }) =>
                        `flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[11px] font-medium transition-colors ${
                          isActive
                            ? 'bg-blue-600/80 text-white font-semibold'
                            : 'text-slate-400 hover:bg-slate-800/40 hover:text-slate-200'
                        }`
                      }
                    >
                      <Icon className="h-3.5 w-3.5 shrink-0" />
                      <span>{item.label}</span>
                    </NavLink>
                  );
                })}
              </div>
            )}
          </div>

          {/* Group 13: Pengaturan & Sistem */}
          <div className="pt-1">
            <NavLink
              to="/settings"
              onClick={() => setMobileMenuOpen(false)}
              className={({ isActive }) =>
                `flex items-center justify-between rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-600 text-white shadow-xs font-semibold'
                    : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                }`
              }
            >
              <div className="flex items-center gap-3">
                <Settings className="h-4 w-4 shrink-0" />
                <span>13. Pengaturan & Sistem</span>
              </div>
            </NavLink>
          </div>
        </nav>

        {/* User Footer Profile */}
        <div className="border-t border-slate-800 bg-slate-950/50 p-4">
          <div className="flex items-center justify-between gap-3">
            <div className="truncate">
              <p className="truncate text-xs font-semibold text-white">{user?.fullName || 'Operator'}</p>
              <div className="mt-1 flex items-center gap-1.5">
                <StatusBadge status={user?.role || 'OPERATOR'} size="sm" />
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-rose-400 transition-colors cursor-pointer"
              title="Keluar / Logout"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top Navigation Bar */}
        <header className="flex h-16 shrink-0 items-center justify-between border-b border-slate-200/80 bg-white px-6 shadow-2xs">
          <div className="flex items-center gap-4">
            <button
              onClick={() => setMobileMenuOpen(true)}
              className="text-slate-600 hover:text-slate-900 md:hidden cursor-pointer"
            >
              <Menu className="h-6 w-6" />
            </button>
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <span className="font-semibold text-slate-900">{getPageTitle()}</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-2 rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
              <span>Sesi Terautentikasi</span>
            </div>
          </div>
        </header>

        {/* Page Dynamic Content View */}
        <main className="flex-1 overflow-y-auto p-6 md:p-8 bg-slate-50/60">
          <div className="mx-auto max-w-7xl">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};

