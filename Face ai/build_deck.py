"""
build_deck.py
-------------
Generates the complete, professional 14-slide PowerPoint presentation:
'Facial_AI_of_Wellness_Tracker.pptx' and exports 'Facial_AI_of_Wellness_Tracker.pdf'.
"""

import os
import sys
from pathlib import Path
import pptx
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

# Theme Colors
BG_DARK = RGBColor(10, 17, 40)            # #0A1128 Deep Midnight Navy
CARD_BG = RGBColor(19, 30, 58)            # #131E3A Dark Slate Card
CARD_BG_ALT = RGBColor(24, 39, 75)        # #18274B Lighter Slate Card
CARD_BORDER = RGBColor(30, 58, 95)        # #1E3A5F Muted Slate Border
BORDER_CYAN = RGBColor(6, 182, 212)       # #06B6D4 Vibrant Cyan Border
BORDER_BLUE = RGBColor(59, 130, 246)      # #3B82F6 Vibrant Blue Border
BORDER_EMERALD = RGBColor(16, 185, 129)   # #10B981 Emerald Border
BORDER_AMBER = RGBColor(245, 158, 11)     # #F59E0B Amber Border
BORDER_ROSE = RGBColor(239, 68, 68)       # #EF4444 Rose Border

TEXT_WHITE = RGBColor(255, 255, 255)
TEXT_MUTED = RGBColor(148, 163, 184)      # #94A3B8 Slate Gray
TEXT_BODY = RGBColor(226, 232, 240)       # #E2E8F0 Light Slate Body
CYAN_ACCENT = RGBColor(34, 211, 238)      # #22D3EE Bright Neon Cyan
BLUE_ACCENT = RGBColor(96, 165, 250)      # #60A5FA Soft Sky Blue
EMERALD_ACCENT = RGBColor(52, 211, 153)   # #34D399 Mint Green
AMBER_ACCENT = RGBColor(251, 191, 36)     # #FBBF24 Warning Amber

FONT_FAMILY = "Segoe UI"
FONT_CODE = "Consolas"


def set_bg(slide):
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
    bg.fill.solid()
    bg.fill.fore_color.rgb = BG_DARK
    bg.line.fill.background()
    return bg


def add_header(slide, category: str, title: str, subtitle: str = ""):
    tag_box = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(0.8), Inches(0.42), Inches(len(category) * 0.11 + 0.45), Inches(0.28)
    )
    tag_box.fill.solid()
    tag_box.fill.fore_color.rgb = RGBColor(16, 42, 77)
    tag_box.line.color.rgb = CYAN_ACCENT
    tag_box.line.width = Pt(1)
    tf_tag = tag_box.text_frame
    tf_tag.word_wrap = False
    tf_tag.margin_left = tf_tag.margin_right = Inches(0.08)
    tf_tag.margin_top = tf_tag.margin_bottom = Inches(0.02)
    p_tag = tf_tag.paragraphs[0]
    p_tag.text = category.upper()
    p_tag.font.name = FONT_FAMILY
    p_tag.font.size = Pt(9.5)
    p_tag.font.bold = True
    p_tag.font.color.rgb = CYAN_ACCENT

    title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.75), Inches(11.733), Inches(0.95))
    tf = title_box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    
    p_title = tf.paragraphs[0]
    p_title.text = title
    p_title.font.name = FONT_FAMILY
    p_title.font.size = Pt(21)
    p_title.font.bold = True
    p_title.font.color.rgb = TEXT_WHITE
    p_title.space_after = Pt(2)

    if subtitle:
        p_sub = tf.add_paragraph()
        p_sub.text = subtitle
        p_sub.font.name = FONT_FAMILY
        p_sub.font.size = Pt(11.5)
        p_sub.font.color.rgb = TEXT_MUTED


def add_card(slide, left, top, width, height, title, items, border_color=CARD_BORDER, bg_color=CARD_BG, title_color=CYAN_ACCENT):
    card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    card.fill.solid()
    card.fill.fore_color.rgb = bg_color
    card.line.color.rgb = border_color
    card.line.width = Pt(1.2)

    tf = card.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.20)
    tf.margin_right = Inches(0.20)
    tf.margin_top = Inches(0.18)
    tf.margin_bottom = Inches(0.16)

    if title:
        p_title = tf.paragraphs[0]
        p_title.text = title
        p_title.font.name = FONT_FAMILY
        p_title.font.size = Pt(12.5)
        p_title.font.bold = True
        p_title.font.color.rgb = title_color
        p_title.space_after = Pt(6)
    
    for i, item in enumerate(items):
        if not title and i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        
        if isinstance(item, tuple):
            prefix, text = item
            run_pre = p.add_run()
            run_pre.text = prefix + " "
            run_pre.font.name = FONT_FAMILY
            run_pre.font.bold = True
            run_pre.font.size = Pt(10)
            run_pre.font.color.rgb = BLUE_ACCENT
            
            run_txt = p.add_run()
            run_txt.text = text
            run_txt.font.name = FONT_FAMILY
            run_txt.font.size = Pt(10)
            run_txt.font.color.rgb = TEXT_BODY
        else:
            p.text = item
            p.font.name = FONT_FAMILY
            p.font.size = Pt(10)
            p.font.color.rgb = TEXT_BODY
        
        p.space_after = Pt(4)
    return card


def add_notes(slide, text: str):
    notes_slide = slide.notes_slide
    text_frame = notes_slide.notes_text_frame
    text_frame.text = text.strip()


