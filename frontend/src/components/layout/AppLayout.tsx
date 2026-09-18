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
  CheckSquare,
  ChevronDown,
  ChevronRight,
  Inbox as InboxIcon,
} from 'lucide-react';
import { useAuth } from '../../store/AuthContext';
import { StatusBadge } from '../ui/StatusBadge';

export const AppLayout: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Group expansion state
  const [inboxOpen, setInboxOpen] = useState(false);
  const [cashBankOpen, setCashBankOpen] = useState(false);
  const [billingOpen, setBillingOpen] = useState(false);
  const [reportsOpen, setReportsOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Sub-items for Inbox
  const inboxItems = [
    { label: 'WhatsApp Inbox', path: '/whatsapp-inbox', icon: MessageSquare },
    { label: 'Dokumen Bukti', path: '/documents', icon: FileText },
    { label: 'Perlu Diperiksa', path: '/review-queue', icon: AlertTriangle },
  ];

  // Sub-items for Kas & Bank
  const cashBankItems = [
    { label: 'Akun Kas & Bank', path: '/payment-accounts', icon: Wallet },
    { label: 'Rekonsiliasi Bank', path: '/bank-reconciliation', icon: Landmark },
    { label: 'Transaksi Jurnal', path: '/transactions', icon: Receipt },
  ];

  // Sub-items for Tagihan
  const billingItems = [
    { label: 'Piutang Pelanggan', path: '/receivables', icon: ArrowDownLeft },
    { label: 'Utang Vendor', path: '/payables', icon: ArrowUpRight },
  ];

  // Financial Reports
  const reportItems = [
    { label: 'Laporan Laba Rugi', path: '/reports/profit-loss', icon: TrendingUp },
    { label: 'Laporan Posisi Keuangan (Neraca)', path: '/reports/balance-sheet', icon: Landmark },
    { label: 'Laporan Arus Kas', path: '/reports/cash-flow', icon: ArrowUpRight },
    { label: 'Profitabilitas Proyek', path: '/reports/project-profitability', icon: Building2 },
    { label: 'Posisi Kas Proyek', path: '/reports/project-cash', icon: Wallet },
    { label: 'Anggaran vs Realisasi', path: '/reports/budget-vs-actual', icon: FileText },
    { label: 'Neraca Saldo', path: '/reports/trial-balance', icon: Scale },
    { label: 'Buku Besar', path: '/reports/general-ledger', icon: BookOpen },
    { label: 'Umur Piutang Pelanggan', path: '/reports/receivables', icon: ArrowDownLeft },
    { label: 'Umur Utang Vendor', path: '/reports/payables', icon: ArrowUpRight },
    { label: 'Rekonsiliasi Konsultan', path: '/reports/consultant-reconciliation', icon: CheckSquare },
  ];

  // Settings & Master
  const settingsItems = [
    { label: 'Pelanggan', path: '/customers', icon: Users },
    { label: 'Vendor & Subkon', path: '/vendors', icon: Truck },
    { label: 'Aset Tetap', path: '/fixed-assets', icon: Landmark },
    { label: 'Daftar Akun (COA)', path: '/chart-of-accounts', icon: BookOpen },
    { label: 'Konfigurasi Sistem', path: '/settings', icon: Settings },
  ];

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const isInboxActive = inboxItems.some((item) => location.pathname.startsWith(item.path));
  const isCashBankActive = cashBankItems.some((item) => location.pathname.startsWith(item.path));
  const isBillingActive = billingItems.some((item) => location.pathname.startsWith(item.path));
  const isReportsActive = reportItems.some((item) => location.pathname.startsWith(item.path));
  const isSettingsActive = settingsItems.some((item) => location.pathname.startsWith(item.path));

  const getPageTitle = () => {
    if (location.pathname === '/dashboard') return 'Beranda';
    if (location.pathname.startsWith('/whatsapp-inbox')) return 'WhatsApp Inbox';
    if (location.pathname.startsWith('/documents')) return 'Dokumen Bukti';
    if (location.pathname.startsWith('/review-queue')) return 'Perlu Diperiksa';
    if (location.pathname.startsWith('/projects')) return 'Proyek';
    if (location.pathname.startsWith('/payment-accounts')) return 'Akun Kas & Bank';
    if (location.pathname.startsWith('/bank-reconciliation')) return 'Rekonsiliasi Bank';
    if (location.pathname.startsWith('/transactions')) return 'Transaksi Jurnal';
    if (location.pathname.startsWith('/receivables')) return 'Piutang Pelanggan';
    if (location.pathname.startsWith('/payables')) return 'Utang Vendor';
    if (location.pathname.startsWith('/customers')) return 'Pelanggan';
    if (location.pathname.startsWith('/vendors')) return 'Vendor & Subkon';
    if (location.pathname.startsWith('/fixed-assets')) return 'Aset Tetap';
    if (location.pathname.startsWith('/chart-of-accounts')) return 'Daftar Akun (COA)';
    if (location.pathname.startsWith('/settings')) return 'Pengaturan & Sistem';

    const reportMatch = reportItems.find((item) => location.pathname.startsWith(item.path));
    if (reportMatch) return reportMatch.label;

    return 'Sistem Keuangan Kontraktor';
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
        <div className="flex h-16 shrink-0 items-center justify-between border-b border-slate-800 px-5">
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
            aria-label="Tutup Menu"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Active Company Indicator */}
        <div className="border-b border-slate-800/80 bg-slate-950/40 px-5 py-2.5">
          <p className="text-[10px] font-semibold tracking-wider uppercase text-slate-400">
            Perusahaan Aktif
          </p>
          <p className="truncate text-xs font-semibold text-white mt-0.5">
            {user?.organizationName || 'Organisasi'}
          </p>
        </div>

        {/* Navigation Links */}
        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-3">
          {/* 1. Beranda */}
          <NavLink
            to="/dashboard"
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
              <LayoutDashboard className="h-4 w-4 shrink-0" />
              <span>Beranda</span>
            </div>
          </NavLink>

          {/* 2. Inbox (WhatsApp, Dokumen, Perlu Diperiksa) */}
          <div>
            <button
              onClick={() => setInboxOpen(!inboxOpen)}
              className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-xs font-medium transition-colors cursor-pointer ${
                isInboxActive ? 'text-white font-semibold' : 'text-slate-300 hover:bg-slate-800/60 hover:text-white'
              }`}
            >
              <div className="flex items-center gap-3">
                <InboxIcon className="h-4 w-4 shrink-0 text-cyan-400" />
                <span>Inbox</span>
              </div>
              {inboxOpen || isInboxActive ? (
                <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5 text-slate-400" />
              )}
            </button>
            {(inboxOpen || isInboxActive) && (
              <div className="ml-4 pl-3 border-l border-slate-800 space-y-1 mt-1">
                {inboxItems.map((item) => {
                  const Icon = item.icon;
                  return (
                    <NavLink
                      key={item.path}
                      to={item.path}
                      onClick={() => setMobileMenuOpen(false)}
                      className={({ isActive }) =>
                        `flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[11px] font-medium transition-colors ${
                          isActive
                            ? 'bg-blue-600 text-white font-semibold'
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

          {/* 3. Proyek */}
          <NavLink
            to="/projects"
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
              <Building2 className="h-4 w-4 shrink-0 text-emerald-400" />
              <span>Proyek</span>
            </div>
          </NavLink>

          {/* 4. Kas & Bank (Akun, Rekonsiliasi, Transaksi) */}
          <div>
            <button
              onClick={() => setCashBankOpen(!cashBankOpen)}
              className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-xs font-medium transition-colors cursor-pointer ${
                isCashBankActive ? 'text-white font-semibold' : 'text-slate-300 hover:bg-slate-800/60 hover:text-white'
              }`}
            >
              <div className="flex items-center gap-3">
                <Wallet className="h-4 w-4 shrink-0 text-blue-400" />
                <span>Kas & Bank</span>
              </div>
              {cashBankOpen || isCashBankActive ? (
                <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5 text-slate-400" />
              )}
            </button>
            {(cashBankOpen || isCashBankActive) && (
              <div className="ml-4 pl-3 border-l border-slate-800 space-y-1 mt-1">
                {cashBankItems.map((item) => {
                  const Icon = item.icon;
                  return (
                    <NavLink
                      key={item.path}
                      to={item.path}
                      onClick={() => setMobileMenuOpen(false)}
                      className={({ isActive }) =>
                        `flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[11px] font-medium transition-colors ${
                          isActive
                            ? 'bg-blue-600 text-white font-semibold'
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

          {/* 5. Tagihan (Piutang, Utang) */}
          <div>
            <button
              onClick={() => setBillingOpen(!billingOpen)}
              className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-xs font-medium transition-colors cursor-pointer ${
                isBillingActive ? 'text-white font-semibold' : 'text-slate-300 hover:bg-slate-800/60 hover:text-white'
              }`}
            >
              <div className="flex items-center gap-3">
                <Receipt className="h-4 w-4 shrink-0 text-amber-400" />
                <span>Tagihan</span>
              </div>
              {billingOpen || isBillingActive ? (
                <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5 text-slate-400" />
              )}
            </button>
            {(billingOpen || isBillingActive) && (
              <div className="ml-4 pl-3 border-l border-slate-800 space-y-1 mt-1">
                {billingItems.map((item) => {
                  const Icon = item.icon;
                  return (
                    <NavLink
                      key={item.path}
                      to={item.path}
                      onClick={() => setMobileMenuOpen(false)}
                      className={({ isActive }) =>
                        `flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[11px] font-medium transition-colors ${
                          isActive
                            ? 'bg-blue-600 text-white font-semibold'
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

          {/* 6. Laporan (Collapsible) */}
          <div>
            <button
              onClick={() => setReportsOpen(!reportsOpen)}
              className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-xs font-medium transition-colors cursor-pointer ${
                isReportsActive ? 'text-white font-semibold' : 'text-slate-300 hover:bg-slate-800/60 hover:text-white'
              }`}
            >
              <div className="flex items-center gap-3">
                <BookOpen className="h-4 w-4 shrink-0 text-indigo-400" />
                <span>Laporan</span>
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

          {/* 7. Pengaturan (Master Data & Sistem) */}
          <div>
            <button
              onClick={() => setSettingsOpen(!settingsOpen)}
              className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-xs font-medium transition-colors cursor-pointer ${
                isSettingsActive ? 'text-white font-semibold' : 'text-slate-300 hover:bg-slate-800/60 hover:text-white'
              }`}
            >
              <div className="flex items-center gap-3">
                <Settings className="h-4 w-4 shrink-0 text-slate-400" />
                <span>Pengaturan</span>
              </div>
              {settingsOpen || isSettingsActive ? (
                <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5 text-slate-400" />
              )}
            </button>
            {(settingsOpen || isSettingsActive) && (
              <div className="ml-4 pl-3 border-l border-slate-800 space-y-1 mt-1">
                {settingsItems.map((item) => {
                  const Icon = item.icon;
                  return (
                    <NavLink
                      key={item.path}
                      to={item.path}
                      onClick={() => setMobileMenuOpen(false)}
                      className={({ isActive }) =>
                        `flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[11px] font-medium transition-colors ${
                          isActive
                            ? 'bg-blue-600 text-white font-semibold'
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
              aria-label="Buka Menu"
            >
              <Menu className="h-6 w-6" />
            </button>
            <div className="flex items-center gap-2">
              <h1 className="text-lg md:text-xl font-bold text-slate-900 tracking-tight">{getPageTitle()}</h1>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Subtle, de-emphasized session indicator */}
            <div className="hidden sm:flex items-center gap-1.5 text-xs text-slate-400 font-medium">
              <ShieldCheck className="h-3.5 w-3.5 text-slate-400" />
              <span>Sesi Aman</span>
            </div>
          </div>
        </header>

        {/* Page Dynamic Content View with 1440-1600px usable desktop max-width */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 md:p-8 bg-slate-50/60">
          <div className="mx-auto w-full max-w-[1536px]">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};
