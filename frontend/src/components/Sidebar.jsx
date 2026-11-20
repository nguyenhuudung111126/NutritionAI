import { useState } from 'react';
import {
  Activity,
  Apple,
  Bot,
  CalendarDays,
  ChevronRight,
  Cpu,
  Droplets,
  FileText,
  Flame,
  HeartPulse,
  LayoutDashboard,
  LogOut,
  Menu,
  ScrollText,
  Settings,
  Stethoscope,
  TrendingUp,
  UserRound,
  Users,
  X,
} from 'lucide-react';

const ADMIN_SECTIONS = [
  {
    title: 'Dữ liệu & Phác đồ',
    items: [
      { id: 'admin-overview', label: 'Tổng quan', icon: LayoutDashboard },
      { id: 'admin-foods', label: 'Kho Thực phẩm', icon: Apple },
      { id: 'admin-diseases', label: 'Danh mục Bệnh lý', icon: Stethoscope },
      { id: 'admin-documents', label: 'Quản lý Tài liệu', icon: FileText },
    ],
  },
  {
    title: 'Quản trị Hệ thống',
    items: [
      { id: 'admin-patients', label: 'Quản lý Tài khoản', icon: Users },
      { id: 'admin-audit', label: 'Giám sát Vận hành', icon: ScrollText },
      { id: 'admin-evals', label: 'Đánh giá Hệ thống', icon: Cpu },
    ],
  },
  {
    title: 'Hệ thống',
    items: [{ id: 'admin-account', label: 'Tài khoản', icon: Settings }],
  },
];

const PATIENT_ITEMS = [
  { id: 'overview', label: 'Bảng điều khiển', shortLabel: 'Tổng quan', icon: LayoutDashboard },
  { id: 'meal-plan', label: 'Lập Thực đơn', shortLabel: 'Thực đơn', icon: CalendarDays },
  { id: 'foods', label: 'Tra cứu Thực phẩm', shortLabel: 'Thực phẩm', icon: Apple },
  { id: 'assistant', label: 'Trợ lý AI', shortLabel: 'Trợ lý AI', icon: Bot },
  { id: 'trends', label: 'Biểu đồ Xét nghiệm', shortLabel: 'Xét nghiệm', icon: TrendingUp },
  { id: 'profile', label: 'Hồ sơ của tôi', shortLabel: 'Hồ sơ', icon: UserRound },
];

const PATIENT_BOTTOM_IDS = ['overview', 'meal-plan', 'foods', 'assistant', 'profile'];
const ADMIN_BOTTOM_ITEMS = [
  { id: 'admin-overview', shortLabel: 'Tổng quan', icon: LayoutDashboard },
  { id: 'admin-foods', shortLabel: 'Thực phẩm', icon: Apple },
  { id: 'admin-patients', shortLabel: 'Tài khoản', icon: Users },
  { id: 'admin-audit', shortLabel: 'Giám sát', icon: ScrollText },
];

const SIDEBAR_BG_STYLE = {
  backgroundColor: '#dff2fe',
  backgroundImage: [
    'radial-gradient(circle at 15% 10%, rgba(125, 211, 252, 0.55) 0%, transparent 45%)',
    'radial-gradient(circle at 88% 34%, rgba(94, 234, 212, 0.45) 0%, transparent 48%)',
    'radial-gradient(circle at 12% 64%, rgba(103, 232, 249, 0.48) 0%, transparent 46%)',
    'radial-gradient(circle at 85% 90%, rgba(110, 231, 183, 0.45) 0%, transparent 48%)',
    'linear-gradient(180deg, rgba(224, 242, 254, 0.92) 0%, rgba(207, 250, 254, 0.88) 50%, rgba(204, 251, 241, 0.94) 100%)',
  ].join(', '),
};

