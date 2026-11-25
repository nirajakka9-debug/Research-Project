import React, { useState } from "react";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  RefreshCw,
  RotateCcw,
  ScanFace,
  Mic,
  TrendingUp,
} from "lucide-react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { resetBaseline } from "../services/api";
import type { BaselinesResponse, CheckinSession } from "../types/mindtrack";
import { EmptyStateCard, NonDiagnosticBanner } from "../components/SharedUI";

interface BaselinesPageProps {
  userId: string;
  baselines: BaselinesResponse | null;
  checkins: CheckinSession[];
  onRefresh: () => void;
  onNotify: (type: "success" | "error" | "info", text: string) => void;
}

const FACE_FEATURE_LABELS: Record<string, string> = {
  facialMovementVelocity: "Facial Movement Velocity",
  eyeBlinkRatePm: "Eye Blink Rate (blinks/min)",
  headPoseJitterStd: "Head Pose Jitter Std",
  smileIntensityProxy: "Smile Intensity Proxy",
  browFurrowProxy: "Brow Furrow Proxy",
};

const VOICE_FEATURE_LABELS: Record<string, string> = {
  speakingRateWpm: "Speaking Rate (WPM)",
  pitchMeanHz: "Pitch Mean (Hz)",
  pitchStdDevHz: "Pitch Std Dev (Hz)",
  meanPauseDurationMs: "Mean Pause Duration (ms)",
  speechRatio: "Speech Ratio",
  energyMeanRms: "Energy Mean (RMS)",
  totalPauseCount: "Total Pause Count",
  longestPauseDurationMs: "Longest Pause (ms)",
  speechDurationSec: "Speech Duration (s)",
  silenceDurationSec: "Silence Duration (s)",
  pitchRangeHz: "Pitch Range (Hz)",
  energyStdDev: "Energy Std Dev",
};

const CHART_COLORS = ["#0284c7", "#0d9488", "#7c3aed", "#f59e0b", "#ec4899"];

