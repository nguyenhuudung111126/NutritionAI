import { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { api, getAuthToken, setAuthToken, setUnauthorizedHandler } from './api';
import Sidebar from './components/Sidebar';
import AdminAccountPage from './pages/AdminAccountPage';
import AdminCatalogPage from './pages/AdminCatalogPage';
import AdminDocumentsPage from './pages/AdminDocumentsPage';
import AdminFoodsPage from './pages/AdminFoodsPage';
import AdminOverviewPage from './pages/AdminOverviewPage';
import AdminPatientsPage from './pages/AdminPatientsPage';
import AssistantPage from './pages/AssistantPage';
import FoodsPage from './pages/FoodsPage';
import LoginPage from './pages/LoginPage';
import MealPlanPage from './pages/MealPlanPage';
import OverviewPage from './pages/OverviewPage';
import ProfilePage from './pages/ProfilePage';
import SystemPage from './pages/SystemPage';
import TrendsPage from './pages/TrendsPage';

export default function App() {
  const [user, setUser] = useState(null);
  const [authChecking, setAuthChecking] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  const [patients, setPatients] = useState([]);
  const [selectedPatientId, setSelectedPatientId] = useState('');
  const [overview, setOverview] = useState(null);

  const isAdmin = user?.role === 'ADMIN';

  const handleLogout = () => {
    setAuthToken('');
    setUser(null);
    setPatients([]);
    setSelectedPatientId('');
    setOverview(null);
    setActiveTab('overview');
  };

  useEffect(() => {
    setUnauthorizedHandler(() => {
      handleLogout();
    });
  }, []);

  useEffect(() => {
    const token = getAuthToken();
    if (!token) {
      setAuthChecking(false);
      return;
    }
    api
      .me()
      .then((res) => {
        setUser(res.user);
        setActiveTab(res.user?.role === 'ADMIN' ? 'admin-overview' : 'overview');
      })
      .catch(() => {
        setAuthToken('');
        setUser(null);
      })
      .finally(() => setAuthChecking(false));
  }, []);

  const loadPatientData = async (currentUser = user) => {
    if (!currentUser || currentUser.role !== 'PATIENT') return;
    const list = await api.getPatients();
    setPatients(list);
    const ownId = currentUser.patient_id || list[0]?.id || '';
    setSelectedPatientId(ownId);
  };

  const loadOverview = async (pid) => {
    if (!pid) {
      setOverview(null);
      return;
    }
    const data = await api.getOverview(pid);
    setOverview(data);
  };

  useEffect(() => {
    if (user?.role === 'PATIENT') {
      loadPatientData(user).catch(() => {});
    }
  }, [user]);

  useEffect(() => {
    if (user?.role === 'PATIENT' && selectedPatientId) {
      loadOverview(selectedPatientId).catch(() => {});
    } else {
      setOverview(null);
    }
  }, [user, selectedPatientId]);

  const handleLoginSuccess = (loggedUser) => {
    setUser(loggedUser);
    setSelectedPatientId(loggedUser.role === 'PATIENT' ? loggedUser.patient_id || '' : '');
    setActiveTab(loggedUser.role === 'ADMIN' ? 'admin-overview' : 'overview');
  };

  if (authChecking) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="flex items-center gap-2.5 rounded-2xl border border-white/90 bg-white/90 px-5 py-3.5 text-sm font-bold text-slate-700 shadow-lg">
          <Loader2 className="h-5 w-5 animate-spin text-sky-600" />
          Đang kiểm tra phiên đăng nhập...
        </div>
      </div>
    );
  }

  if (!user) {
    return <LoginPage onLoginSuccess={handleLoginSuccess} />;
  }

  const activePatient = patients.find((p) => p.id === selectedPatientId);

  return (
    <div className="min-h-screen flex flex-col lg:flex-row">
      <Sidebar
        user={user}
        onLogout={handleLogout}
        activeTab={activeTab}
        onChangeTab={setActiveTab}
        overview={overview}
      />

      <div className="flex-1 flex flex-col min-w-0">
        <main className="mx-auto w-full max-w-6xl flex-1 px-3.5 pt-4 pb-24 sm:px-5 sm:py-7 lg:pb-7">
          {isAdmin ? (
            <>
              {activeTab === 'admin-overview' && <AdminOverviewPage onNavigate={setActiveTab} />}
              {activeTab === 'admin-foods' && <AdminFoodsPage />}
              {activeTab === 'admin-diseases' && <AdminCatalogPage />}
              {activeTab === 'admin-documents' && <AdminDocumentsPage />}
              {activeTab === 'admin-patients' && <AdminPatientsPage currentUser={user} />}
              {activeTab === 'admin-audit' && <SystemPage mode="audit" />}
              {activeTab === 'admin-evals' && <SystemPage mode="evals" />}
              {activeTab === 'admin-account' && <AdminAccountPage user={user} />}
            </>
          ) : patients.length === 0 ? (
            <div className="rounded-2xl border border-amber-200 bg-white/95 p-8 text-center shadow-xs space-y-2">
              <h2 className="text-lg font-extrabold text-slate-900">Tài khoản chưa được gắn Hồ sơ Bệnh nhân</h2>
              <p className="text-xs text-slate-600">
                Vui lòng liên hệ Quản trị viên để gắn tài khoản <strong>@{user.username}</strong> với hồ sơ bệnh án của bạn.
              </p>
            </div>
          ) : (
            <>
              {activeTab === 'overview' && (
                <OverviewPage overview={overview} onNavigate={setActiveTab} />
              )}
              {activeTab === 'profile' && (
                <ProfilePage
                  overview={overview}
                  isAdmin={false}
                  onCreatedPatient={() => {}}
                  onUpdatedPatient={() => loadOverview(selectedPatientId)}
                />
              )}
              {activeTab === 'meal-plan' && (
                <MealPlanPage patientId={selectedPatientId} overview={overview} />
              )}
              {activeTab === 'foods' && <FoodsPage patientId={selectedPatientId} />}
              {activeTab === 'assistant' && (
                <AssistantPage
                  patientId={selectedPatientId}
                  patientName={activePatient?.nickname || 'Bệnh nhân'}
                />
              )}
              {activeTab === 'trends' && (
                <TrendsPage
                  patientId={selectedPatientId}
                  onDeletedCheckup={() => loadOverview(selectedPatientId)}
                />
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