export default function Sidebar({
  user,
  onLogout,
  activeTab,
  onChangeTab,
  overview,
}) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const isAdmin = user?.role === 'ADMIN';
  const profile = overview?.profile;
  const target = overview?.target;
  const initialLetter = (profile?.nickname || user?.display_name || 'B').trim().charAt(0).toUpperCase();

  const allItems = isAdmin ? ADMIN_SECTIONS.flatMap((s) => s.items) : PATIENT_ITEMS;
  const currentTabLabel = allItems.find((it) => it.id === activeTab)?.label || 'NutriGuard AI';

  const handleSelectTab = (id) => {
    onChangeTab(id);
    setMobileOpen(false);
  };

  const renderNavButton = ({ id, label, icon: Icon }) => {
    const active = activeTab === id;
    return (
      <button
        key={id}
        onClick={() => handleSelectTab(id)}
        className={`group flex w-full items-center justify-between gap-2 rounded-lg px-3 py-2 text-xs font-semibold transition-all ${
          active
            ? 'bg-gradient-to-r from-sky-500 to-teal-500 text-white shadow-md shadow-sky-600/25'
            : 'border border-white/85 bg-white/75 text-slate-700 shadow-2xs backdrop-blur-sm hover:border-white hover:bg-white/95 hover:text-sky-800'
        }`}
      >
        <span className="flex min-w-0 items-center gap-2.5">
          <span
            className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-md transition ${
              active
                ? 'bg-white/20 text-white'
                : 'bg-sky-100/75 text-sky-700 group-hover:bg-sky-100'
            }`}
          >
            <Icon className="h-3.5 w-3.5" />
          </span>
          <span className="truncate font-bold">{label}</span>
        </span>
        {active && <ChevronRight className="h-4 w-4 shrink-0 text-white/90" />}
      </button>
    );
  };

  const renderSidebarInner = (isMobileDrawer = false) => (
    <>
      <svg
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 h-full w-full opacity-55"
        preserveAspectRatio="none"
        viewBox="0 0 300 900"
      >
        <defs>
          <pattern id={isMobileDrawer ? 'sidebar-dots-mob' : 'sidebar-grid-dots'} width="24" height="24" patternUnits="userSpaceOnUse">
            <circle cx="3" cy="3" r="1.1" fill="rgba(14, 165, 233, 0.18)" />
          </pattern>
          <linearGradient id={isMobileDrawer ? 'ribbon-a-mob' : 'ribbon-a'} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="rgba(255,255,255,0.55)" />
            <stop offset="100%" stopColor="rgba(56,189,248,0.18)" />
          </linearGradient>
          <linearGradient id={isMobileDrawer ? 'ribbon-b-mob' : 'ribbon-b'} x1="1" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="rgba(45,212,191,0.22)" />
            <stop offset="100%" stopColor="rgba(255,255,255,0.45)" />
          </linearGradient>
        </defs>

        <rect width="300" height="900" fill={`url(#${isMobileDrawer ? 'sidebar-dots-mob' : 'sidebar-grid-dots'})`} />
        <path d="M-30,70 C90,140 210,20 330,110 L330,220 C200,130 90,250 -30,170 Z" fill={`url(#${isMobileDrawer ? 'ribbon-a-mob' : 'ribbon-a'})`} />
        <path d="M-30,290 C110,210 200,370 330,270 L330,385 C195,465 95,315 -30,400 Z" fill={`url(#${isMobileDrawer ? 'ribbon-b-mob' : 'ribbon-b'})`} />
        <path d="M-30,510 C95,595 215,445 330,545 L330,660 C205,565 85,705 -30,615 Z" fill={`url(#${isMobileDrawer ? 'ribbon-a-mob' : 'ribbon-a'})`} />
        <path d="M-30,735 C105,660 210,805 330,720 L330,850 C195,915 90,775 -30,845 Z" fill={`url(#${isMobileDrawer ? 'ribbon-b-mob' : 'ribbon-b'})`} />
        <circle cx="255" cy="185" r="78" fill="none" stroke="rgba(255,255,255,0.5)" strokeWidth="1.2" />
        <circle cx="42" cy="480" r="95" fill="none" stroke="rgba(255,255,255,0.45)" strokeWidth="1.2" />
        <circle cx="240" cy="760" r="88" fill="none" stroke="rgba(255,255,255,0.5)" strokeWidth="1.2" />
      </svg>

      <div className="relative z-10 flex-1 space-y-5 overflow-y-auto p-4 sm:p-5">
        {/* Brand */}
        <div className="flex items-center justify-between gap-2">
          <button
            onClick={() => handleSelectTab(isAdmin ? 'admin-overview' : 'overview')}
            className="group flex min-w-0 items-center gap-3 px-1 text-left"
          >
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-sky-500 to-teal-500 text-white shadow-md shadow-sky-500/25 transition group-hover:scale-105">
              <Stethoscope className="h-5 w-5" />
            </span>
            <div className="min-w-0">
              <div className="truncate text-base font-extrabold tracking-tight text-slate-900">NutriGuard AI</div>
              <div className="truncate text-[11px] font-semibold text-teal-800">
                {isAdmin ? 'Cổng Quản trị Hệ thống' : 'Trạm Dinh dưỡng Lâm sàng'}
              </div>
            </div>
          </button>
          {isMobileDrawer && (
            <button
              type="button"
              onClick={() => setMobileOpen(false)}
              className="rounded-xl border border-white/90 bg-white/80 p-1.5 text-slate-600 hover:bg-white"
              aria-label="Đóng menu"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>

        {isAdmin ? (
          <div className="space-y-4">
            {ADMIN_SECTIONS.map((sec) => (
              <div key={sec.title} className="space-y-1.5">
                <div className="px-1 text-[10px] font-extrabold uppercase tracking-wider text-sky-900/70">
                  {sec.title}
                </div>
                <nav className="space-y-1.5">
                  {sec.items.map(renderNavButton)}
                </nav>
              </div>
            ))}
          </div>
        ) : (
          <>
            {/* Patient Monitor Card */}
            <div className="rounded-2xl border border-white/95 bg-white/90 p-3.5 shadow-sm shadow-sky-900/10 backdrop-blur-md space-y-2.5">
              <div className="flex items-center justify-between gap-2">
                <div className="flex min-w-0 items-center gap-2">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-sky-500 to-teal-500 text-xs font-extrabold text-white shadow-2xs">
                    {initialLetter}
                  </span>
                  <span className="truncate text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    Hồ sơ của bạn
                  </span>
                </div>
                {target && (
                  <span className="shrink-0 whitespace-nowrap rounded-full border border-sky-200 bg-sky-50 px-2.5 py-0.5 text-[10px] font-extrabold text-sky-700">
                    {target.regime_code}
                  </span>
                )}
              </div>

              <div className="rounded-lg border border-sky-100 bg-sky-50/50 px-3 py-2 text-xs font-extrabold text-slate-900">
                {profile?.nickname || user?.display_name || 'Bệnh nhân'}
              </div>

              {profile && target && (
                <div className="space-y-2 text-[11px]">
                  <div className="flex items-center justify-between px-0.5 font-medium text-slate-500">
                    <span>{profile.age} tuổi • {profile.gender}</span>
                    <span>{profile.weight_kg ? `${profile.weight_kg}kg` : '—'}{profile.bmi ? ` (BMI ${profile.bmi})` : ''}</span>
                  </div>
                  <div className="grid grid-cols-2 gap-1.5">
                    <div className="rounded-lg border border-sky-100 bg-sky-50/65 px-2.5 py-1.5">
                      <div className="flex items-center gap-1 text-[10px] font-semibold text-sky-700">
                        <Flame className="h-3 w-3 text-sky-600" /> Calo/ngày
                      </div>
                      <div className="font-extrabold text-slate-900 tabular-nums">{target.energy_kcal} kcal</div>
                    </div>
                    <div className="rounded-lg border border-teal-100 bg-teal-50/65 px-2.5 py-1.5">
                      <div className="flex items-center gap-1 text-[10px] font-semibold text-teal-700">
                        <HeartPulse className="h-3 w-3 text-teal-600" /> Đạm/ngày
                      </div>
                      <div className="font-extrabold text-slate-900 tabular-nums">{target.protein_g} g</div>
                    </div>
                    <div className="rounded-lg border border-sky-100 bg-sky-50/65 px-2.5 py-1.5">
                      <div className="flex items-center gap-1 text-[10px] font-semibold text-sky-700">
                        <Droplets className="h-3 w-3 text-sky-600" /> Natri max
                      </div>
                      <div className="font-extrabold text-sky-800 tabular-nums">
                        {target.sodium_max_mg != null ? `≤ ${target.sodium_max_mg} mg` : 'Theo chuẩn'}
                      </div>
                    </div>
                    <div className="rounded-lg border border-teal-100 bg-teal-50/65 px-2.5 py-1.5">
                      <div className="flex items-center gap-1 text-[10px] font-semibold text-teal-700">
                        <Activity className="h-3 w-3 text-teal-600" /> Kali max
                      </div>
                      <div className="font-extrabold text-teal-800 tabular-nums">
                        {target.potassium_max_mg != null ? `≤ ${target.potassium_max_mg} mg` : 'Theo chuẩn'}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <nav className="space-y-1.5">
              {PATIENT_ITEMS.map(renderNavButton)}
            </nav>
          </>
        )}
      </div>

      {/* Logged-in User & Logout Footer */}
      <div className="relative z-10 p-4 pt-0">
        <div className="flex items-center justify-between gap-2 rounded-xl border border-white/95 bg-white/85 p-3 shadow-2xs backdrop-blur-md">
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span className={`h-2 w-2 shrink-0 rounded-full ${isAdmin ? 'bg-sky-600' : 'bg-teal-500'}`} />
              <span className="truncate text-xs font-extrabold text-slate-900">
                {user?.display_name || user?.username}
              </span>
            </div>
            <div className="truncate text-[10px] font-semibold text-slate-500">
              @{user?.username} • {isAdmin ? 'Quản trị viên' : 'Bệnh nhân'}
            </div>
          </div>

          <button
            type="button"
            onClick={onLogout}
            className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] font-bold text-slate-700 transition hover:border-rose-200 hover:bg-rose-50 hover:text-rose-700"
            title="Đăng xuất"
          >
            <LogOut className="h-3.5 w-3.5" /> Thoát
          </button>
        </div>
      </div>
    </>
  );

  const patientBottomItems = PATIENT_ITEMS.filter((it) => PATIENT_BOTTOM_IDS.includes(it.id));

  return (
    <>
      {/* 1. MOBILE TOP BAR (< lg) */}
      <header className="sticky top-0 z-30 flex items-center justify-between gap-2 border-b border-sky-200/80 bg-[#e4f4fe]/90 px-3.5 py-2.5 backdrop-blur-xl lg:hidden">
        <div className="flex min-w-0 items-center gap-2.5">
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-white/90 bg-white/85 text-slate-700 shadow-2xs active:scale-95"
            aria-label="Mở menu điều hướng"
          >
            <Menu className="h-4.5 w-4.5" />
          </button>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="text-sm font-extrabold tracking-tight text-slate-900">NutriGuard AI</span>
              {!isAdmin && target?.regime_code && (
                <span className="rounded-full border border-sky-200 bg-white px-2 py-0.5 text-[10px] font-extrabold text-sky-700">
                  {target.regime_code}
                </span>
              )}
            </div>
            <div className="truncate text-[11px] font-semibold text-teal-800">{currentTabLabel}</div>
          </div>
        </div>

        <button
          type="button"
          onClick={onLogout}
          className="inline-flex shrink-0 items-center gap-1 rounded-xl border border-white/90 bg-white/85 px-2.5 py-1.5 text-[11px] font-bold text-slate-700 shadow-2xs"
          title="Đăng xuất"
        >
          <LogOut className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Thoát</span>
        </button>
      </header>

      {/* 2. MOBILE SLIDE-OVER DRAWER (< lg) */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 flex lg:hidden">
          <div
            className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs"
            onClick={() => setMobileOpen(false)}
          />
          <aside
            className="relative z-10 flex h-full w-[84vw] max-w-[310px] flex-col justify-between overflow-hidden border-r border-sky-200/80 text-slate-800 shadow-2xl"
            style={SIDEBAR_BG_STYLE}
          >
            {renderSidebarInner(true)}
          </aside>
        </div>
      )}

      {/* 3. DESKTOP SIDEBAR (>= lg) */}
      <aside
        className="relative hidden w-74 shrink-0 flex-col justify-between overflow-hidden border-r border-sky-200/80 text-slate-800 backdrop-blur-2xl lg:sticky lg:top-0 lg:flex lg:h-screen"
        style={SIDEBAR_BG_STYLE}
      >
        {renderSidebarInner(false)}
      </aside>

      {/* 4. MOBILE BOTTOM NAVIGATION BAR (< lg) */}
      <nav className="fixed inset-x-0 bottom-0 z-30 border-t border-slate-200/90 bg-white/95 px-1.5 py-1.5 shadow-[0_-4px_20px_rgba(15,23,42,0.06)] backdrop-blur-xl lg:hidden">
        {isAdmin ? (
          <div className="grid grid-cols-5 gap-1">
            {ADMIN_BOTTOM_ITEMS.map(({ id, shortLabel, icon: Icon }) => {
              const active = activeTab === id;
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => handleSelectTab(id)}
                  className={`flex flex-col items-center justify-center gap-0.5 rounded-xl py-1.5 text-[10px] font-bold transition ${
                    active ? 'bg-sky-50 text-sky-700' : 'text-slate-500'
                  }`}
                >
                  <Icon className={`h-4 w-4 ${active ? 'text-sky-600' : 'text-slate-400'}`} />
                  <span className="truncate max-w-full px-0.5">{shortLabel}</span>
                </button>
              );
            })}
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="flex flex-col items-center justify-center gap-0.5 rounded-xl py-1.5 text-[10px] font-bold text-slate-500"
            >
              <Menu className="h-4 w-4 text-slate-400" />
              <span>Thêm</span>
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-5 gap-1">
            {patientBottomItems.map(({ id, shortLabel, icon: Icon }) => {
              const active = activeTab === id;
              return (
                <button
                  key={id}
                  type="button"
                  onClick={() => handleSelectTab(id)}
                  className={`flex flex-col items-center justify-center gap-0.5 rounded-xl py-1.5 text-[10px] font-bold transition ${
                    active ? 'bg-sky-50 text-sky-700' : 'text-slate-500'
                  }`}
                >
                  <Icon className={`h-4 w-4 ${active ? 'text-sky-600' : 'text-slate-400'}`} />
                  <span className="truncate max-w-full px-0.5">{shortLabel}</span>
                </button>
              );
            })}
          </div>
        )}
      </nav>
    </>
  );
}
