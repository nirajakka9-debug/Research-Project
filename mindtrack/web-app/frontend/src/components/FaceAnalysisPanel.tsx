import React, { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  FileVideo,
  Info,
  Loader2,
  PlayCircle,
  ScanFace,
  ShieldCheck,
  Upload,
} from "lucide-react";
import { analyzeFaceVideo } from "../services/api";
import type { AnalysisRunResponse, FaceAnalysisResult, OperationalMode } from "../types/mindtrack";
import { JsonInspectorCard } from "./SharedUI";

const ALLOWED_VIDEO_EXTS = [".mp4", ".avi", ".mov", ".mkv", ".webm"];

interface FaceAnalysisPanelProps {
  userId: string;
  baselineProgress?: { recorded: number; minRequired: number; isCalibrated: boolean };
  currentRun: AnalysisRunResponse<FaceAnalysisResult> | null;
  onAnalysisComplete: (run: AnalysisRunResponse<FaceAnalysisResult>) => void;
  onNotify?: (type: "success" | "error" | "info", text: string) => void;
}

export const FaceAnalysisPanel: React.FC<FaceAnalysisPanelProps> = ({
  userId,
  baselineProgress,
  currentRun,
  onAnalysisComplete,
  onNotify,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [videoDurationSec, setVideoDurationSec] = useState<number | null>(null);
  const [maxDuration, setMaxDuration] = useState<number>(30);
  const [mode, setMode] = useState<OperationalMode>("single");
  const [updateBaseline, setUpdateBaseline] = useState<boolean>(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [progress, setProgress] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const handleFilePicked = (file: File | null) => {
    setValidationError(null);
    setApiError(null);
    setVideoDurationSec(null);
    if (!file) return;

    const lower = file.name.toLowerCase();
    const validExt = ALLOWED_VIDEO_EXTS.some((ext) => lower.endsWith(ext));
    if (!validExt) {
      setValidationError(`Unsupported video format. Allowed extensions: ${ALLOWED_VIDEO_EXTS.join(", ")}.`);
      return;
    }
    if (file.size === 0) {
      setValidationError("Selected video file is empty (0 bytes).");
      return;
    }
    if (file.size > 150 * 1024 * 1024) {
      setValidationError("Video file exceeds the 150 MB limit.");
      return;
    }

    if (previewUrl) URL.revokeObjectURL(previewUrl);
    const nextUrl = URL.createObjectURL(file);
    setSelectedFile(file);
    setPreviewUrl(nextUrl);
  };

  const handleAnalyze = async () => {
    if (!selectedFile) {
      setValidationError("Please upload a video file before running facial analysis.");
      return;
    }
    if (videoDurationSec !== null && videoDurationSec > maxDuration) {
      setValidationError(
        `Video duration (${videoDurationSec.toFixed(1)}s) exceeds configured limit (${maxDuration}s).`,
      );
      return;
    }

    setAnalyzing(true);
    setProgress(5);
    setApiError(null);
    try {
      const run = await analyzeFaceVideo({
        file: selectedFile,
        userId,
        mode,
        maxDuration,
        updateBaseline: mode === "assess" && updateBaseline,
        onProgress: setProgress,
      });
      onAnalysisComplete(run);
      if (run.result.calibration_status?.error) {
        onNotify?.("info", `Facial analysis finished, but calibration skipped: ${run.result.calibration_status.error}`);
      } else {
        onNotify?.("success", `Facial analysis completed (${run.result.quality.usable_frames} tracked frames).`);
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Facial analysis failed.";
      setApiError(msg);
      onNotify?.("error", msg);
    } finally {
      setAnalyzing(false);
    }
  };

  const res = currentRun?.result;

  return (
    <div className="space-y-5">
      {/* Configuration & Upload Row */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-7 space-y-4">
          <div
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              handleFilePicked(e.dataTransfer.files?.[0] ?? null);
            }}
            className="cursor-pointer rounded-2xl border-2 border-dashed border-teal-200 bg-teal-50/30 hover:bg-teal-50/60 p-6 text-center transition"
          >
            <input
              ref={inputRef}
              type="file"
              accept=".mp4,.avi,.mov,.mkv,.webm,video/*"
              className="hidden"
              onChange={(e) => handleFilePicked(e.target.files?.[0] ?? null)}
            />
            <div className="mx-auto mb-3 h-11 w-11 rounded-xl bg-teal-100 text-teal-700 flex items-center justify-center">
              <Upload className="h-5 w-5" />
            </div>
            <p className="text-sm font-semibold text-slate-900">
              {selectedFile ? selectedFile.name : "Drop or select a facial check-in video"}
            </p>
            <p className="text-xs text-slate-500 mt-1">
              Supports MP4, AVI, MOV, MKV, WEBM • Up to {maxDuration}s duration • Max 150 MB
            </p>
            {selectedFile && (
              <div className="mt-3 inline-flex flex-wrap items-center gap-2 rounded-full bg-white px-3 py-1 text-xs font-medium text-teal-800 border border-teal-200">
                <FileVideo className="h-3.5 w-3.5" />
                {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB
                {videoDurationSec !== null && ` • ${videoDurationSec.toFixed(1)}s`}
              </div>
            )}
          </div>

          {previewUrl && (
            <div className="rounded-2xl border border-slate-200 bg-slate-950 overflow-hidden">
              <video
                src={previewUrl}
                controls
                onLoadedMetadata={(e) => {
                  const dur = e.currentTarget.duration;
                  if (Number.isFinite(dur)) {
                    setVideoDurationSec(dur);
                    if (dur > maxDuration) {
                      setValidationError(
                        `Video duration (${dur.toFixed(1)}s) exceeds the ${maxDuration}s analyzer limit.`,
                      );
                    }
                  }
                }}
                className="w-full max-h-64 object-contain"
              />
            </div>
          )}
        </div>

        <div className="lg:col-span-5 rounded-2xl border border-slate-200 bg-slate-50/70 p-4 space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
              <ScanFace className="h-4 w-4 text-teal-600" />
              Face AI Analyzer Settings
            </h4>
            {baselineProgress && (
              <span
                className={`wellness-pill text-[11px] ${
                  baselineProgress.isCalibrated
                    ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                    : "bg-amber-50 text-amber-700 border border-amber-200"
                }`}
              >
                Baseline: {baselineProgress.recorded}/{baselineProgress.minRequired}
              </span>
            )}
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">Operational Mode</label>
            <div className="grid grid-cols-3 gap-1.5">
              {(
                [
                  { id: "single", label: "Single", desc: "Features only" },
                  { id: "calibrate", label: "Calibrate", desc: "Add to baseline" },
                  { id: "assess", label: "Assess", desc: "Compare baseline" },
                ] as const
              ).map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => setMode(m.id)}
                  className={`rounded-xl border px-2.5 py-2 text-left transition ${
                    mode === m.id
                      ? "border-teal-600 bg-teal-600 text-white shadow-sm"
                      : "border-slate-200 bg-white text-slate-700 hover:bg-slate-100"
                  }`}
                >
                  <div className="text-xs font-semibold">{m.label}</div>
                  <div className={`text-[10px] ${mode === m.id ? "text-teal-100" : "text-slate-400"}`}>{m.desc}</div>
                </button>
              ))}
            </div>
          </div>

          <div>
            <div className="flex justify-between text-xs font-semibold text-slate-700 mb-1">
              <span>Max Video Duration Limit</span>
              <span>{maxDuration}s (max 30s)</span>
            </div>
            <input
              type="range"
              min={5}
              max={30}
              step={1}
              value={maxDuration}
              onChange={(e) => {
                const next = Number(e.target.value);
                setMaxDuration(next);
                if (videoDurationSec !== null && videoDurationSec <= next) {
                  setValidationError(null);
                }
              }}
              className="w-full accent-teal-600"
            />
          </div>

          {mode === "assess" && (
            <label className="flex items-start gap-2.5 rounded-xl border border-slate-200 bg-white p-3 cursor-pointer text-xs text-slate-700">
              <input
                type="checkbox"
                checked={updateBaseline}
                onChange={(e) => setUpdateBaseline(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-slate-300 text-teal-600"
              />
              <span>
                <strong>Update baseline after assessment</strong> (only applied if quality passes suitability threshold)
              </span>
            </label>
          )}

          <div className="rounded-xl bg-white border border-slate-200 p-3 text-xs text-slate-600 space-y-1">
            <div className="font-semibold text-slate-800">Active Profile: {userId}</div>
            <p>Runs the Python MediaPipe FaceLandmarker pipeline locally. Raw video frames are deleted after extraction.</p>
          </div>

          <button
            type="button"
            disabled={analyzing || !selectedFile || Boolean(validationError)}
            onClick={handleAnalyze}
            className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-teal-600 to-sky-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:from-teal-700 hover:to-sky-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {analyzing ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Analyzing with MediaPipe...
              </>
            ) : (
              <>
                <PlayCircle className="h-4 w-4" />
                Analyze Facial Video
              </>
            )}
          </button>

          {analyzing && (
            <div className="space-y-1">
              <div className="h-2 w-full rounded-full bg-slate-200 overflow-hidden">
                <div
                  className="h-full bg-teal-600 transition-all duration-300"
                  style={{ width: `${Math.max(15, progress)}%` }}
                />
              </div>
              <p className="text-[11px] text-slate-500 text-center">
                {progress < 90 ? `Uploading video (${progress}%)...` : "Running MediaPipe landmark tracking..."}
              </p>
            </div>
          )}
        </div>
      </div>

      {(validationError || apiError) && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800 flex items-start gap-2.5">
          <AlertTriangle className="h-5 w-5 shrink-0 text-rose-600 mt-0.5" />
          <span>{validationError || apiError}</span>
        </div>
      )}

      {/* Results Display */}
      {res && (
        <div className="space-y-4 pt-2 border-t border-slate-200">
          {/* Calibration notice if calibration failed or updated */}
          {res.calibration_status?.error && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-900 flex items-start gap-2.5">
              <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 mt-0.5" />
              <div>
                <strong>Calibration Skipped:</strong> {res.calibration_status.error}
              </div>
            </div>
          )}

          {res.calibration_status && !res.calibration_status.error && (
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-xs text-emerald-900 flex items-center justify-between gap-2">
              <span className="flex items-center gap-2 font-medium">
                <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                Calibration session recorded for <strong>{res.calibration_status.user_id}</strong>:{" "}
                {res.calibration_status.total_checkins} / {res.calibration_status.min_required} required sessions
              </span>
              <span className="font-semibold">
                {res.calibration_status.is_calibrated ? "Baseline Established" : "In Progress"}
              </span>
            </div>
          )}

          {/* Quality Assessment */}
          <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h4 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-teal-600" />
                Tracking Quality Assessment
              </h4>
              <div className="flex flex-wrap gap-2">
                <span
                  className={`wellness-pill ${
                    res.quality.is_reliable
                      ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                      : "bg-amber-50 text-amber-800 border border-amber-200"
                  }`}
                >
                  {res.quality.is_reliable ? "Reliable Tracking" : "Low Reliability"}
                </span>
                <span
                  className={`wellness-pill ${
                    res.quality.is_suitable_for_baseline
                      ? "bg-sky-50 text-sky-700 border border-sky-200"
                      : "bg-slate-100 text-slate-600 border border-slate-200"
                  }`}
                >
                  {res.quality.is_suitable_for_baseline ? "Baseline Suitable" : "Not Baseline Suitable"}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <MetricMini label="Quality Score" value={`${res.quality.quality_score.toFixed(1)} / 100`} />
              <MetricMini
                label="Detection Coverage"
                value={`${(res.quality.detection_coverage * 100).toFixed(1)}%`}
                sub={`${res.quality.usable_frames}/${res.quality.total_frames} frames`}
              />
              <MetricMini
                label="Duration & FPS"
                value={`${res.video_metadata.duration_sec.toFixed(2)}s`}
                sub={`${res.video_metadata.fps.toFixed(1)} FPS • ${res.video_metadata.resolution}`}
              />
              <MetricMini
                label="Lighting & Scale"
                value={`Lum ${res.quality.avg_luminance.toFixed(0)}`}
                sub={`Face area ${(res.quality.avg_face_scale * 100).toFixed(1)}%`}
              />
            </div>

            {res.quality.warnings.length > 0 && (
              <ul className="space-y-1 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-xl p-3">
                {res.quality.warnings.map((w, idx) => (
                  <li key={idx}>• {w}</li>
                ))}
              </ul>
            )}
          </div>

          {/* Five Facial Features */}
          <div className="space-y-3">
            <h4 className="text-sm font-semibold text-slate-900">Five Extracted Facial Behavioural Features</h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-3">
              {(
                [
                  {
                    key: "facialMovementVelocity",
                    label: "Facial Movement Velocity",
                    unit: "face-units / s",
                    extra: "Mean landmark displacement",
                  },
                  {
                    key: "eyeBlinkRatePm",
                    label: "Eye-Blink Rate",
                    unit: "blinks / min",
                    extra: `${res.features.auxiliary_metrics?.total_blinks_detected ?? 0} blinks detected`,
                  },
                  {
                    key: "headPoseJitterStd",
                    label: "Head-Pose Variability",
                    unit: "degrees",
                    extra: `Yaw SD ${res.features.auxiliary_metrics?.yaw_std_deg ?? "N/A"}°`,
                  },
                  {
                    key: "smileIntensityProxy",
                    label: "Smile-Intensity Proxy",
                    unit: "ratio",
                    extra: `Peak ${res.features.auxiliary_metrics?.smile_peak_ratio ?? "N/A"}`,
                  },
                  {
                    key: "browFurrowProxy",
                    label: "Brow-Furrow Proxy",
                    unit: "ratio",
                    extra: `Min ${res.features.auxiliary_metrics?.brow_min_ratio ?? "N/A"} (lower = stronger)`,
                  },
                ] as const
              ).map((item) => {
                const rawVal = res.features[item.key];
                const defText = res.features.feature_definitions?.[item.key];
                return (
                  <div key={item.key} className="rounded-xl border border-slate-200 bg-white p-3.5 flex flex-col justify-between">
                    <div>
                      <div className="text-xs font-semibold text-slate-700 flex items-start justify-between gap-1">
                        <span>{item.label}</span>
                        {defText && (
                          <span title={defText} className="text-slate-400 cursor-help shrink-0">
                            <Info className="h-3.5 w-3.5" />
                          </span>
                        )}
                      </div>
                      <div className="mt-2 text-lg font-bold text-slate-900">
                        {rawVal !== null && rawVal !== undefined ? rawVal.toFixed(3) : "Unavailable"}
                      </div>
                      <div className="text-[11px] text-slate-500">{item.unit}</div>
                    </div>
                    <div className="mt-2 pt-2 border-t border-slate-100 text-[11px] text-slate-500">{item.extra}</div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Baseline Comparison Table (Assess Mode) */}
          {res.baseline_comparison && (
            <div className="rounded-2xl border border-slate-200 bg-white p-4 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h4 className="text-sm font-semibold text-slate-900">Personal Baseline Comparison</h4>
                <span className="wellness-pill bg-sky-50 text-sky-700 border border-sky-200">
                  {res.baseline_comparison.is_calibrated
                    ? `Calibrated (${res.baseline_comparison.total_calibration_checkins} sessions)`
                    : `Preliminary (${res.baseline_comparison.total_calibration_checkins}/${res.baseline_comparison.min_checkins_required})`}
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead>
                    <tr className="border-b border-slate-200 text-slate-500">
                      <th className="py-2 pr-3 font-semibold">Feature</th>
                      <th className="py-2 pr-3 font-semibold">Observed</th>
                      <th className="py-2 pr-3 font-semibold">Base Mean ± SD</th>
                      <th className="py-2 pr-3 font-semibold">z-score</th>
                      <th className="py-2 font-semibold">Interpretation</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {Object.values(res.baseline_comparison.comparisons).map((c) => (
                      <tr key={c.feature_name}>
                        <td className="py-2 pr-3 font-medium text-slate-800">{c.feature_name}</td>
                        <td className="py-2 pr-3">{c.current_value !== null ? c.current_value.toFixed(3) : "N/A"}</td>
                        <td className="py-2 pr-3 text-slate-600">
                          {c.baseline_mean !== null
                            ? `${c.baseline_mean.toFixed(3)} ± ${(c.baseline_std ?? 0).toFixed(3)}`
                            : "N/A"}
                        </td>
                        <td className="py-2 pr-3 font-semibold">
                          {c.standardized_z !== null ? `${c.standardized_z >= 0 ? "+" : ""}${c.standardized_z.toFixed(2)}` : "N/A"}
                        </td>
                        <td className="py-2 text-slate-600">{c.interpretation}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Limitations & JSON */}
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3.5 text-xs text-slate-600">
            <strong>Limitations:</strong> {res.disclaimer}
          </div>

          <JsonInspectorCard
            title="Facial AI JSON Output"
            filename={`face_analysis_${currentRun?.runId.slice(0, 8)}.json`}
            data={res}
          />
        </div>
      )}
    </div>
  );
};

const MetricMini: React.FC<{ label: string; value: string; sub?: string }> = ({ label, value, sub }) => (
  <div className="rounded-xl border border-slate-200 bg-white p-3">
    <div className="text-[11px] font-medium text-slate-500">{label}</div>
    <div className="text-sm font-bold text-slate-900 mt-0.5">{value}</div>
    {sub && <div className="text-[11px] text-slate-400 mt-0.5">{sub}</div>}
  </div>
);
