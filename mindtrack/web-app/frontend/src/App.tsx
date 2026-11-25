import React, { useCallback, useEffect, useState } from "react";
import {
  Activity,
  BarChart3,
  ClipboardList,
  History,
  LayoutDashboard,
  Menu,
  Mic,
  PlusCircle,
  ScanFace,
  Settings,
  X,
} from "lucide-react";
import { ToastBanner } from "./components/SharedUI";
import { DashboardPage, type NavPage } from "./pages/DashboardPage";
import { NewCheckinPage } from "./pages/NewCheckinPage";
import { QuestionnairePage } from "./pages/QuestionnairePage";
import { FaceAiPage } from "./pages/FaceAiPage";
import { VoiceAiPage } from "./pages/VoiceAiPage";
import { BaselinesPage } from "./pages/BaselinesPage";
import { HistoryPage } from "./pages/HistoryPage";
import { SettingsPage } from "./pages/SettingsPage";
import {
  fetchDashboard,
  fetchBaselines,
  fetchCheckins,
  fetchRecentRuns,
  fetchUsers,
} from "./services/api";
import type {
  AnalysisRunResponse,
  BaselinesResponse,
  CheckinSession,
  DashboardResponse,
  FaceAnalysisResult,
  UserProfile,
  VoiceAnalysisResult,
} from "./types/mindtrack";

const NAV_ITEMS: { page: NavPage; label: string; icon: React.ReactNode }[] = [
  { page: "dashboard", label: "Dashboard", icon: <LayoutDashboard className="h-5 w-5" /> },
  { page: "checkin", label: "New Check-in", icon: <PlusCircle className="h-5 w-5" /> },
  { page: "questionnaire", label: "Questionnaire", icon: <ClipboardList className="h-5 w-5" /> },
  { page: "face", label: "Facial AI", icon: <ScanFace className="h-5 w-5" /> },
  { page: "voice", label: "Voice AI", icon: <Mic className="h-5 w-5" /> },
  { page: "baselines", label: "Baselines & Trends", icon: <BarChart3 className="h-5 w-5" /> },
  { page: "history", label: "Check-in History", icon: <History className="h-5 w-5" /> },
  { page: "settings", label: "Settings", icon: <Settings className="h-5 w-5" /> },
];

