import type {
  AnalysisRunResponse,
  BaselinesResponse,
  CheckinSession,
  DashboardResponse,
  FaceAnalysisResult,
  HealthStatus,
  OperationalMode,
  QuestionnairePayload,
  UserProfile,
  VoiceAnalysisResult,
} from "../types/mindtrack";

const API_BASE = "/api/v1";

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data?.detail === "string") {
        message = data.detail;
      } else if (Array.isArray(data?.detail)) {
        message = data.detail.map((e: { msg?: string }) => e.msg || JSON.stringify(e)).join("; ");
      }
    } catch {
      // ignore json parse failure
    }
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

export async function fetchHealth(): Promise<HealthStatus> {
  const res = await fetch(`${API_BASE}/health`);
  return handleResponse<HealthStatus>(res);
}

export async function fetchUsers(): Promise<UserProfile[]> {
  const res = await fetch(`${API_BASE}/users`);
  return handleResponse<UserProfile[]>(res);
}

export async function createUser(payload: { id: string; fullName: string; email: string }): Promise<UserProfile> {
  const res = await fetch(`${API_BASE}/users`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<UserProfile>(res);
}

export async function fetchDashboard(userId: string): Promise<DashboardResponse> {
  const res = await fetch(`${API_BASE}/dashboard/${encodeURIComponent(userId)}`);
  return handleResponse<DashboardResponse>(res);
}

export async function fetchBaselines(userId: string): Promise<BaselinesResponse> {
  const res = await fetch(`${API_BASE}/baselines/${encodeURIComponent(userId)}`);
  return handleResponse<BaselinesResponse>(res);
}

export async function resetBaseline(userId: string, modality: "face" | "voice"): Promise<{ reset: boolean }> {
  const res = await fetch(`${API_BASE}/baselines/${encodeURIComponent(userId)}/${modality}`, {
    method: "DELETE",
  });
  return handleResponse<{ reset: boolean }>(res);
}

export async function fetchCheckins(userId: string): Promise<CheckinSession[]> {
  const res = await fetch(`${API_BASE}/checkins?userId=${encodeURIComponent(userId)}`);
  return handleResponse<CheckinSession[]>(res);
}

export async function deleteCheckin(checkinId: string): Promise<{ deleted: boolean }> {
  const res = await fetch(`${API_BASE}/checkins/${encodeURIComponent(checkinId)}`, {
    method: "DELETE",
  });
  return handleResponse<{ deleted: boolean }>(res);
}

export async function createCheckin(payload: {
  userId: string;
  questionnaire?: QuestionnairePayload | null;
  faceAnalysisRunId?: string | null;
  voiceAnalysisRunId?: string | null;
  notes?: string | null;
}): Promise<CheckinSession> {
  const res = await fetch(`${API_BASE}/checkins`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<CheckinSession>(res);
}

export async function fetchRecentRuns<T = FaceAnalysisResult | VoiceAnalysisResult>(
  userId: string,
  modality?: "FACE" | "VOICE",
): Promise<Array<AnalysisRunResponse<T>>> {
  const qs = modality ? `?modality=${modality}` : "";
  const res = await fetch(`${API_BASE}/analysis-runs/${encodeURIComponent(userId)}${qs}`);
  return handleResponse<Array<AnalysisRunResponse<T>>>(res);
}

export function uploadWithProgress<T>(
  endpoint: string,
  formData: FormData,
  onProgress?: (pct: number) => void,
): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}${endpoint}`);

    xhr.upload.onprogress = (evt) => {
      if (evt.lengthComputable && onProgress) {
        const pct = Math.min(95, Math.round((evt.loaded / evt.total) * 90));
        onProgress(pct);
      }
    };

    xhr.onload = () => {
      if (onProgress) onProgress(100);
      try {
        const parsed = JSON.parse(xhr.responseText || "{}");
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(parsed as T);
        } else {
          reject(new Error(parsed?.detail || `Request failed (${xhr.status})`));
        }
      } catch {
        reject(new Error(`Unexpected server response (${xhr.status})`));
      }
    };

    xhr.onerror = () => {
      reject(new Error("Could not connect to the MindTrack backend service."));
    };

    xhr.send(formData);
  });
}

export async function analyzeFaceVideo(params: {
  file: File;
  userId: string;
  mode: OperationalMode;
  maxDuration: number;
  updateBaseline: boolean;
  onProgress?: (pct: number) => void;
}): Promise<AnalysisRunResponse<FaceAnalysisResult>> {
  const form = new FormData();
  form.append("file", params.file);
  form.append("userId", params.userId);
  form.append("mode", params.mode);
  form.append("maxDuration", String(params.maxDuration));
  form.append("updateBaseline", String(params.updateBaseline));
  return uploadWithProgress<AnalysisRunResponse<FaceAnalysisResult>>("/face/analyze", form, params.onProgress);
}

export async function analyzeVoiceAudio(params: {
  file: File;
  userId: string;
  mode: OperationalMode;
  updateBaseline: boolean;
  onProgress?: (pct: number) => void;
}): Promise<AnalysisRunResponse<VoiceAnalysisResult>> {
  const form = new FormData();
  form.append("file", params.file);
  form.append("userId", params.userId);
  form.append("mode", params.mode);
  form.append("updateBaseline", String(params.updateBaseline));
  return uploadWithProgress<AnalysisRunResponse<VoiceAnalysisResult>>("/voice/analyze", form, params.onProgress);
}
