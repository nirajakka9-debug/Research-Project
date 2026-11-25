export type Modality = "QUESTIONNAIRE" | "FACE" | "VOICE";
export type OperationalMode = "single" | "calibrate" | "assess";

export interface HealthStatus {
  service: string;
  runtime: string;
  status: string;
  database: string;
  faceAiAvailable: boolean;
  voiceAiAvailable: boolean;
  disclaimer: string;
}

export interface UserProfile {
  id: string;
  email: string;
  fullName: string;
  role: string;
  createdAt: string;
}

export interface QuestionnairePayload {
  userId?: string;
  phq2Anhedonia?: number | null;
  phq2DepressedMood?: number | null;
  gad2Nervousness?: number | null;
  gad2Worrying?: number | null;
  dailyAffectMood: number;
  dailyAffectEnergy: number;
  dailyAffectStress: number;
  sleepQuality?: number | null;
  reflectionNote?: string | null;
}

export interface QuestionnaireSummary extends QuestionnairePayload {
  phq2Total: number | null;
  gad2Total: number | null;
}

export interface FaceQuality {
  total_frames: number;
  usable_frames: number;
  fps: number;
  duration_sec: number;
  detection_coverage: number;
  quality_score: number;
  is_reliable: boolean;
  is_suitable_for_baseline: boolean;
  multi_face_frames: number;
  identity_switch_warnings: number;
  avg_face_scale: number;
  avg_luminance: number;
  avg_contrast: number;
  warnings: string[];
}

export interface FaceFeaturesData {
  facialMovementVelocity: number | null;
  eyeBlinkRatePm: number | null;
  headPoseJitterStd: number | null;
  smileIntensityProxy: number | null;
  browFurrowProxy: number | null;
  units: Record<string, string>;
  auxiliary_metrics: Record<string, number | string | null>;
  feature_definitions: Record<string, string>;
}

export interface FaceBaselineComparisonItem {
  feature_name: string;
  current_value: number | null;
  baseline_mean: number | null;
  baseline_std: number | null;
  baseline_count: number;
  units: string;
  absolute_difference: number | null;
  relative_change_pct: number | null;
  standardized_z: number | null;
  interpretation: string;
}

export interface FaceAnalysisResult {
  version: string;
  module: string;
  disclaimer: string;
  processing_time_sec: number;
  operational_mode?: OperationalMode;
  user_id?: string;
  video_metadata: {
    filename: string;
    filesize_bytes: number;
    duration_sec: number;
    total_frames: number;
    fps: number;
    resolution: string;
  };
  quality: FaceQuality;
  features: FaceFeaturesData;
  calibration_status?: {
    user_id: string;
    total_checkins?: number;
    min_required?: number;
    is_calibrated?: boolean;
    profile_path?: string;
    error?: string;
  };
  baseline_comparison?: {
    user_id: string;
    is_calibrated: boolean;
    total_calibration_checkins: number;
    min_checkins_required: number;
    comparisons: Record<string, FaceBaselineComparisonItem>;
    summary_observations: string[];
    limitations: string;
  };
}

export interface VoiceAnalysisResult {
  timestamp: string;
  status: string;
  operational_mode?: OperationalMode;
  user_id?: string;
  audio: {
    durationSec: number;
    sampleRate: number;
    channels: number;
    signalLevelRms: number;
    clippingRatio: number;
  };
  qualityScore: number;
  qualityWarnings?: string[];
  limitations?: string;
  features: {
    speakingRateWpm: number;
    totalPauseCount: number;
    meanPauseDurationMs: number;
    longestPauseDurationMs: number;
    speechRatio: number;
    speechDurationSec: number;
    silenceDurationSec: number;
    pitchMeanHz: number;
    pitchStdDevHz: number;
    pitchRangeHz: number;
    energyMeanRms: number;
    energyStdDev: number;
  };
  voicePattern?: {
    baselineType: string;
    isBaselineEstablished?: boolean;
    observationCount?: number;
    minObservationsRequired?: number;
    technicalDeviationScore: number | null;
    featureDeviations: Record<string, number | null>;
    significantDeviations: string[];
    status?: string;
  };
  calibrationStatus?: {
    user_id: string;
    observation_count: number;
    min_observations_required: number;
    is_established: boolean;
  };
}

export interface AnalysisRunResponse<T = FaceAnalysisResult | VoiceAnalysisResult> {
  runId: string;
  userId: string;
  modality: "FACE" | "VOICE";
  mode: OperationalMode;
  filename: string;
  qualityScore: number | null;
  isReliable: boolean | null;
  createdAt: string;
  result: T;
  disclaimer?: string;
}

