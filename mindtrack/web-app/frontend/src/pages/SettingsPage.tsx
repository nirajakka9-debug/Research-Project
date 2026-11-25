import React, { useEffect, useState } from "react";
import {
  Activity,
  AlertCircle,
  CheckCircle2,
  Loader2,
  Plus,
  RefreshCw,
  Server,
  Settings,
  User,
} from "lucide-react";
import { createUser, fetchHealth } from "../services/api";
import type { HealthStatus, UserProfile } from "../types/mindtrack";
import { NonDiagnosticBanner } from "../components/SharedUI";

interface SettingsPageProps {
  userId: string;
  users: UserProfile[];
  onUserChange: (id: string) => void;
  onRefresh: () => void;
  onNotify: (type: "success" | "error" | "info", text: string) => void;
}

export const SettingsPage: React.FC<SettingsPageProps> = ({
  userId,
  users,
  onUserChange,
  onRefresh,
  onNotify,
}) => {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);

  const [newId, setNewId] = useState("");
  const [newName, setNewName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [creating, setCreating] = useState(false);

  const checkHealth = async () => {
    setHealthLoading(true);
    try {
      const h = await fetchHealth();
      setHealth(h);
    } catch {
      setHealth(null);
      onNotify("error", "Could not reach the MindTrack backend.");
    } finally {
      setHealthLoading(false);
    }
  };

  useEffect(() => {
    checkHealth();
  }, []);

  const handleCreateUser = async () => {
    if (!newId.trim() || !newName.trim()) {
      onNotify("error", "User ID and Full Name are required.");
      return;
    }
    setCreating(true);
    try {
      await createUser({ id: newId.trim(), fullName: newName.trim(), email: newEmail.trim() || `${newId.trim()}@mindtrack.local` });
      onNotify("success", `User "${newId.trim()}" created.`);
      setNewId("");
      setNewName("");
      setNewEmail("");
      onRefresh();
    } catch (err) {
      onNotify("error", err instanceof Error ? err.message : "Failed to create user.");
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
          <Settings className="h-6 w-6 text-sky-600" /> Settings
        </h2>
        <p className="text-sm text-slate-500 mt-0.5">
          Manage profiles, check backend connectivity, and configure MindTrack
        </p>
      </div>

      <NonDiagnosticBanner compact />

      {/* Backend health */}
      <div className="wellness-card p-5 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
            <Server className="h-4 w-4 text-slate-500" /> Backend Service Status
          </h3>
          <button
            type="button"
            onClick={checkHealth}
            disabled={healthLoading}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            {healthLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
            Check
          </button>
        </div>

        {health ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 text-xs">
            <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-3">
              <div className="text-slate-500 mb-1">Service</div>
              <div className="font-bold text-slate-900">{health.service}</div>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-3">
              <div className="text-slate-500 mb-1">Status</div>
              <div className="flex items-center gap-1.5">
                {health.status === "UP" ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                ) : (
                  <AlertCircle className="h-4 w-4 text-rose-600" />
                )}
                <span className="font-bold text-slate-900">{health.status}</span>
              </div>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-3">
              <div className="text-slate-500 mb-1">Face AI</div>
              <div className="flex items-center gap-1.5">
                {health.faceAiAvailable ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                ) : (
                  <AlertCircle className="h-4 w-4 text-amber-500" />
                )}
                <span className="font-bold text-slate-900">{health.faceAiAvailable ? "Available" : "Unavailable"}</span>
              </div>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50/70 p-3">
              <div className="text-slate-500 mb-1">Voice AI</div>
              <div className="flex items-center gap-1.5">
                {health.voiceAiAvailable ? (
                  <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                ) : (
                  <AlertCircle className="h-4 w-4 text-amber-500" />
                )}
                <span className="font-bold text-slate-900">{health.voiceAiAvailable ? "Available" : "Unavailable"}</span>
              </div>
            </div>
          </div>
        ) : (
          <div className="rounded-lg bg-rose-50 border border-rose-200 p-3 text-xs text-rose-800 flex items-start gap-2">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Backend unreachable</p>
              <p className="mt-0.5">Make sure the FastAPI backend is running on port 8080. Start it with:</p>
              <code className="mt-1 block rounded bg-rose-100 p-1.5 font-mono text-[11px]">
                cd mindtrack/web-app/backend &amp;&amp; .venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8080
              </code>
            </div>
          </div>
        )}
      </div>

      {/* Active Profile */}
      <div className="wellness-card p-5 space-y-4">
        <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
          <User className="h-4 w-4 text-slate-500" /> Active Profile
        </h3>
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-xs font-medium text-slate-600 mb-1">Select User</label>
            <select
              value={userId}
              onChange={(e) => onUserChange(e.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-sky-200"
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
        </div>
        {users.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-left text-slate-500">
                  <th className="pb-2 pr-4 font-medium">ID</th>
                  <th className="pb-2 pr-4 font-medium">Name</th>
                  <th className="pb-2 pr-4 font-medium">Email</th>
                  <th className="pb-2 font-medium">Created</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className={`border-b border-slate-100 ${u.id === userId ? "bg-sky-50/50" : ""}`}>
                    <td className="py-2 pr-4 font-semibold text-slate-700">{u.id}</td>
                    <td className="py-2 pr-4 text-slate-600">{u.fullName}</td>
                    <td className="py-2 pr-4 text-slate-600">{u.email}</td>
                    <td className="py-2 text-slate-500">{new Date(u.createdAt).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Create user */}
      <div className="wellness-card p-5 space-y-4">
        <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
          <Plus className="h-4 w-4 text-slate-500" /> Create New Profile
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">User ID</label>
            <input
              type="text"
              value={newId}
              onChange={(e) => setNewId(e.target.value)}
              placeholder="e.g. john_doe"
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-sky-200"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Full Name</label>
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="e.g. John Doe"
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-sky-200"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1">Email (optional)</label>
            <input
              type="email"
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
              placeholder="e.g. john@example.com"
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-sky-200"
            />
          </div>
        </div>
        <button
          type="button"
          onClick={handleCreateUser}
          disabled={creating}
          className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-sky-600 to-teal-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:from-sky-700 hover:to-teal-700 transition disabled:opacity-50"
        >
          {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
          Create Profile
        </button>
      </div>

      {/* About */}
      <div className="wellness-card p-5 space-y-3">
        <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
          <Activity className="h-4 w-4 text-sky-600" /> About MindTrack
        </h3>
        <div className="text-xs text-slate-600 space-y-2 leading-relaxed">
          <p>
            MindTrack is a longitudinal multimodal wellness monitoring research tool. It tracks self-reported
            check-ins, facial behaviour measurements (MediaPipe FaceLandmarker), and voice acoustic features
            (DSP pipeline) relative to your own personal empirical baseline.
          </p>
          <p>
            <strong>Architecture:</strong> React + TypeScript + Vite (frontend) → FastAPI + SQLite (backend) → Python AI adapters
            (Face AI with MediaPipe, Voice AI with DSP/VAD pipeline).
          </p>
          <p className="text-amber-700 font-medium">
            ⚠ MindTrack does not detect, diagnose, or score stress, depression, anxiety, or any medical condition.
            All results reflect objective behavioural measurements compared to your own baseline, not clinical assessments.
          </p>
        </div>
      </div>
    </div>
  );
};