export default function App() {
  const [page, setPage] = useState<NavPage>("dashboard");
  const [userId, setUserId] = useState("demo_user");
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [loading, setLoading] = useState(true);

  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [baselines, setBaselines] = useState<BaselinesResponse | null>(null);
  const [checkins, setCheckins] = useState<CheckinSession[]>([]);
  const [faceRuns, setFaceRuns] = useState<AnalysisRunResponse<FaceAnalysisResult>[]>([]);
  const [voiceRuns, setVoiceRuns] = useState<AnalysisRunResponse<VoiceAnalysisResult>[]>([]);

  const [toast, setToast] = useState<{ type: "success" | "error" | "info"; text: string } | null>(null);

  const notify = useCallback((type: "success" | "error" | "info", text: string) => {
    setToast({ type, text });
    setTimeout(() => setToast(null), 5000);
  }, []);

  const refreshAll = useCallback(async () => {
    setLoading(true);
    try {
      const [dash, bases, cks, fRuns, vRuns, usrs] = await Promise.allSettled([
        fetchDashboard(userId),
        fetchBaselines(userId),
        fetchCheckins(userId),
        fetchRecentRuns<FaceAnalysisResult>(userId, "FACE"),
        fetchRecentRuns<VoiceAnalysisResult>(userId, "VOICE"),
        fetchUsers(),
      ]);
      if (dash.status === "fulfilled") setDashboard(dash.value);
      if (bases.status === "fulfilled") setBaselines(bases.value);
      if (cks.status === "fulfilled") setCheckins(cks.value);
      if (fRuns.status === "fulfilled") setFaceRuns(fRuns.value as AnalysisRunResponse<FaceAnalysisResult>[]);
      if (vRuns.status === "fulfilled") setVoiceRuns(vRuns.value as AnalysisRunResponse<VoiceAnalysisResult>[]);
      if (usrs.status === "fulfilled") setUsers(usrs.value);
    } catch {
      // individual promises are allSettled so this won't fire
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  const handleNavigate = useCallback((p: NavPage) => {
    setPage(p);
    setSidebarOpen(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, []);

  const renderPage = () => {
    switch (page) {
      case "dashboard":
        return <DashboardPage dashboard={dashboard} loading={loading} onNavigate={handleNavigate} />;
      case "checkin":
        return (
          <NewCheckinPage
            userId={userId}
            baselines={baselines}
            onCheckinSaved={refreshAll}
            onNavigate={handleNavigate}
            onNotify={notify}
          />
        );
      case "questionnaire":
        return (
          <QuestionnairePage
            userId={userId}
            checkins={checkins}
            onSaved={refreshAll}
            onNotify={notify}
          />
        );
      case "face":
        return (
          <FaceAiPage
            userId={userId}
            baselines={baselines}
            recentRuns={faceRuns}
            onRefresh={refreshAll}
            onNotify={notify}
          />
        );
      case "voice":
        return (
          <VoiceAiPage
            userId={userId}
            baselines={baselines}
            recentRuns={voiceRuns}
            onRefresh={refreshAll}
            onNotify={notify}
          />
        );
      case "baselines":
        return (
          <BaselinesPage
            userId={userId}
            baselines={baselines}
            checkins={checkins}
            onRefresh={refreshAll}
            onNotify={notify}
          />
        );
      case "history":
        return (
          <HistoryPage
            userId={userId}
            checkins={checkins}
            onRefresh={refreshAll}
            onNavigate={handleNavigate}
            onNotify={notify}
          />
        );
      case "settings":
        return (
          <SettingsPage
            userId={userId}
            users={users}
            onUserChange={(id) => { setUserId(id); }}
            onRefresh={refreshAll}
            onNotify={notify}
          />
        );
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/30 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-slate-200/80 bg-white/95 backdrop-blur-md transition-transform duration-200 lg:relative lg:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Logo */}
        <div className="flex items-center justify-between px-5 py-5 border-b border-slate-100">
          <div className="flex items-center gap-2.5">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-sky-500 to-teal-500 flex items-center justify-center shadow-sm">
              <Activity className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-slate-900 leading-none">MindTrack</h1>
              <p className="text-[10px] font-medium text-slate-400 leading-none mt-0.5">Wellness Research Tool</p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setSidebarOpen(false)}
            className="lg:hidden rounded-lg p-1 hover:bg-slate-100"
          >
            <X className="h-5 w-5 text-slate-500" />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          {NAV_ITEMS.map((item) => {
            const active = page === item.page;
            return (
              <button
                key={item.page}
                type="button"
                onClick={() => handleNavigate(item.page)}
                className={`w-full flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-medium transition-all ${
                  active
                    ? "bg-gradient-to-r from-sky-50 to-teal-50 text-sky-700 border border-sky-200/70 shadow-sm"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                }`}
              >
                {item.icon}
                {item.label}
              </button>
            );
          })}
        </nav>

        {/* Profile selector */}
        <div className="border-t border-slate-100 px-4 py-4">
          <label className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-1 block">
            Active Profile
          </label>
          <select
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-sky-200"
          >
            {users.length === 0 ? (
              <option value={userId}>{userId}</option>
            ) : (
              users.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.fullName} ({u.id})
                </option>
              ))
            )}
          </select>
        </div>
      </aside>

      {/* Main content area */}
      <div className="flex-1 flex flex-col min-h-screen">
        {/* Mobile top bar */}
        <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-slate-200/80 bg-white/90 backdrop-blur-md px-4 py-3 lg:hidden">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className="rounded-lg p-1.5 hover:bg-slate-100"
          >
            <Menu className="h-5 w-5 text-slate-700" />
          </button>
          <div className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-sky-600" />
            <span className="text-sm font-bold text-slate-900">MindTrack</span>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 px-4 sm:px-6 lg:px-8 py-6 lg:py-8 max-w-7xl w-full mx-auto">
          <React.Fragment key={userId}>{renderPage()}</React.Fragment>
        </main>
      </div>

      <ToastBanner toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}