export interface CheckinSession {
  id: string;
  userId: string;
  sessionTimestamp: string;
  status: string;
  availableModalities: Modality[];
  missingModalities: Modality[];
  notes?: string | null;
  questionnaire: QuestionnaireSummary | null;
  face: {
    id: string;
    analysisRunId: string | null;
    mode: OperationalMode;
    filename: string;
    durationSec: number | null;
    totalFrames: number | null;
    usableFrames: number | null;
    detectionCoverage: number | null;
    qualityScore: number | null;
    isReliable: boolean | null;
    isSuitableForBaseline: boolean | null;
    features: {
      facialMovementVelocity: number | null;
      eyeBlinkRatePm: number | null;
      headPoseJitterStd: number | null;
      smileIntensityProxy: number | null;
      browFurrowProxy: number | null;
    };
    raw: FaceAnalysisResult;
  } | null;
  voice: {
    id: string;
    analysisRunId: string | null;
    mode: OperationalMode;
    filename: string;
    durationSec: number | null;
    sampleRate: number | null;
    qualityScore: number | null;
    technicalDeviationScore: number | null;
    features: VoiceAnalysisResult["features"];
    voicePattern?: VoiceAnalysisResult["voicePattern"];
    qualityWarnings?: string[];
    raw: VoiceAnalysisResult;
  } | null;
  wellnessSummary: {
    fusionModelStatus: string;
    fusionModelNotice: string;
    stressScore: null;
    availableModalities: Modality[];
    missingModalities: Modality[];
    crossModalityObservations: string[];
    disclaimer: string;
  } | null;
}

export interface TrendPoint {
  checkinId: string;
  timestamp: string;
  label: string;
  availableModalities: Modality[];
  mood: number | null;
  energy: number | null;
  stress: number | null;
  phq2Total: number | null;
  gad2Total: number | null;
  facialMovementVelocity: number | null;
  eyeBlinkRatePm: number | null;
  headPoseJitterStd: number | null;
  smileIntensityProxy: number | null;
  browFurrowProxy: number | null;
  faceQualityScore: number | null;
  speakingRateWpm: number | null;
  pitchMeanHz: number | null;
  meanPauseDurationMs: number | null;
  speechRatio: number | null;
  energyMeanRms: number | null;
  voiceQualityScore: number | null;
}

export interface DashboardResponse {
  user: { id: string; fullName: string; email: string };
  todayStatus: {
    checkedInToday: boolean;
    totalCheckins: number;
    lastCheckinAt: string | null;
  };
  latestCheckin: CheckinSession | null;
  latestQuestionnaire: QuestionnaireSummary | null;
  latestFace: CheckinSession["face"];
  latestVoice: CheckinSession["voice"];
  baselines: {
    face: {
      isCalibrated: boolean;
      totalRecorded: number;
      minRequired: number;
      featureStats: Record<string, { count: number; mean: number | null; std: number | null; min: number | null; max: number | null }>;
    };
    voice: {
      isEstablished: boolean;
      observationCount: number;
      minRequired: number;
      stats: Record<string, { count: number; mean: number; std: number; min: number; max: number }>;
    };
    questionnaire: Record<string, { count: number; mean: number | null; std: number | null }>;
  };
  recentCheckins: CheckinSession[];
  recentAnalysisRuns: Array<{
    runId: string;
    modality: "FACE" | "VOICE";
    mode: OperationalMode;
    filename: string;
    qualityScore: number | null;
    isReliable: boolean | null;
    createdAt: string;
  }>;
  trends: TrendPoint[];
  disclaimer: string;
}

export interface BaselinesResponse {
  userId: string;
  face: {
    exists: boolean;
    user_id: string;
    is_calibrated: boolean;
    total_checkins_recorded: number;
    min_calibration_checkins: number;
    updated_at?: string;
    feature_stats: Record<string, { count: number; mean: number | null; std: number | null; min: number | null; max: number | null }>;
    history: Array<{
      timestamp: string;
      filename: string;
      quality_score: number;
      coverage: number;
      usable_frames: number;
      features: Record<string, number | null>;
    }>;
  };
  voice: {
    exists: boolean;
    user_id: string;
    is_established: boolean;
    observation_count: number;
    min_observations: number;
    stats: Record<string, { count: number; mean: number; std: number; min: number; max: number }>;
    history: Array<{
      timestamp: string;
      features: Record<string, number>;
    }>;
  };
  questionnaire: {
    sessionCount: number;
    stats: Record<string, { count: number; mean: number | null; std: number | null }>;
  };
  disclaimer: string;
}