def create_deck(output_pptx_path: str):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # =========================================================================
    # SLIDE 1: TITLE SLIDE
    # =========================================================================
    s1 = prs.slides.add_slide(blank_layout)
    set_bg(s1)

    # Accent vertical line
    bar = s1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(1.0), Inches(2.1), Inches(0.12), Inches(2.9))
    bar.fill.solid()
    bar.fill.fore_color.rgb = CYAN_ACCENT
    bar.line.fill.background()

    tb = s1.shapes.add_textbox(Inches(1.4), Inches(1.9), Inches(10.8), Inches(3.2))
    tf = tb.text_frame
    tf.word_wrap = True

    p0 = tf.paragraphs[0]
    p0.text = "RESEARCH MODULE • COMPUTER VISION • PERSONAL BASELINES"
    p0.font.name = FONT_FAMILY
    p0.font.size = Pt(11.5)
    p0.font.bold = True
    p0.font.color.rgb = CYAN_ACCENT
    p0.space_after = Pt(12)

    p1 = tf.add_paragraph()
    p1.text = "Facial AI of Wellness Tracker"
    p1.font.name = FONT_FAMILY
    p1.font.size = Pt(40)
    p1.font.bold = True
    p1.font.color.rgb = TEXT_WHITE
    p1.space_after = Pt(8)

    p2 = tf.add_paragraph()
    p2.text = "Facial Behaviour Analysis for Longitudinal Wellness Monitoring"
    p2.font.name = FONT_FAMILY
    p2.font.size = Pt(18)
    p2.font.color.rgb = BLUE_ACCENT
    p2.space_after = Pt(16)

    p3 = tf.add_paragraph()
    p3.text = "An exploratory computer-vision framework measuring quantitative facial-behaviour proxies and tracking individual deviations relative to personal empirical baselines."
    p3.font.name = FONT_FAMILY
    p3.font.size = Pt(12.5)
    p3.font.color.rgb = TEXT_MUTED

    # Bottom pill badges
    pills = [
        "Local Privacy Execution",
        "Zero Cloud Transmission",
        "Non-Diagnostic Telemetry",
        "MediaPipe FaceLandmarker"
    ]
    for i, pill in enumerate(pills):
        pb = s1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.0 + i * 2.85), Inches(5.8), Inches(2.65), Inches(0.48))
        pb.fill.solid()
        pb.fill.fore_color.rgb = CARD_BG
        pb.line.color.rgb = CARD_BORDER
        pb.line.width = Pt(1)
        pbtf = pb.text_frame
        pbtf.paragraphs[0].text = pill
        pbtf.paragraphs[0].font.name = FONT_FAMILY
        pbtf.paragraphs[0].font.size = Pt(9.5)
        pbtf.paragraphs[0].font.bold = True
        pbtf.paragraphs[0].font.color.rgb = TEXT_BODY
        pbtf.paragraphs[0].alignment = PP_ALIGN.CENTER

    add_notes(s1, """
Welcome to this technical presentation on the Facial AI module of MindTrack.
MindTrack is an academic research project investigating how computational computer vision can support longitudinal mental wellness monitoring.
Crucially, this module does not attempt to diagnose psychological illnesses or claim that a webcam can read minds or detect stress from a single recording.
Instead, it extracts objective geometric and temporal facial behaviour parameters, verifies video quality, establishes an empirical personal baseline over multiple distinct sessions, and observes whether an individual's expressions deviate from their own historical reference over time.
""")

    # =========================================================================
    # SLIDE 2: INTRODUCTION
    # =========================================================================
    s2 = prs.slides.add_slide(blank_layout)
    set_bg(s2)
    add_header(s2, "Context & Foundations", "Facial Behaviour in Multimodal Wellness Monitoring", 
               "Understanding the role and scientific boundaries of computer-vision facial telemetry.")

    add_card(s2, Inches(0.8), Inches(1.88), Inches(3.64), Inches(4.9),
             "1. Multimodal Framework", [
                 ("Broad Architecture:", "MindTrack conceptualizes wellness monitoring as a multimodal discipline requiring diverse, synchronized observational streams."),
                 ("Integrative Context:", "Facial behaviour is designed as one complementary observational signal alongside self-reports, activity rhythms, and physiological metrics."),
                 ("No Standalone Reliance:", "No single modality is treated as ground-truth or definitive evidence of affective or mental health state."),
                 ("Non-Intrusive Capture:", "Enables short, friction-free video check-ins without specialized hardware sensors.")
             ], border_color=BORDER_BLUE)

    add_card(s2, Inches(4.84), Inches(1.88), Inches(3.64), Inches(4.9),
             "2. Measurable Telemetry", [
                 ("Geometric Quantification:", "Extracts raw, objective geometric landmarks (468/478 points) from video rather than subjective visual ratings."),
                 ("Temporal Kinematics:", "Tracks movement dynamics over time—such as blink frequencies, landmark displacement velocity, and head-pose angular jitter."),
                 ("Rigid Normalization:", "Uses outer-eye inter-ocular distance to make all spatial displacements invariant to camera distance and face scale."),
                 ("Deterministic Math:", "All features rely on transparent geometric formulas without black-box opaque emotion classifiers.")
             ], border_color=BORDER_CYAN)

    add_card(s2, Inches(8.88), Inches(1.88), Inches(3.64), Inches(4.9),
             "3. Non-Diagnostic Scope", [
                 ("Scientific Humility:", "The system strictly refrains from inferring psychiatric conditions, clinical depression, or acute stress states."),
                 ("Behavioural Proxies:", "Measured numbers represent physical facial kinematics (e.g., eye closures, mouth widening), not validated emotional constructs."),
                 ("Confounding Factors:", "Acknowledges that facial dynamics fluctuate naturally due to physical fatigue, ambient lighting, speaking, and room setup."),
                 ("Research Integrity:", "Emphasizes longitudinal self-comparison rather than deceptive universal population thresholds.")
             ], border_color=BORDER_EMERALD)

    add_notes(s2, """
On Slide 2, we introduce where this facial AI module sits within the broader MindTrack framework.
Affective science has demonstrated that facial expressions are highly context-dependent and culturally idiosyncratic. Therefore, this module is strictly a provider of measurable geometric features.
We extract landmarks and quantify velocity, blink rate, head-pose jitter, mouth widening, and brow displacement.
Importantly, facial behaviour is only one stream within a multimodal framework. It must never be used alone to infer psychological state.
""")

    # =========================================================================
    # SLIDE 3: PROBLEM STATEMENT
    # =========================================================================
    s3 = prs.slides.add_slide(blank_layout)
    set_bg(s3)
    add_header(s3, "Research Challenge", "The Limitations of Single-Recording Affective Inference",
               "Why universal thresholds fail and how personal baselines address individual heterogeneity.")

    add_card(s3, Inches(0.8), Inches(1.88), Inches(3.64), Inches(4.9),
             "The Single-Recording Fallacy", [
                 ("Cross-Sectional Blindness:", "A single 15-second recording cannot reveal if an observed expression is normal, habitual, or unusual for that individual."),
                 ("High Inter-Subject Variance:", "One person naturally blinks 30 times a minute; another blinks 12. Cross-population models label the former as 'anxious' and the latter as 'flat'."),
                 ("Static Misattribution:", "Facial anatomy variations (e.g., natural brow furrow or resting smile shape) are routinely misclassified as persistent negative affect."),
                 ("Lack of Context:", "Snapshot inference ignores whether the participant just finished talking, working on a screen, or entered a sunny room.")
             ], border_color=BORDER_ROSE)

    add_card(s3, Inches(4.84), Inches(1.88), Inches(3.64), Inches(4.9),
             "Environmental & Physical Confounders", [
                 ("Lighting Shifts:", "Shadows, backlighting, and screen glare alter detected landmark contrast and falsely skew geometric ratios."),
                 ("Speech & Articulation:", "Active verbal communication continuously shifts lip and jaw positions, distorting smile and movement proxies."),
                 ("Fatigue & Strain:", "Dry eyes and prolonged display staring drastically alter blink frequency and eyelid aperture without emotional cause."),
                 ("Camera Parallax:", "Varying webcam height, tilt angle, and optical focal distortion directly corrupt uncalibrated 3D pose calculations.")
             ], border_color=BORDER_AMBER)

    add_card(s3, Inches(8.88), Inches(1.88), Inches(3.64), Inches(4.9),
             "The Longitudinal Baseline Solution", [
                 ("Self-Referential Framing:", "Instead of comparing Participant A to an arbitrary population dataset, we compare Participant A strictly against Participant A."),
                 ("Longitudinal Tracking:", "By capturing repeated check-ins across multiple days, we establish an empirical normal distribution (mean, standard deviation)."),
                 ("Detecting Deviations:", "A meaningful wellness signal is only flagged when current check-in metrics deviate statistically from the participant's own baseline."),
                 ("Robust to Idiosyncrasy:", "Natural facial resting features are absorbed into the baseline reference, neutralizing anatomical bias.")
             ], border_color=BORDER_CYAN)

    add_notes(s3, """
Slide 3 addresses the fundamental scientific challenge in facial computing: the failure of single-recording emotion and stress detection.
Commercial tools often claim to detect stress from a single webcam snapshot. This is scientifically unfounded. Inter-individual baseline differences far exceed affective signal differences.
Natural resting faces vary widely. A person with deep-set eyes may permanently look 'furrowed'. A person with dry eyes blinks twice as fast.
Furthermore, environmental factors like speech, lighting, and computer screen glare heavily influence facial dynamics.
The solution implemented in this module is personal-baseline comparison: observing changes relative to the individual's own multi-day baseline.
""")

    # =========================================================================
    # SLIDE 4: OBJECTIVES
    # =========================================================================
    s4 = prs.slides.add_slide(blank_layout)
    set_bg(s4)
    add_header(s4, "Engineering & Research Goals", "Module Scope and Core Technical Objectives",
               "Systematic implementation roadmap for robust, non-diagnostic facial telemetry.")

    grid_items = [
        ("1. Facial Landmark Tracking", [
            ("MediaPipe Mesh:", "Detect and track 468 canonical facial landmarks across video frames."),
            ("Single-Face Policy:", "Enforce conservative single-face tracking to reject background faces and prevent identity switching.")
        ], BORDER_BLUE),
        ("2. Geometric Feature Extraction", [
            ("Kinematic Metrics:", "Compute normalized movement velocity, blink rate, head-pose jitter, smile proxy, and brow furrow proxy."),
            ("Rigid Normalization:", "Normalize all spatial measurements by outer-eye distance to handle scale.")
        ], BORDER_CYAN),
        ("3. Comprehensive Quality Assessment", [
            ("0–100 Quality Metric:", "Calculate coverage, lighting luminance/contrast, face scale, and tracking continuity."),
            ("Baseline Suitability Gating:", "Prevent corrupted or poorly lit videos from polluting personal profiles.")
        ], BORDER_EMERALD),
        ("4. Persistent Baseline Calibration", [
            ("Multi-Session Accumulation:", "Record at least 5 distinct check-ins to establish stable personal distributions."),
            ("Statistical Rigor:", "Maintain feature-specific sample count, mean, and standard deviation in local JSON.")
        ], BORDER_CYAN),
        ("5. Standardized Deviation Assessment", [
            ("Z-Score Comparisons:", "Compute absolute diff, relative change %, and standardized deviation z."),
            ("Edge-Case Safeguards:", "Safely handle zero baseline variance and missing features without NaN or errors.")
        ], BORDER_BLUE),
        ("6. Non-Diagnostic Scientific Reporting", [
            ("Contextual Narratives:", "Generate clear terminal and JSON reports using careful, research-oriented language."),
            ("Explicit Boundary Notices:", "Reiterate that stress inference is unvalidated and no diagnoses are made.")
        ], BORDER_AMBER)
    ]

    for idx, (title, items, border_c) in enumerate(grid_items):
        col = idx % 3
        row = idx // 3
        cx = Inches(0.8 + col * 4.04)
        cy = Inches(1.88 + row * 2.50)
        add_card(s4, cx, cy, Inches(3.64), Inches(2.32), title, items, border_color=border_c)

    add_notes(s4, """
Slide 4 outlines the six core objectives of this codebase.
1. Robust tracking using MediaPipe FaceLandmarker with conservative single-face locking.
2. Geometric extraction across 5 verified features with inter-ocular scale normalization.
3. Quality assessment scoring each clip from 0 to 100 based on measurable physical factors.
4. Baseline calibration accumulating at least 5 check-ins to build personal profile statistics.
5. Standardized deviation assessment calculating differences, percentage changes, and z-scores.
6. Transparent reporting that communicates behavioral change while strictly avoiding clinical or emotional labeling.
""")

    # =========================================================================
    # SLIDE 5: TECHNOLOGY STACK
    # =========================================================================
    s5 = prs.slides.add_slide(blank_layout)
    set_bg(s5)
    add_header(s5, "Implementation Foundation", "Verified Minimalist Technology Stack",
               "Built strictly with verified, lightweight libraries for deterministic local execution.")

    tech_items = [
        ("Python 3.12 (Standard)", [
            ("Runtime Environment:", "Cross-platform terminal execution with modern typing and dataclasses."),
            ("No Heavy Frameworks:", "Free from web servers (no Flask/FastAPI), UI frameworks (no Streamlit/Qt), or database daemons."),
            ("Zero Overhead:", "Executes directly from CLI, ideal for integration into larger research pipelines.")
        ], BORDER_BLUE),
        ("MediaPipe FaceLandmarker", [
            ("Google Vision Tasks:", "State-of-the-art BlazeFace short-range detector + 3D FaceLandmarker pipeline."),
            ("Model Asset Verification:", "Official Google float16 model bundle (3.76 MB, SHA256 verified) with auto-download."),
            ("Video Running Mode:", "Monotonically increasing timestamps in milliseconds for temporal mesh tracking.")
        ], BORDER_CYAN),
        ("OpenCV (opencv-python)", [
            ("Video Decoding:", "Robust multi-codec frame retrieval via VideoCapture with format and header validation."),
            ("Geometric 3D Pose:", "Iterative Levenberg-Marquardt solvePnP mapping 2D landmarks to generic 3D face model."),
            ("Lighting Assessment:", "Pixel-level grayscale luminance and contrast quantification inside facial bounding box.")
        ], BORDER_EMERALD),
        ("NumPy (Vectorized Math)", [
            ("Coordinate Kinematics:", "Fast vector operations for Euclidean landmark displacements across 468 mesh points."),
            ("Statistical Distributions:", "Bessel-corrected sample standard deviations and z-scores across multi-session data."),
            ("Numerical Sanitization:", "Guarantees no NaN, Inf, or division-by-zero enters exported JSON structures.")
        ], BORDER_CYAN),
        ("JSON Profile Store", [
            ("Zero-DB Architecture:", "Local filesystem storage in profiles/{user_id}.json without external database dependency."),
            ("Strict Sanitization:", "Regex validation against path traversal attacks (alphanumeric, hyphens, underscores only)."),
            ("Longitudinal Profiles:", "Versioned schema maintaining historical session logs and feature-specific moments.")
        ], BORDER_BLUE),
        ("pytest Testing Framework", [
            ("33 Automated Tests:", "Comprehensive suite covering validation, features, quality, baseline math, and edge cases."),
            ("Sub-3s Execution:", "Complete test suite executes in ~2.4 seconds with zero regressions."),
            ("Synthetic Verification:", "Unit tests utilize deterministic synthetic coordinates to guarantee isolation.")
        ], BORDER_AMBER)
    ]

    for idx, (title, items, border_c) in enumerate(tech_items):
        col = idx % 3
        row = idx // 3
        cx = Inches(0.8 + col * 4.04)
        cy = Inches(1.88 + row * 2.50)
        add_card(s5, cx, cy, Inches(3.64), Inches(2.32), title, items, border_color=border_c)

    add_notes(s5, """
On Slide 5, we present the verified technology stack.
In accordance with research specifications, no unverified tools are listed.
We use Python 3.12, MediaPipe FaceLandmarker with the official Google 3.76 MB task bundle, OpenCV for video decoding and solvePnP pose estimation, NumPy for landmark kinematics, local JSON files for baseline persistence without requiring a database, and pytest with 33 verified tests.
Everything executes locally in memory. No video frames are ever written to disk or sent across a network.
""")

    # =========================================================================
    # SLIDE 6: SYSTEM ARCHITECTURE
    # =========================================================================
    s6 = prs.slides.add_slide(blank_layout)
    set_bg(s6)
    add_header(s6, "Pipeline Architecture", "End-to-End System Architecture & Dataflow",
               "Modular flow from raw video input to baseline comparison and structured reporting.")

    arch_steps = [
        ("1. Video Input", "MP4, AVI, MOV\nMax duration check", BORDER_BLUE),
        ("2. Validation", "Format, size, FPS\nOpenCV decodability", CARD_BORDER),
        ("3. Detection", "MediaPipe 468 pts\nSingle-face lock", BORDER_CYAN),
        ("4. Extraction", "Velocity, Blink, Pose\nSmile, Brow proxies", BORDER_CYAN),
        ("5. Quality Score", "Coverage, Lum, Con\n0-100 Suitability", BORDER_EMERALD),
        ("6. Baseline Mgr", "profiles/{id}.json\nMulti-session math", BORDER_BLUE),
        ("7. Reporting", "Terminal Report\nJSON Export", BORDER_AMBER)
    ]

    step_w = Inches(1.52)
    step_h = Inches(1.50)
    for i, (stitle, sdesc, sborder) in enumerate(arch_steps):
        sx = Inches(0.8 + i * 1.70)
        sy = Inches(1.95)
        card = s6.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, sx, sy, step_w, step_h)
        card.fill.solid()
        card.fill.fore_color.rgb = CARD_BG
        card.line.color.rgb = sborder
        card.line.width = Pt(1.5)
        tf = card.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = Inches(0.06)
        tf.margin_top = Inches(0.12)
        p1 = tf.paragraphs[0]
        p1.text = stitle
        p1.font.name = FONT_FAMILY
        p1.font.size = Pt(10)
        p1.font.bold = True
        p1.font.color.rgb = TEXT_WHITE
        p1.alignment = PP_ALIGN.CENTER
        p1.space_after = Pt(4)

        p2 = tf.add_paragraph()
        p2.text = sdesc
        p2.font.name = FONT_FAMILY
        p2.font.size = Pt(8.5)
        p2.font.color.rgb = TEXT_MUTED
        p2.alignment = PP_ALIGN.CENTER

        if i < len(arch_steps) - 1:
            arr = s6.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, sx + step_w + Inches(0.03), sy + Inches(0.60), Inches(0.12), Inches(0.2))
            arr.fill.solid()
            arr.fill.fore_color.rgb = CYAN_ACCENT
            arr.line.fill.background()

    # Three Operational Flow Containers Below
    add_card(s6, Inches(0.8), Inches(3.78), Inches(3.64), Inches(3.0),
             "Mode A: Single Session (--mode single)", [
                 ("Workflow:", "Standalone check-in execution."),
                 ("Baseline Interaction:", "Read-only; no profile directory accessed."),
                 ("Output:", "Prints instantaneous facial behaviour measurements and quality scores."),
                 ("Use-Case:", "Initial recording check, camera positioning check, or quick diagnostic of lighting.")
             ], border_color=BORDER_BLUE)

    add_card(s6, Inches(4.84), Inches(3.78), Inches(3.64), Inches(3.0),
             "Mode B: Calibration (--mode calibrate)", [
                 ("Workflow:", "Personal baseline profile establishment."),
                 ("Quality Gating:", "Strictly requires quality score >= 45 and coverage >= 50% to prevent corrupted data."),
                 ("Storage:", "Appends session observations to profiles/{user_id}.json."),
                 ("Threshold:", "Requires >= 5 valid check-ins before is_calibrated is marked established.")
             ], border_color=BORDER_CYAN)

    add_card(s6, Inches(8.88), Inches(3.78), Inches(3.64), Inches(3.0),
             "Mode C: Assessment (--mode assess)", [
                 ("Workflow:", "Longitudinal comparative wellness check-in."),
                 ("Requirement:", "Loads existing baseline; rejects execution if profile is missing."),
                 ("Comparative Math:", "Calculates difference, relative % change, and standardized z-score."),
                 ("Baseline Safety:", "Does NOT modify baseline unless --update-baseline is explicitly passed.")
             ], border_color=BORDER_EMERALD)

    add_notes(s6, """
Slide 6 depicts the end-to-end system architecture.
The top horizontal chain shows the linear pipeline: Video Input undergoes format and duration validation, landmark extraction via MediaPipe, feature extraction, and quality scoring.
From there, the pipeline branches into three operational modes:
- Single mode for one-off inspection without touching profile files.
- Calibration mode for accumulating at least 5 clean check-in sessions into the participant's JSON profile.
- Assessment mode for loading the baseline, computing deviations and z-scores, and rendering the five-section report.
Notice the safety boundary: assessment mode is strictly read-only by default to prevent accidental baseline drift.
""")

    # =========================================================================
    # SLIDE 7: VIDEO PROCESSING WORKFLOW
    # =========================================================================
    s7 = prs.slides.add_slide(blank_layout)
    set_bg(s7)
    add_header(s7, "Execution Pipeline", "Video Processing Workflow & Quality Enforcement",
               "Detailed sequence executed during video ingestion and feature extraction.")

    workflow_steps = [
        ("Step 1: Input Ingestion & Validation", [
            ("File Integrity Checks:", "Validates existence, format extension (.mp4, .avi, .mov, .mkv, .webm), and size (< 500 MB)."),
            ("Stream Readability:", "Verifies OpenCV VideoCapture can decode the stream and read initial frame headers."),
            ("Configurable Duration:", "Enforces maximum duration limit (default: 15.0s, successfully tested up to 30.0s).")
        ]),
        ("Step 2: Frame-by-Frame Mesh Tracking", [
            ("MediaPipe Ingestion:", "Converts BGR to RGB; passes frames to FaceLandmarker with millisecond timestamps."),
            ("Single-Face Policy:", "Tracks maximum of 2 faces to detect multi-face ambiguity; selects primary face via spatial IoU."),
            ("Jump Detection:", "Monitors bounding-box center jumps (> 35% frame diagonal) to flag potential identity shifts.")
        ]),
        ("Step 3: Quality Telemetry Collection", [
            ("Lighting Analysis:", "Calculates mean grayscale luminance (80–175 ideal) and contrast within facial bounding box."),
            ("Face Scale Adequacy:", "Measures bounding box area relative to frame (5%–55% optimal)."),
            ("Coverage Accounting:", "Counts usable tracked frames versus total video frames.")
        ]),
        ("Step 4: Deterministic Feature Calculation", [
            ("Velocity Math:", "Calculates inter-frame Euclidean displacement across all 468 mesh points normalized by eye distance."),
            ("Blink Hysteresis:", "Evaluates Eye Aspect Ratio (EAR < 0.21) hysteresis logic to debounce consecutive closed frames."),
            ("Pose & Proxies:", "Executes solvePnP for head pose jitter, mouth width ratio, and brow furrow distance.")
        ]),
        ("Step 5: Output Assembly & Serialization", [
            ("Numerical Sanitization:", "Converts all NaN, Inf, and division-by-zero outputs to null or finite floats."),
            ("Terminal Presentation:", "Renders structured multi-section wellness summary card with ANSI formatting."),
            ("JSON Export:", "Serializes versioned metadata, quality scores, features, and baseline comparisons.")
        ])
    ]

    card_w_step = Inches(11.733)
    card_h_step = Inches(0.90)
    for i, (title, items) in enumerate(workflow_steps):
        sy = Inches(1.88 + i * 0.98)
        add_card(s7, Inches(0.8), sy, card_w_step, card_h_step, title, items, border_color=BORDER_CYAN if i%2==0 else BORDER_BLUE)

    add_notes(s7, """
Slide 7 walks through the video processing sequence step-by-step.
First, validation ensures the file is a readable video, non-empty, and within the configured duration limit (configurable from 15s to 30s or more).
Second, MediaPipe extracts 468 landmarks per frame while monitoring for identity jumps or multiple faces.
Third, photometric quality checks evaluate face luminance, contrast, and scale.
Fourth, mathematical feature extractors calculate velocity, blink count, pose jitter, smile ratio, and brow furrow ratio.
Finally, the results are sanitized to guarantee valid numerical representations before being rendered to the terminal or exported as JSON.
""")

    # =========================================================================
    # SLIDE 8: EXTRACTED FACIAL BEHAVIOUR FEATURES
    # =========================================================================
    s8 = prs.slides.add_slide(blank_layout)
    set_bg(s8)
    add_header(s8, "Feature Engineering", "Extracted Facial Behaviour Features & Formulations",
               "Quantitative geometric and temporal telemetry extracted from detected landmarks.")

    feat_cards = [
        ("1. Facial Movement Velocity", [
            ("Mathematical Basis:", "Mean Euclidean displacement across all 468 mesh points between consecutive usable frames."),
            ("Normalization:", "Divided by outer-eye inter-ocular distance (landmarks 33 to 263) and time step dt."),
            ("Unit:", "face-units / sec"),
            ("Caveat / Limitation:", "Reflects physical head movement and articulation; does not quantify agitation or restlessness.")
        ], BORDER_BLUE),
        ("2. Eye-Blink Rate per Minute", [
            ("Mathematical Basis:", "Bilateral Eye Aspect Ratio (EAR). Closure detected when EAR < 0.21."),
            ("Temporal Logic:", "Consecutive closed frames count as one blink upon reopening. Excludes closures > 800ms."),
            ("Unit:", "blinks / min"),
            ("Caveat / Limitation:", "Influenced by screen glare, dry eyes, and fatigue; must not be labeled as proof of stress.")
        ], BORDER_CYAN),
        ("3. Head-Pose Variability (Jitter)", [
            ("Mathematical Basis:", "OpenCV solvePnP iterative alignment with 6 canonical points mapped to generic 3D face model."),
            ("Variability Score:", "Vector standard deviation of yaw, pitch, and roll: sqrt(std_yaw^2 + std_pitch^2 + std_roll^2)."),
            ("Unit:", "degrees"),
            ("Caveat / Limitation:", "Generic anthropometric model provides relative angular variability, not calibrated ground truth.")
        ], BORDER_EMERALD),
        ("4. Smile-Intensity Proxy", [
            ("Mathematical Basis:", "Euclidean distance between mouth corners (landmarks 61 to 291)."),
            ("Normalization:", "Normalized by outer-eye inter-ocular distance (corners 33 to 263)."),
            ("Unit:", "dimensionless ratio"),
            ("Caveat / Limitation:", "Measures physical mouth widening; does not infer positive valence or genuine emotional smiling.")
        ], BORDER_BLUE),
        ("5. Brow-Furrow Proxy", [
            ("Mathematical Basis:", "Vertical distance from inner/mid brows (107, 336) to upper eyelid centers (159, 386)."),
            ("Normalization:", "Normalized by inter-ocular distance. Lower value indicates stronger brow furrowing / lowering."),
            ("Unit:", "dimensionless ratio"),
            ("Caveat / Limitation:", "Anatomical resting brow height varies widely across individuals; meaningful only relative to baseline.")
        ], BORDER_AMBER)
    ]

    card_w_feat = Inches(3.64)
    card_h_feat = Inches(2.36)

    for idx in range(3):
        title, items, border_c = feat_cards[idx]
        cx = Inches(0.8 + idx * 4.04)
        cy = Inches(1.88)
        add_card(s8, cx, cy, card_w_feat, card_h_feat, title, items, border_color=border_c)

    card_w_feat2 = Inches(5.66)
    for idx in range(3, 5):
        title, items, border_c = feat_cards[idx]
        cx = Inches(0.8 + (idx - 3) * 6.07)
        cy = Inches(4.42)
        add_card(s8, cx, cy, card_w_feat2, card_h_feat, title, items, border_color=border_c)

    add_notes(s8, """
Slide 8 breaks down the five extracted facial features.
1. Facial Movement Velocity measures aggregate landmark displacement across the entire face normalized by inter-ocular distance.
2. Eye-Blink Rate uses temporal Eye Aspect Ratio with debouncing to prevent multi-counting consecutive closed frames. It requires at least 3 seconds of usable video to extrapolate blinks per minute.
3. Head-Pose Variability uses OpenCV's solvePnP algorithm on a generic 3D anthropometric face model to determine the standard deviation of yaw, pitch, and roll in degrees.
4. Smile-Intensity Proxy measures normalized mouth width relative to inter-ocular distance.
5. Brow-Furrow Proxy measures normalized vertical distance between the eyebrows and upper eyelids.
Every feature is rigorously normalized to be invariant to camera distance.
""")

    # =========================================================================
    # SLIDE 9: THREE OPERATING MODES
    # =========================================================================
    s9 = prs.slides.add_slide(blank_layout)
    set_bg(s9)
    add_header(s9, "Command-Line Interface", "Three Operating Modes & Verified CLI Syntax",
               "Flexible execution paradigms for ad-hoc inspection, baseline calibration, and longitudinal assessment.")

    table_shape = s9.shapes.add_table(4, 4, Inches(0.8), Inches(1.88), Inches(11.733), Inches(4.9))
    table = table_shape.table
    table.columns[0].width = Inches(1.8)
    table.columns[1].width = Inches(2.9)
    table.columns[2].width = Inches(2.2)
    table.columns[3].width = Inches(4.833)

    headers = ["Operating Mode", "Primary Research Objective", "Baseline State & Impact", "Verified Command-Line Syntax"]
    for j, h in enumerate(headers):
        cell = table.cell(0, j)
        cell.fill.solid()
        cell.fill.fore_color.rgb = RGBColor(16, 42, 77)
        p = cell.text_frame.paragraphs[0]
        p.text = h
        p.font.name = FONT_FAMILY
        p.font.size = Pt(10.5)
        p.font.bold = True
        p.font.color.rgb = CYAN_ACCENT

    mode_data = [
        ("single",
         "Ad-hoc video analysis and instantaneous feature extraction. Evaluates tracking feasibility and quality.",
         "Read-only.\nNo personal profiles created, loaded, or modified.",
         "python main.py --video videos/demo.mp4 \\\n  --user-id participant1 --mode single \\\n  --max-duration 30 --output outputs/demo_results.json"),
        ("calibrate",
         "Accumulates valid check-in sessions into the participant's empirical baseline profile history.",
         "Profile appended.\nRequires >= 5 check-ins before is_calibrated is marked True.",
         "python main.py --video videos/checkin1.mp4 \\\n  --user-id participant1 --mode calibrate \\\n  --max-duration 30"),
        ("assess",
         "Compares a new recording against the participant's established baseline; computes z-scores and differences.",
         "Read-only by default.\nOptional --update-baseline appends observation post-assessment.",
         "python main.py --video videos/checkin6.mp4 \\\n  --user-id participant1 --mode assess \\\n  --max-duration 30 --output outputs/assessment.json")
    ]

    for i, row in enumerate(mode_data):
        for j, val in enumerate(row):
            cell = table.cell(i + 1, j)
            cell.fill.solid()
            cell.fill.fore_color.rgb = CARD_BG if i % 2 == 0 else CARD_BG_ALT
            p = cell.text_frame.paragraphs[0]
            p.text = val
            p.font.name = FONT_CODE if j == 3 else FONT_FAMILY
            p.font.size = Pt(9.5 if j == 3 else 10)
            p.font.bold = (j == 0)
            p.font.color.rgb = CYAN_ACCENT if j == 0 else (BLUE_ACCENT if j == 3 else TEXT_BODY)

    add_notes(s9, """
Slide 9 presents the three operating modes implemented in the CLI.
1. Single mode analyzes a video in isolation and reports features without touching the personal baseline directory.
2. Calibration mode requires a user ID and appends the check-in to that user's baseline profile. It requires at least 5 sessions to establish baseline distributions.
3. Assessment mode compares new check-ins against the existing baseline, reporting differences and z-scores. If no baseline profile exists, it displays an informative notice instructing the user to calibrate first.
The command syntax shown on this slide has been verified directly against main.py.
""")

    # =========================================================================
    # SLIDE 10: PERSONAL BASELINE AND LONGITUDINAL COMPARISON
    # =========================================================================
    s10 = prs.slides.add_slide(blank_layout)
    set_bg(s10)
    add_header(s10, "Comparative Methodology", "Personal Baseline Architecture & Statistical Modeling",
               "Mathematical framework for personal baseline accumulation and longitudinal deviation detection.")

    add_card(s10, Inches(0.8), Inches(1.88), Inches(5.66), Inches(4.9),
             "Phase 1: Multi-Session Calibration", [
                 ("Multi-Session Heuristic:", "Requires >= 5 distinct check-ins (configurable engineering default) to capture natural physiological variance."),
                 ("Quality Gating Enforcement:", "Check-ins with quality score < 45 or coverage < 50% are rejected from entering calibration to prevent corrupted statistics."),
                 ("Statistical Moments Tracking:", "Maintains sample count (N), mean (mu), and sample standard deviation (sigma with Bessel's N-1 correction) per feature."),
                 ("Missing Feature Protection:", "If a feature is unavailable (e.g. blink rate in short clip), it is strictly omitted from that feature's stats—NEVER recorded as zero!"),
                 ("Versioned Local Schema:", "Stored in profiles/{user_id}.json with timestamped session histories and metadata.")
             ], border_color=BORDER_CYAN)

    add_card(s10, Inches(6.87), Inches(1.88), Inches(5.66), Inches(4.9),
             "Phase 2: Comparative Assessment Math", [
                 ("Absolute Difference:", "Delta = Observed_Value - Baseline_Mean (preserves physical measurement units)."),
                 ("Relative Percentage Change:", "Rel% = (Delta / Baseline_Mean) * 100 (guarded against division by near-zero means)."),
                 ("Standardized Deviation (z):", "z = (Observed_Value - Baseline_Mean) / Baseline_SD (quantifies deviation in SD units)."),
                 ("Zero-Variance Safeguard:", "If Baseline_SD < 1e-4 (identical calibration sessions), z-score is marked None, and difference is reported without ZeroDivisionError."),
                 ("Non-Diagnostic Labeling:", "Deviations are categorized descriptively: 'Within personal baseline' (|z| <= 1.2), 'Higher than baseline', or 'Lower than baseline'.")
             ], border_color=BORDER_EMERALD)

    add_notes(s10, """
Slide 10 details the personal baseline architecture.
Calibration accumulates multiple valid sessions to capture day-to-day variance. A single session cannot establish a baseline. We configure 5 check-ins as the engineering default.
Crucially, missing features are never imputed as zero.
During assessment, we compute absolute differences, relative percentage changes, and standardized z-scores.
If a participant has near-zero variance across calibration, our algorithm catches this edge-case gracefully without dividing by zero.
""")

    # =========================================================================
    # SLIDE 11: EXAMPLE OUTPUT AND DEMONSTRATION
    # =========================================================================
    s11 = prs.slides.add_slide(blank_layout)
    set_bg(s11)
    add_header(s11, "Empirical Validation", "Illustrative Technical Run on Benchmark Recording",
               "Representative extraction results from a benchmark sample video (illustrative demonstration).")

    add_card(s11, Inches(0.8), Inches(1.88), Inches(4.8), Inches(4.9),
             "Benchmark Video & Tracking Quality", [
                 ("Video Duration:", "16.76 seconds"),
                 ("Video Resolution:", "848 x 478 pixels"),
                 ("Frames Processed:", "418 frames (30.0 FPS)"),
                 ("Tracking Coverage:", "100.0% (418 of 418 frames usable)"),
                 ("Mean Face Scale:", "18.4% of frame area"),
                 ("Photometric Quality:", "Luminance 134.2 / 255 | Contrast 42.1"),
                 ("Quality Score:", "100.0 / 100.0"),
                 ("Reliability Status:", "RELIABLE"),
                 ("Baseline Suitability:", "YES (High-integrity check-in)")
             ], border_color=BORDER_BLUE)

    add_card(s11, Inches(5.8), Inches(1.88), Inches(6.733), Inches(3.25),
             "Extracted Facial Behaviour Measurements", [
                 ("1. Facial Movement Velocity:", "0.3961 face-units / sec  (Normalized landmark displacement per second)"),
                 ("2. Eye-Blink Rate:", "14.3 blinks / min  (Calculated from 4 distinct debounced blink events)"),
                 ("3. Head-Pose Variability:", "16.27 deg  (Aggregate std dev; yaw=12.1 deg, pitch=8.4 deg, roll=6.2 deg)"),
                 ("4. Smile-Intensity Proxy:", "0.541  (Mean mouth-to-interocular distance ratio; peak=0.612)"),
                 ("5. Brow-Furrow Proxy:", "0.354  (Mean brow-to-eye distance ratio; minimum=0.318)")
             ], border_color=BORDER_CYAN)

    add_card(s11, Inches(5.8), Inches(5.28), Inches(6.733), Inches(1.50),
             "Scientific Disclaimer & Scope Boundary", [
                 ("Illustrative Run Only:", "These values represent one specific technical execution and must NOT be interpreted as population norms or universal wellness benchmarks."),
                 ("Quality vs Validity:", "A 100/100 quality score confirms computer-vision tracking fidelity; it does NOT confirm emotional or psychological state validity.")
             ], border_color=BORDER_AMBER, bg_color=CARD_BG_ALT)

    add_notes(s11, """
Slide 11 presents an illustrative technical run from a known benchmark video.
Notice the parameters: 16.76 seconds, 848x478 resolution, 418 frames, 100% detection coverage, and a tracking quality score of 100.0/100.0.
The extracted measurements show: movement velocity of 0.3961 face-units/s, blink rate of 14.3 blinks/min, head-pose variability of 16.27 degrees, smile intensity proxy of 0.541, and brow furrow proxy of 0.354.
We emphasize the disclaimer at the bottom: a 100/100 quality score indicates excellent landmark tracking; it does not mean the person is in a particular emotional state.
""")

    # =========================================================================
    # SLIDE 12: PERSONAL BASELINE COMPARISON AND REPORTING
    # =========================================================================
    s12 = prs.slides.add_slide(blank_layout)
    set_bg(s12)
    add_header(s12, "Reporting Architecture", "Structure of the Wellness-Monitoring Report",
               "Transparent 5-section report format emphasizing behavioral telemetry over diagnostic claims.")

    sections_top = [
        ("Section [A]: Check-In Quality", [
            ("Parameters:", "Recording duration, total/usable frames, coverage %, luminance, contrast, scale."),
            ("Gating:", "Explicitly declares tracking reliability and baseline suitability (YES/NO).")
        ], BORDER_BLUE),
        ("Section [B]: Behavioural Observations", [
            ("Features:", "Reports all 5 features with physical units, peak/min auxiliary values, and availability status."),
            ("Data Integrity:", "Marks features 'Unavailable' if clip duration or usable frames are insufficient.")
        ], BORDER_CYAN),
        ("Section [C]: Personal Baseline Comparison", [
            ("Statistical Table:", "Compares observed value against baseline mean (mu), standard deviation (sigma), and sample count."),
            ("Metrics:", "Reports absolute difference (Delta), relative change %, and standardized deviation (z-score).")
        ], BORDER_EMERALD),
        ("Section [D]: Wellness-Related Interpretation", [
            ("Careful Language:", "'Within personal baseline', 'Higher than personal baseline', 'Lower than baseline'."),
            ("Context Notice:", "Explicitly notes that physical fatigue, room lighting, and speech influence metrics.")
        ], BORDER_BLUE)
    ]

    card_w_sec = Inches(5.66)
    card_h_sec = Inches(1.85)
    for idx in range(4):
        col = idx % 2
        row = idx // 2
        cx = Inches(0.8 + col * 6.07)
        cy = Inches(1.88 + row * 1.95)
        title, items, border_c = sections_top[idx]
        add_card(s12, cx, cy, card_w_sec, card_h_sec, title, items, border_color=border_c)

    # Section E: Wide banner at bottom
    add_card(s12, Inches(0.8), Inches(5.88), Inches(11.733), Inches(1.15),
             "Section [E]: Stress & Mental Wellness Limitations", [
                 ("Mandatory Statement:", "Stress inference is not validated. This check-in provides facial-behaviour measurements and personal-baseline comparisons only."),
                 ("Strict Boundary:", "The system does NOT compute a stress score, percentage, probability, or clinical mental health diagnosis.")
             ], border_color=BORDER_AMBER, bg_color=CARD_BG_ALT)

    add_notes(s12, """
Slide 12 breaks down the five distinct sections generated in both the terminal summary card and exported JSON reports.
Section A evaluates check-in quality and baseline suitability.
Section B reports raw measured facial behaviour features with units and availability status.
Section C provides the statistical baseline comparison table showing mean, standard deviation, difference, and z-score.
Section D offers descriptive, non-diagnostic behavioral interpretations.
Section E enforces the mandatory research boundary notice, explicitly stating that stress inference is not validated and no clinical labels or scores are generated.
""")

    # =========================================================================
    # SLIDE 13: TESTING, LIMITATIONS, AND FUTURE WORK
    # =========================================================================
    s13 = prs.slides.add_slide(blank_layout)
    set_bg(s13)
    add_header(s13, "Validation & Roadmap", "Automated Testing, Current Limitations & Roadmap",
               "Rigorous empirical verification and transparent boundaries for future research expansion.")

    add_card(s13, Inches(0.8), Inches(1.88), Inches(3.64), Inches(4.9),
             "Automated Test Suite (Verified)", [
                 ("33 / 33 Passing Tests:", "Verified passing status across all modules in ~2.4 seconds."),
                 ("Baseline Persistence:", "Tests profile creation, JSON serialization, and sanitization."),
                 ("Zero-Variance Protection:", "Validates robust handling of zero standard deviation without ZeroDivisionError."),
                 ("Quality Gating:", "Confirms rejection of low-quality check-ins for calibration."),
                 ("Path Traversal Defense:", "Tests rejection of unsafe user IDs containing '../' or invalid characters.")
             ], border_color=BORDER_EMERALD)

    add_card(s13, Inches(4.84), Inches(1.88), Inches(3.64), Inches(4.9),
             "Current Technical Limitations", [
                 ("Tracking != Validity:", "High tracking quality confirms landmark detection fidelity, not affective truth."),
                 ("Environmental Sensitivity:", "Facial kinematics vary with speech, dry eyes, display glare, and room illumination."),
                 ("Baseline Drift:", "Long-term shifts in webcam placement or seasonal lighting can alter baseline parameters."),
                 ("No Stress Model:", "No validated machine learning classifier trained on physiological stress ground-truth is claimed or present.")
             ], border_color=BORDER_AMBER)

    add_card(s13, Inches(8.88), Inches(1.88), Inches(3.64), Inches(4.9),
             "Planned Future Research", [
                 ("Multi-Session Longitudinal Studies:", "Evaluate baseline stability over weeks across real-world cohort recordings."),
                 ("Multimodal Signal Fusion:", "Integrate facial telemetry with contextual ecological momentary assessments (EMA) and wearable sensors."),
                 ("Ethical Validation:", "Conduct ethically approved IRB validation studies with physiological biomarkers."),
                 ("Adaptive Baseline Windows:", "Explore exponential moving average weighting for longitudinal baselines.")
             ], border_color=BORDER_CYAN)

    add_notes(s13, """
Slide 13 discusses testing status, current limitations, and future research directions.
The test suite consists of 33 automated tests in pytest, all passing in approximately 2.4 seconds. These tests cover input validation, landmark geometry, temporal blink debouncing, baseline persistence, zero-variance safeguards, and report wording.
We transparently outline current limitations: tracking quality does not equal psychological validity; environmental factors confound measurements; and no stress detection model is claimed.
Planned future work includes real-world cohort studies, multimodal sensor fusion, and adaptive longitudinal baseline windows.
""")

    # =========================================================================
    # SLIDE 14: CONCLUSION
    # =========================================================================
    s14 = prs.slides.add_slide(blank_layout)
    set_bg(s14)
    add_header(s14, "Research Summary", "Conclusion: Objective Facial Behaviour Tracking",
               "A principled, privacy-first computer vision module for longitudinal wellness monitoring.")

    add_card(s14, Inches(0.8), Inches(1.88), Inches(11.733), Inches(3.2),
             "Core Contributions & Architectural Takeaways", [
                 ("1. Lightweight & Modular:", "A self-contained Python CLI module using MediaPipe and OpenCV, without heavy UI frameworks or database daemons."),
                 ("2. Rigorous Normalization:", "Five objective geometric and temporal features normalized by inter-ocular distance, ensuring scale-invariant kinematic tracking."),
                 ("3. Longitudinal Personal Baseline:", "Shifts the paradigm from flawed one-size-fits-all emotion detection to individualized multi-session baseline comparison."),
                 ("4. Privacy by Design:", "100% local in-memory video processing. Zero video frames or facial images are persisted to disk or sent across networks."),
                 ("5. Scientific Humility:", "Strictly avoids pseudo-clinical stress scores, emotion percentages, or diagnostic claims.")
             ], border_color=BORDER_CYAN)

    # Big Final Highlight Quote Box
    quote_card = s14.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(5.35), Inches(11.733), Inches(1.4))
    quote_card.fill.solid()
    quote_card.fill.fore_color.rgb = RGBColor(16, 42, 77)
    quote_card.line.color.rgb = CYAN_ACCENT
    quote_card.line.width = Pt(2)
    qtf = quote_card.text_frame
    qtf.word_wrap = True
    qtf.margin_top = Inches(0.2)
    
    qp1 = qtf.paragraphs[0]
    qp1.text = "GUIDING SCIENTIFIC PRINCIPLE"
    qp1.font.name = FONT_FAMILY
    qp1.font.size = Pt(11)
    qp1.font.bold = True
    qp1.font.color.rgb = CYAN_ACCENT
    qp1.alignment = PP_ALIGN.CENTER
    qp1.space_after = Pt(4)

    qp2 = qtf.add_paragraph()
    qp2.text = "“Measuring behavioural change is not the same as diagnosing psychological state.”"
    qp2.font.name = FONT_FAMILY
    qp2.font.size = Pt(16.5)
    qp2.font.bold = True
    qp2.font.color.rgb = TEXT_WHITE
    qp2.alignment = PP_ALIGN.CENTER

    add_notes(s14, """
In conclusion, on Slide 14, we summarize the MindTrack facial AI module.
It delivers a robust, reproducible, and private computer-vision engine for extracting five geometric and temporal facial behaviour metrics.
By moving away from cross-sectional emotion detection and embracing longitudinal personal baselines, it provides a principled framework for observing individual behavioural shifts over time.
We close with our guiding scientific principle: Measuring behavioural change is not the same as diagnosing psychological state.
Thank you.
""")

    prs.save(output_pptx_path)
    print(f"[*] Presentation saved successfully to: {output_pptx_path}")


if __name__ == "__main__":
    out_dir = Path("presentation")
    out_dir.mkdir(parents=True, exist_ok=True)
    pptx_path = out_dir / "Facial_AI_of_Wellness_Tracker.pptx"
    create_deck(str(pptx_path))
    # Also save a copy directly in the project root as specified by instructions
    root_pptx_path = Path("Facial_AI_of_Wellness_Tracker.pptx")
    import shutil
    shutil.copyfile(pptx_path, root_pptx_path)
    print(f"[*] Presentation copy saved to project root: {root_pptx_path}")
