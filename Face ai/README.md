# MindTrack: Facial Behaviour Longitudinal Wellness Monitoring Module

A standalone, terminal-based computer vision research module developed for the **MindTrack MCA Research Project**. 

MindTrack investigates whether facial-behaviour changes relative to an individual's own personal baseline can contribute useful information to longitudinal wellness monitoring.

> **CRITICAL RESEARCH & NON-DIAGNOSTIC NOTICE**:  
> "Stress inference is not validated. This check-in provides facial-behaviour measurements and personal-baseline comparisons only."  
> This system does **NOT** detect, diagnose, or classify stress, depression, anxiety, or any psychiatric illness. It does not compute a stress score, percentage, probability, or clinical label. Facial behaviour measurements are exploratory geometric proxies influenced by physical, environmental, and cognitive factors.

---

## 1. Longitudinal Wellness Monitoring Approach

A single video recording cannot establish a personal baseline or indicate whether an observed facial behaviour is unusual for that individual. MindTrack implements persistent, per-user empirical baselines using local JSON files (no database required):

### Two Explicit Modes:

1. **Calibration Mode (`--mode calibrate`)**:
   - Records valid check-in sessions to build a participant's longitudinal baseline profile.
   - Requires multiple separate sessions (default: **at least 5 valid check-ins**) before considering the baseline established.
   - Computes feature-specific sample count, mean, and standard deviation.
   - **Never treats missing features as zero**.
   - Validates recording quality to prevent low-quality tracking from corrupting the baseline profile.

2. **Assessment Mode (`--mode assess`)**:
   - Compares a new recording against the participant's saved personal baseline profile.
   - If no baseline exists, clearly explains that calibration is required instead of inventing a baseline.
   - Computes absolute differences ($\Delta$), relative percentage change, and standardized deviations ($z$-scores).
   - Handles zero or near-zero baseline variance and missing features safely without division by zero.
   - **Does not update the baseline profile automatically** during assessment unless `--update-baseline` is explicitly specified.

---

## 2. Five Facial Behavioural Features

| Feature | Unit | Mathematical Definition & Normalization |
| :--- | :--- | :--- |
| `facialMovementVelocity` | `face-units / sec` | Mean Euclidean displacement across all 468 facial mesh landmarks between consecutive usable frames, normalized by outer-eye inter-ocular distance ($S = \|p_{33} - p_{263}\|$) and divided by $\Delta t$. |
| `eyeBlinkRatePm` | `blinks / min` | Extrapolated blinks per minute calculated from Eye Aspect Ratio ($\text{EAR} < 0.21$) eye closure and reopening events over actual usable recording duration. Distinguishes measured 0 blinks from unavailable data. |
| `headPoseJitterStd` | `degrees` | Vector standard deviation ($\sqrt{\sigma_{\text{yaw}}^2 + \sigma_{\text{pitch}}^2 + \sigma_{\text{roll}}^2}$) across frames estimated via `cv2.solvePnP` mapping 6 canonical 2D landmarks to a generic 3D anthropometric face model. *Reflects relative angular variability across frames.* |
| `smileIntensityProxy` | `ratio (dimensionless)` | Mean ratio of mouth width ($\|p_{61} - p_{291}\|$) to outer-eye inter-ocular distance ($\|p_{33} - p_{263}\|$) across usable frames. |
| `browFurrowProxy` | `ratio (dimensionless)` | Mean vertical distance from inner/mid-eyebrow landmarks (107, 336) to upper eyelid centers (159, 386) normalized by inter-ocular distance. Lower value indicates stronger brow lowering/furrowing. |

---

## 3. Check-In Report Structure

Each check-in produces a five-section terminal card:
- **[A] Check-In Quality**: Duration, usable frames, coverage, lighting, scale, tracking quality score (0-100), reliability, and baseline suitability.
- **[B] Facial Behavioural Observations**: Measured numerical values, units, quality, and status for each of the five features.
- **[C] Personal Baseline Comparison**: Calibration progress, feature-by-feature comparison table (observed, base mean, base SD, diff, z-score, and statistical interpretation).
- **[D] Wellness-Related Interpretation**: Narrative description of which features varied from baseline using non-diagnostic research language.
- **[E] Stress and Mental Wellness Limitations**: Explicit statement that stress inference is not validated.

---

## 4. Command-Line Usage

### 1. Calibration Mode (Build Personal Baseline)
Run multiple separate recordings to establish a participant baseline (minimum 5):
```powershell
python main.py --video videos/checkin1.mp4 --user-id demo_user --mode calibrate
```

### 2. Assessment Mode (Compare to Baseline)
Compare a new check-in against the user's established baseline:
```powershell
python main.py --video videos/checkin2.mp4 --user-id demo_user --mode assess --output outputs/assessment.json
```

### 3. Assessment with Explicit Baseline Update
Assess and optionally incorporate the new session into the baseline history:
```powershell
python main.py --video videos/checkin2.mp4 --user-id demo_user --mode assess --update-baseline
```

### 4. Single Recording Generic Check-in (Backward Compatible)
```powershell
python main.py --video sample_synthetic.mp4
```

### 5. CLI Help
```powershell
python main.py --help
```

---

## 5. Security & Profile Storage

- **Profiles Directory**: Profiles are stored as versioned JSON files in `profiles/{user_id}.json`.
- **User ID Sanitization**: User IDs are validated against `^[a-zA-Z0-9_-]{1,64}$` to strictly prevent directory traversal or unsafe filesystem operations.
- **Privacy**: The `profiles/` folder and video files are excluded by `.gitignore`. All video processing is performed entirely locally in memory.

---

## 6. Automated Testing

Run the full pytest suite (33 unit & integration tests):
```powershell
python -m pytest -v
```
All tests pass in ~2 seconds covering baseline persistence, zero-variance handling, path traversal prevention, quality scoring, missing data handling, and non-diagnostic wording.