export const BaselinesPage: React.FC<BaselinesPageProps> = ({
  userId,
  baselines,
  checkins,
  onRefresh,
  onNotify,
}) => {
  const [resetting, setResetting] = useState<string | null>(null);

  const handleReset = async (modality: "face" | "voice") => {
    if (!confirm(`Reset your ${modality} baseline? This will require re-calibration.`)) return;
    setResetting(modality);
    try {
      await resetBaseline(userId, modality);
      onNotify("success", `${modality === "face" ? "Facial" : "Voice"} baseline reset. Re-calibrate by running new sessions in "calibrate" mode.`);
      onRefresh();
    } catch (err) {
      onNotify("error", err instanceof Error ? err.message : "Failed to reset baseline.");
    } finally {
      setResetting(null);
    }
  };

  const fb = baselines?.face;
  const vb = baselines?.voice;
  const qb = baselines?.questionnaire;

  /* Build trend data from checkins */
  const faceTrendData = checkins
    .filter((c) => c.face !== null)
    .map((c) => ({
      label: new Date(c.sessionTimestamp).toLocaleDateString(),
      timestamp: c.sessionTimestamp,
      facialMovementVelocity: c.face!.features.facialMovementVelocity,
      eyeBlinkRatePm: c.face!.features.eyeBlinkRatePm,
      smileIntensityProxy: c.face!.features.smileIntensityProxy,
    }))
    .reverse();

  const voiceTrendData = checkins
    .filter((c) => c.voice !== null)
    .map((c) => ({
      label: new Date(c.sessionTimestamp).toLocaleDateString(),
      timestamp: c.sessionTimestamp,
      speakingRateWpm: c.voice!.features.speakingRateWpm,
      pitchMeanHz: c.voice!.features.pitchMeanHz,
      speechRatio: c.voice!.features.speechRatio,
    }))
    .reverse();

  const qTrendData = checkins
    .filter((c) => c.questionnaire !== null)
    .map((c) => ({
      label: new Date(c.sessionTimestamp).toLocaleDateString(),
      mood: c.questionnaire!.dailyAffectMood,
      energy: c.questionnaire!.dailyAffectEnergy,
      stress: c.questionnaire!.dailyAffectStress,
    }))
    .reverse();

  if (!baselines) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-10 w-64 rounded-xl bg-slate-200/70" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => <div key={i} className="h-48 rounded-2xl bg-slate-200/70" />)}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2">
            <BarChart3 className="h-6 w-6 text-sky-600" />
            Baselines &amp; Trends
          </h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Personal empirical baselines and longitudinal feature trends for {userId}
          </p>
        </div>
        <button
          type="button"
          onClick={onRefresh}
          className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 transition"
        >
          <RefreshCw className="h-4 w-4" /> Refresh
        </button>
      </div>

      <NonDiagnosticBanner compact />

      {/* Calibration progress cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Face baseline card */}
        <div className="wellness-card p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
              <ScanFace className="h-5 w-5 text-teal-600" /> Facial Baseline
            </span>
            <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${fb?.is_calibrated ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>
              {fb?.is_calibrated ? "Calibrated" : "Calibrating"}
            </span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-2.5">
            <div
              className="h-2.5 rounded-full bg-gradient-to-r from-teal-400 to-teal-600 transition-all"
              style={{ width: `${Math.min(100, ((fb?.total_checkins_recorded ?? 0) / (fb?.min_calibration_checkins ?? 5)) * 100)}%` }}
            />
          </div>
          <p className="text-xs text-slate-500">
            {fb?.total_checkins_recorded ?? 0} / {fb?.min_calibration_checkins ?? 5} calibration sessions
          </p>
          {(fb?.exists || (fb?.total_checkins_recorded ?? 0) > 0) && (
            <button
              type="button"
              onClick={() => handleReset("face")}
              disabled={resetting === "face"}
              className="mt-1 inline-flex items-center gap-1.5 text-xs font-semibold text-rose-600 hover:text-rose-700 disabled:opacity-50"
            >
              <RotateCcw className="h-3.5 w-3.5" /> {resetting === "face" ? "Resetting…" : "Reset Baseline"}
            </button>
          )}
        </div>

        {/* Voice baseline card */}
        <div className="wellness-card p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
              <Mic className="h-5 w-5 text-violet-600" /> Voice Baseline
            </span>
            <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${vb?.is_established ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>
              {vb?.is_established ? "Established" : "Calibrating"}
            </span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-2.5">
            <div
              className="h-2.5 rounded-full bg-gradient-to-r from-violet-400 to-violet-600 transition-all"
              style={{ width: `${Math.min(100, ((vb?.observation_count ?? 0) / (vb?.min_observations ?? 3)) * 100)}%` }}
            />
          </div>
          <p className="text-xs text-slate-500">
            {vb?.observation_count ?? 0} / {vb?.min_observations ?? 3} calibration observations
          </p>
          {(vb?.exists || (vb?.observation_count ?? 0) > 0) && (
            <button
              type="button"
              onClick={() => handleReset("voice")}
              disabled={resetting === "voice"}
              className="mt-1 inline-flex items-center gap-1.5 text-xs font-semibold text-rose-600 hover:text-rose-700 disabled:opacity-50"
            >
              <RotateCcw className="h-3.5 w-3.5" /> {resetting === "voice" ? "Resetting…" : "Reset Baseline"}
            </button>
          )}
        </div>

        {/* Questionnaire stats card */}
        <div className="wellness-card p-5 space-y-3">
          <div className="flex items-center justify-between">
            <span className="inline-flex items-center gap-2 text-sm font-semibold text-slate-900">
              <Activity className="h-5 w-5 text-sky-600" /> Questionnaire Stats
            </span>
            <span className="text-xs font-bold text-sky-700 bg-sky-50 px-2 py-0.5 rounded-full">
              {qb?.sessionCount ?? 0} sessions
            </span>
          </div>
          {qb && Object.keys(qb.stats).length > 0 ? (
            <div className="space-y-1.5">
              {Object.entries(qb.stats).map(([key, stat]) => (
                <div key={key} className="flex justify-between text-xs">
                  <span className="text-slate-600 capitalize">{key.replace(/([A-Z])/g, " $1").trim()}</span>
                  <span className="font-semibold text-slate-800">
                    μ={stat.mean?.toFixed(2) ?? "—"} σ={stat.std?.toFixed(2) ?? "—"}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-slate-400">No questionnaire data recorded yet.</p>
          )}
        </div>
      </div>

      {/* Face feature stats table */}
      {fb && Object.keys(fb.feature_stats).length > 0 && (
        <div className="wellness-card p-5 space-y-3">
          <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
            <ScanFace className="h-4 w-4 text-teal-600" /> Facial Feature Baseline Statistics
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-left text-slate-500">
                  <th className="pb-2 pr-4 font-medium">Feature</th>
                  <th className="pb-2 pr-4 font-medium text-right">Count</th>
                  <th className="pb-2 pr-4 font-medium text-right">Mean</th>
                  <th className="pb-2 pr-4 font-medium text-right">Std Dev</th>
                  <th className="pb-2 pr-4 font-medium text-right">Min</th>
                  <th className="pb-2 font-medium text-right">Max</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(fb.feature_stats).map(([key, stat]) => (
                  <tr key={key} className="border-b border-slate-100">
                    <td className="py-2 pr-4 font-medium text-slate-700">{FACE_FEATURE_LABELS[key] ?? key}</td>
                    <td className="py-2 pr-4 text-right text-slate-600">{stat.count}</td>
                    <td className="py-2 pr-4 text-right font-semibold text-slate-800">{stat.mean?.toFixed(4) ?? "—"}</td>
                    <td className="py-2 pr-4 text-right text-slate-600">{stat.std?.toFixed(4) ?? "—"}</td>
                    <td className="py-2 pr-4 text-right text-slate-600">{stat.min?.toFixed(4) ?? "—"}</td>
                    <td className="py-2 text-right text-slate-600">{stat.max?.toFixed(4) ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Voice feature stats table */}
      {vb && Object.keys(vb.stats).length > 0 && (
        <div className="wellness-card p-5 space-y-3">
          <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
            <Mic className="h-4 w-4 text-violet-600" /> Voice Feature Baseline Statistics
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-left text-slate-500">
                  <th className="pb-2 pr-4 font-medium">Feature</th>
                  <th className="pb-2 pr-4 font-medium text-right">Count</th>
                  <th className="pb-2 pr-4 font-medium text-right">Mean</th>
                  <th className="pb-2 pr-4 font-medium text-right">Std Dev</th>
                  <th className="pb-2 pr-4 font-medium text-right">Min</th>
                  <th className="pb-2 font-medium text-right">Max</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(vb.stats).map(([key, stat]) => (
                  <tr key={key} className="border-b border-slate-100">
                    <td className="py-2 pr-4 font-medium text-slate-700">{VOICE_FEATURE_LABELS[key] ?? key}</td>
                    <td className="py-2 pr-4 text-right text-slate-600">{stat.count}</td>
                    <td className="py-2 pr-4 text-right font-semibold text-slate-800">{stat.mean?.toFixed(4) ?? "—"}</td>
                    <td className="py-2 pr-4 text-right text-slate-600">{stat.std?.toFixed(4) ?? "—"}</td>
                    <td className="py-2 pr-4 text-right text-slate-600">{stat.min?.toFixed(4) ?? "—"}</td>
                    <td className="py-2 text-right text-slate-600">{stat.max?.toFixed(4) ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Trend charts */}
      {qTrendData.length > 0 && (
        <div className="wellness-card p-5 space-y-4">
          <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-sky-600" /> Self-Report Trends (Mood / Energy / Stress)
          </h3>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={qTrendData} margin={{ top: 8, right: 16, left: -12, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#64748b" }} />
                <YAxis domain={[0, 5]} tick={{ fontSize: 11, fill: "#64748b" }} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: "12px" }} />
                <Line type="monotone" dataKey="mood" name="Mood (1–5)" stroke="#0284c7" strokeWidth={2.5} dot={{ r: 4 }} connectNulls={false} />
                <Line type="monotone" dataKey="energy" name="Energy (1–5)" stroke="#0d9488" strokeWidth={2.5} dot={{ r: 4 }} connectNulls={false} />
                <Line type="monotone" dataKey="stress" name="Strain (1–5)" stroke="#7c3aed" strokeWidth={2.5} dot={{ r: 4 }} connectNulls={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {faceTrendData.length > 0 && (
        <div className="wellness-card p-5 space-y-4">
          <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
            <ScanFace className="h-4 w-4 text-teal-600" /> Facial Feature Trends
          </h3>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={faceTrendData} margin={{ top: 8, right: 16, left: -12, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#64748b" }} />
                <YAxis tick={{ fontSize: 11, fill: "#64748b" }} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: "12px" }} />
                <Line type="monotone" dataKey="eyeBlinkRatePm" name="Blink Rate (bpm)" stroke={CHART_COLORS[0]} strokeWidth={2} dot={{ r: 3 }} connectNulls={false} />
                <Line type="monotone" dataKey="facialMovementVelocity" name="Movement Velocity" stroke={CHART_COLORS[1]} strokeWidth={2} dot={{ r: 3 }} connectNulls={false} />
                <Line type="monotone" dataKey="smileIntensityProxy" name="Smile Intensity" stroke={CHART_COLORS[2]} strokeWidth={2} dot={{ r: 3 }} connectNulls={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {voiceTrendData.length > 0 && (
        <div className="wellness-card p-5 space-y-4">
          <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
            <Mic className="h-4 w-4 text-violet-600" /> Voice Feature Trends
          </h3>
          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={voiceTrendData} margin={{ top: 8, right: 16, left: -12, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="label" tick={{ fontSize: 11, fill: "#64748b" }} />
                <YAxis tick={{ fontSize: 11, fill: "#64748b" }} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: "12px" }} />
                <Line type="monotone" dataKey="speakingRateWpm" name="Speaking Rate (WPM)" stroke={CHART_COLORS[0]} strokeWidth={2} dot={{ r: 3 }} connectNulls={false} />
                <Line type="monotone" dataKey="pitchMeanHz" name="Pitch Mean (Hz)" stroke={CHART_COLORS[2]} strokeWidth={2} dot={{ r: 3 }} connectNulls={false} />
                <Line type="monotone" dataKey="speechRatio" name="Speech Ratio" stroke={CHART_COLORS[3]} strokeWidth={2} dot={{ r: 3 }} connectNulls={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Empty state when no trends at all */}
      {qTrendData.length === 0 && faceTrendData.length === 0 && voiceTrendData.length === 0 && (
        <EmptyStateCard
          title="No Trend Data Available"
          description="Complete check-ins to build longitudinal trend data. Each modality (questionnaire, facial video, voice recording) tracks independently."
          icon={<TrendingUp className="h-6 w-6" />}
        />
      )}

      {/* Warning about not resetting */}
      <div className="rounded-xl border border-amber-200/80 bg-amber-50/70 p-4 flex items-start gap-3 text-xs text-amber-800">
        <AlertTriangle className="h-4 w-4 mt-0.5 shrink-0 text-amber-600" />
        <div>
          <p className="font-semibold">About Baselines</p>
          <p className="mt-0.5 leading-relaxed">
            Baselines are computed from your personal calibration sessions. Resetting a baseline deletes the saved
            profile and requires re-calibration. Face requires {fb?.min_calibration_checkins ?? 5} sessions and voice
            requires {vb?.min_observations ?? 3} observations to establish a stable baseline.
          </p>
        </div>
      </div>
    </div>
  );
};
