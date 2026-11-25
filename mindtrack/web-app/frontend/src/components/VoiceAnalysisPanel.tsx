import React, { useEffect, useRef, useState } from "react";
import {
  AlertTriangle,
  FileAudio,
  Loader2,
  Mic,
  PlayCircle,
  Square,
  Upload,
  Waves,
} from "lucide-react";
import { analyzeVoiceAudio } from "../services/api";
import type { AnalysisRunResponse, OperationalMode, VoiceAnalysisResult } from "../types/mindtrack";
import { startWavMicrophoneRecording, type WavRecordingSession } from "../utils/wavRecorder";
import { JsonInspectorCard } from "./SharedUI";

interface VoiceAnalysisPanelProps {
  userId: string;
  baselineProgress?: { observationCount: number; minRequired: number; isEstablished: boolean };
  currentRun: AnalysisRunResponse<VoiceAnalysisResult> | null;
  onAnalysisComplete: (run: AnalysisRunResponse<VoiceAnalysisResult>) => void;
  onNotify?: (type: "success" | "error" | "info", text: string) => void;
}

export const VoiceAnalysisPanel: React.FC<VoiceAnalysisPanelProps> = ({
  userId,
  baselineProgress,
  currentRun,
  onAnalysisComplete,
  onNotify,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [mode, setMode] = useState<OperationalMode>("single");
  const [updateBaseline, setUpdateBaseline] = useState<boolean>(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [progress, setProgress] = useState(0);

  // Microphone WAV recorder state
  const [recording, setRecording] = useState(false);
  const [recordSeconds, setRecordSeconds] = useState(0);
  const [micLevel, setMicLevel] = useState(0);
  const recorderRef = useRef<WavRecordingSession | null>(null);
  const timerRef = useRef<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      if (timerRef.current) window.clearInterval(timerRef.current);
      recorderRef.current?.cancel();
    };
  }, [audioUrl]);

  const setPickedAudioFile = (file: File | null) => {
    setValidationError(null);
    setApiError(null);
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".wav")) {
      setValidationError("Voice AI natively accepts WAV (.wav) recordings. Record directly below or upload a .wav file.");
      return;
    }
    if (file.size === 0) {
      setValidationError("Selected WAV file is empty (0 bytes).");
      return;
    }
    if (file.size > 50 * 1024 * 1024) {
      setValidationError("Audio file exceeds the 50 MB limit.");
      return;
    }
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setSelectedFile(file);
    setAudioUrl(URL.createObjectURL(file));
  };

  const handleStartRecording = async () => {
    setValidationError(null);
    setApiError(null);
    try {
      const session = await startWavMicrophoneRecording((rms) => setMicLevel(Math.min(1, rms * 6)));
      recorderRef.current = session;
      setRecording(true);
      setRecordSeconds(0);
      timerRef.current = window.setInterval(() => {
        setRecordSeconds((prev) => prev + 1);
      }, 1000);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Could not access microphone.";
      setApiError(msg);
      onNotify?.("error", msg);
    }
  };

  const handleStopRecording = async () => {
    if (!recorderRef.current) return;
    if (timerRef.current) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setRecording(false);
    setMicLevel(0);
    const wavFile = await recorderRef.current.stop();
    recorderRef.current = null;
    setPickedAudioFile(wavFile);
  };

  const handleAnalyze = async () => {
    if (!selectedFile) {
      setValidationError("Please upload or record a WAV speech sample first.");
      return;
    }
    setAnalyzing(true);
    setProgress(5);
    setApiError(null);
    try {
      const run = await analyzeVoiceAudio({
        file: selectedFile,
        userId,
        mode,
        updateBaseline: mode === "assess" && updateBaseline,
        onProgress: setProgress,
      });
      onAnalysisComplete(run);
      onNotify?.("success", `Voice acoustic analysis completed (${run.result.features.speakingRateWpm} WPM).`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Voice analysis failed.";
      setApiError(msg);
      onNotify?.("error", msg);
    } finally {
      setAnalyzing(false);
    }
  };

  const res = currentRun?.result;

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        <div className="lg:col-span-7 space-y-4">
          {/* Upload + Mic Recorder */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                setPickedAudioFile(e.dataTransfer.files?.[0] ?? null);
              }}
              className="cursor-pointer rounded-2xl border-2 border-dashed border-violet-200 bg-violet-50/30 hover:bg-violet-50/60 p-5 text-center transition"
            >
              <input
                ref={fileInputRef}
                type="file"
                accept=".wav,audio/wav"
                className="hidden"
                onChange={(e) => setPickedAudioFile(e.target.files?.[0] ?? null)}
              />
              <div className="mx-auto mb-2.5 h-10 w-10 rounded-xl bg-violet-100 text-violet-700 flex items-center justify-center">
                <Upload className="h-5 w-5" />
              </div>
              <p className="text-xs font-semibold text-slate-900">Upload WAV Audio</p>
              <p className="text-[11px] text-slate-500 mt-1">.wav only • Min 0.5s • Max 50 MB</p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-5 flex flex-col items-center justify-center text-center">
              <div
                className={`mb-2.5 h-10 w-10 rounded-xl flex items-center justify-center ${
                  recording ? "bg-rose-100 text-rose-600 animate-pulse" : "bg-sky-50 text-sky-600"
                }`}
              >
                <Mic className="h-5 w-5" />
              </div>
              {!recording ? (
                <>
                  <button
                    type="button"
                    onClick={handleStartRecording}
                    className="rounded-xl bg-slate-900 px-3.5 py-2 text-xs font-semibold text-white hover:bg-slate-800 transition"
                  >
                    Record Microphone (WAV)
                  </button>
                  <p className="text-[11px] text-slate-400 mt-1.5">Speak naturally for 5–15 seconds</p>
                </>
              ) : (
                <div className="w-full space-y-2">
                  <div className="text-xs font-bold text-rose-600">Recording • {recordSeconds}s</div>
                  <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
                    <div
                      className="h-full bg-rose-500 transition-all duration-100"
                      style={{ width: `${Math.round(micLevel * 100)}%` }}
                    />
                  </div>
                  <button
                    type="button"
                    onClick={handleStopRecording}
                    className="inline-flex items-center gap-1.5 rounded-xl bg-rose-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-rose-700"
                  >
                    <Square className="h-3 w-3 fill-current" />
                    Stop &amp; Prepare WAV
                  </button>
                </div>
              )}
            </div>
          </div>

          {selectedFile && audioUrl && (
            <div className="rounded-2xl border border-slate-200 bg-white p-4 space-y-2.5">
              <div className="flex items-center justify-between text-xs">
                <span className="inline-flex items-center gap-2 font-semibold text-slate-800">
                  <FileAudio className="h-4 w-4 text-violet-600" />
                  {selectedFile.name}
                </span>
                <span className="text-slate-500">{(selectedFile.size / 1024).toFixed(1)} KB</span>
              </div>
              <audio src={audioUrl} controls className="w-full" />
            </div>
          )}
        </div>

        <div className="lg:col-span-5 rounded-2xl border border-slate-200 bg-slate-50/70 p-4 space-y-4">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold text-slate-900 flex items-center gap-2">
              <Waves className="h-4 w-4 text-violet-600" />
              Voice AI DSP Settings
            </h4>
            {baselineProgress && (
              <span
                className={`wellness-pill text-[11px] ${
                  baselineProgress.isEstablished
                    ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                    : "bg-amber-50 text-amber-700 border border-amber-200"
                }`}
              >
                Baseline: {baselineProgress.observationCount}/{baselineProgress.minRequired}
              </span>
            )}
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 mb-1.5">Operational Mode</label>
            <div className="grid grid-cols-3 gap-1.5">
              {(
                [
                  { id: "single", label: "Single", desc: "Ref fallback" },
                  { id: "calibrate", label: "Calibrate", desc: "Add baseline" },
                  { id: "assess", label: "Assess", desc: "Personal z-score" },
                ] as const
              ).map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => setMode(m.id)}
                  className={`rounded-xl border px-2.5 py-2 text-left transition ${
                    mode === m.id
                      ? "border-violet-600 bg-violet-600 text-white shadow-sm"
                      : "border-slate-200 bg-white text-slate-700 hover:bg-slate-100"
                  }`}
                >
                  <div className="text-xs font-semibold">{m.label}</div>
                  <div className={`text-[10px] ${mode === m.id ? "text-violet-100" : "text-slate-400"}`}>{m.desc}</div>
                </button>
              ))}
            </div>
          </div>

          {mode === "assess" && (
            <label className="flex items-start gap-2.5 rounded-xl border border-slate-200 bg-white p-3 cursor-pointer text-xs text-slate-700">
              <input
                type="checkbox"
                checked={updateBaseline}
                onChange={(e) => setUpdateBaseline(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-slate-300 text-violet-600"
              />
              <span>
                <strong>Update personal voice baseline</strong> after evaluating against prior sessions
              </span>
            </label>
          )}

          <div className="rounded-xl bg-white border border-slate-200 p-3 text-xs text-slate-600 space-y-1">
            <div className="font-semibold text-slate-800">Active Profile: {userId}</div>
            <p>
              Rule-based DSP pipeline (VAD + normalized autocorrelation pitch + syllabic envelope WPM). No ML emotion
              classifier is used.
            </p>
          </div>

          <button
            type="button"
            disabled={analyzing || !selectedFile || Boolean(validationError)}
            onClick={handleAnalyze}
            className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-sky-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:from-violet-700 hover:to-sky-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {analyzing ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Extracting Acoustic Features...
              </>
            ) : (
              <>
                <PlayCircle className="h-4 w-4" />
                Analyze Voice Recording
              </>
            )}
          </button>

          {analyzing && (
            <div className="h-2 w-full rounded-full bg-slate-200 overflow-hidden">
              <div
                className="h-full bg-violet-600 transition-all duration-300"
                style={{ width: `${Math.max(20, progress)}%` }}
              />
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

      {res && (
        <div className="space-y-4 pt-2 border-t border-slate-200">
          {res.calibrationStatus && (
            <div className="rounded-xl border border-violet-200 bg-violet-50 px-4 py-3 text-xs text-violet-900 flex items-center justify-between gap-2">
              <span>
                Voice baseline sessions for <strong>{res.calibrationStatus.user_id}</strong>:{" "}
                {res.calibrationStatus.observation_count} / {res.calibrationStatus.min_observations_required}
              </span>
              <span className="font-semibold">
                {res.calibrationStatus.is_established ? "Baseline Established" : "Calibrating"}
              </span>
            </div>
          )}

          {/* Audio Quality & Metadata */}
          <div className="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h4 className="text-sm font-semibold text-slate-900">Audio Metadata &amp; Signal Quality</h4>
              <span
                className={`wellness-pill ${
                  res.qualityScore >= 0.55
                    ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                    : "bg-amber-50 text-amber-800 border border-amber-200"
                }`}
              >
                Quality Score: {res.qualityScore.toFixed(2)} / 1.00
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="rounded-xl border border-slate-200 bg-white p-3">
                <div className="text-slate-500">Duration</div>
                <div className="text-sm font-bold text-slate-900 mt-0.5">{res.audio.durationSec}s</div>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white p-3">
                <div className="text-slate-500">Processed Rate</div>
                <div className="text-sm font-bold text-slate-900 mt-0.5">{res.audio.sampleRate} Hz mono</div>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white p-3">
                <div className="text-slate-500">Signal RMS</div>
                <div className="text-sm font-bold text-slate-900 mt-0.5">{res.audio.signalLevelRms}</div>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white p-3">
                <div className="text-slate-500">Clipping Ratio</div>
                <div className="text-sm font-bold text-slate-900 mt-0.5">
                  {(res.audio.clippingRatio * 100).toFixed(2)}%
                </div>
              </div>
            </div>

            {res.qualityWarnings && res.qualityWarnings.length > 0 && (
              <ul className="space-y-1 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-xl p-3">
                {res.qualityWarnings.map((w, idx) => (
                  <li key={idx}>• {w}</li>
                ))}
              </ul>
            )}
          </div>

          {/* 12 Acoustic Features */}
          <div className="space-y-3">
            <h4 className="text-sm font-semibold text-slate-900">12 Extracted Acoustic Features</h4>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {(
                [
                  ["Speaking Rate (Est.)", `${res.features.speakingRateWpm} WPM`],
                  ["Total Pause Count", `${res.features.totalPauseCount}`],
                  ["Mean Pause Duration", `${res.features.meanPauseDurationMs} ms`],
                  ["Longest Pause", `${res.features.longestPauseDurationMs} ms`],
                  ["Speech Ratio", `${(res.features.speechRatio * 100).toFixed(1)}%`],
                  ["Speech Duration", `${res.features.speechDurationSec} s`],
                  ["Silence Duration", `${res.features.silenceDurationSec} s`],
                  ["Pitch Mean (F0)", `${res.features.pitchMeanHz} Hz`],
                  ["Pitch Std Dev", `${res.features.pitchStdDevHz} Hz`],
                  ["Pitch Range", `${res.features.pitchRangeHz} Hz`],
                  ["Energy Mean (RMS)", `${res.features.energyMeanRms}`],
                  ["Energy Std Dev", `${res.features.energyStdDev}`],
                ] as const
              ).map(([label, val]) => (
                <div key={label} className="rounded-xl border border-slate-200 bg-white p-3">
                  <div className="text-[11px] font-medium text-slate-500">{label}</div>
                  <div className="text-base font-bold text-slate-900 mt-0.5">{val}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Voice Pattern / Longitudinal Deviation */}
          {res.voicePattern && (
            <div className="rounded-2xl border border-slate-200 bg-white p-4 space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h4 className="text-sm font-semibold text-slate-900">Technical Acoustic Pattern Deviation</h4>
                  <p className="text-xs text-slate-500">
                    Baseline type:{" "}
                    {res.voicePattern.baselineType === "personal_longitudinal"
                      ? "Personal Longitudinal Baseline"
                      : "Engineering Reference Distribution (Fallback — calibrate >= 3 sessions for personal Z-scores)"}
                  </p>
                </div>
                <span className="wellness-pill bg-violet-50 text-violet-700 border border-violet-200">
                  Deviation Score:{" "}
                  {res.voicePattern.technicalDeviationScore !== null &&
                  res.voicePattern.technicalDeviationScore !== undefined
                    ? res.voicePattern.technicalDeviationScore.toFixed(2)
                    : "Pending baseline"}
                </span>
              </div>

              {res.voicePattern.status && (
                <p className="text-xs text-slate-600">Status: {res.voicePattern.status}</p>
              )}

              {res.voicePattern.significantDeviations?.length > 0 && (
                <div className="rounded-xl bg-slate-50 border border-slate-200 p-3 space-y-1 text-xs text-slate-700">
                  {res.voicePattern.significantDeviations.map((d, i) => (
                    <div key={i}>• {d}</div>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-3.5 text-xs text-slate-600">
            <strong>Limitations:</strong>{" "}
            {res.limitations ||
              "Voice AI extracts physical acoustic features using rule-based signal processing and does not diagnose mental health conditions or predict stress."}
          </div>

          <JsonInspectorCard
            title="Voice AI JSON Output"
            filename={`voice_analysis_${currentRun?.runId.slice(0, 8)}.json`}
            data={res}
          />
        </div>
      )}
    </div>
  );
};
