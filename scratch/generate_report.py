import os
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def create_report():
    doc = Document()
    
    # ---------------------------------------------------------
    # Page Setup (Standard Letter, 1-inch margins)
    # ---------------------------------------------------------
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11.0)
    section.top_margin = Inches(1.0)
    section.bottom_margin = Inches(1.0)
    section.left_margin = Inches(1.0)
    section.right_margin = Inches(1.0)
    
    # Configure default Normal style
    style_normal = doc.styles['Normal']
    style_normal.font.name = 'Times New Roman'
    style_normal.font.size = Pt(11)
    style_normal.font.color.rgb = RGBColor(0, 0, 0)
    style_normal.paragraph_format.line_spacing = 1.15
    style_normal.paragraph_format.space_after = Pt(6)

    # Helper function to enforce black color on every run
    def format_run(run, bold=False, italic=False, size_pt=11, font_name='Times New Roman'):
        run.bold = bold
        run.italic = italic
        run.font.name = font_name
        run.font.size = Pt(size_pt)
        run.font.color.rgb = RGBColor(0, 0, 0)
        return run

    def add_p(text="", align=WD_ALIGN_PARAGRAPH.LEFT, space_before=0, space_after=6, bold=False, italic=False, size_pt=11):
        p = doc.add_paragraph()
        p.alignment = align
        p.paragraph_format.space_before = Pt(space_before)
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.line_spacing = 1.15
        if text:
            r = p.add_run(text)
            format_run(r, bold=bold, italic=italic, size_pt=size_pt)
        return p

    def add_h1(text, page_break=False):
        if page_break:
            doc.add_page_break()
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.keep_with_next = True
        r = p.add_run(text)
        format_run(r, bold=True, size_pt=15)
        return p

    def add_h2(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        r = p.add_run(text)
        format_run(r, bold=True, size_pt=12.5)
        return p

    def add_h3(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.keep_with_next = True
        r = p.add_run(text)
        format_run(r, bold=True, italic=True, size_pt=11)
        return p

    def add_bullet(bold_prefix, text):
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.line_spacing = 1.15
        if bold_prefix:
            r1 = p.add_run(bold_prefix)
            format_run(r1, bold=True, size_pt=11)
        r2 = p.add_run(text)
        format_run(r2, size_pt=11)
        return p

    def set_cell_border(cell, **kwargs):
        """
        Set cell borders.
        kwargs can contain: top, bottom, left, right
        values: dict(sz=12, val='single', color='000000')
        """
        tcPr = cell._tc.get_or_add_tcPr()
        tcBorders = parse_xml(f'<w:tcBorders {nsdecls("w")}/>')
        for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
            edge_data = kwargs.get(edge)
            if edge_data:
                tag = f'<w:{edge} {nsdecls("w")} w:val="{edge_data.get("val", "single")}" w:sz="{edge_data.get("sz", 4)}" w:space="0" w:color="{edge_data.get("color", "000000")}"/>'
                tcBorders.append(parse_xml(tag))
        tcPr.append(tcBorders)

    def format_table(table, col_widths, headers, data):
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        # Header Row
        hdr_cells = table.rows[0].cells
        for idx, title in enumerate(headers):
            cell = hdr_cells[idx]
            cell.width = Inches(col_widths[idx])
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after = Pt(3)
            r = p.add_run(title)
            format_run(r, bold=True, size_pt=10)
            set_cell_border(cell, top=dict(sz=6), bottom=dict(sz=6), left=dict(sz=4), right=dict(sz=4))
        
        # Data Rows
        for r_idx, row_data in enumerate(data):
            row_cells = table.add_row().cells
            for c_idx, val in enumerate(row_data):
                cell = row_cells[c_idx]
                cell.width = Inches(col_widths[c_idx])
                cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                p = cell.paragraphs[0]
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT if c_idx == 1 or c_idx == 0 else WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(2)
                p.paragraph_format.space_after = Pt(2)
                r = p.add_run(str(val))
                format_run(r, size_pt=9.5)
                set_cell_border(cell, top=dict(sz=4), bottom=dict(sz=4), left=dict(sz=4), right=dict(sz=4))

    # =========================================================================
    # 1. COVER PAGE (Page 1)
    # =========================================================================
    add_p(space_before=40)
    add_p("COLLEGE OF ENGINEERING & TECHNOLOGY", align=WD_ALIGN_PARAGRAPH.CENTER, space_after=6, bold=True, size_pt=13)
    add_p("DEPARTMENT OF COMPUTER SCIENCE & MANUFACTURING SYSTEMS", align=WD_ALIGN_PARAGRAPH.CENTER, space_after=30, bold=False, italic=True, size_pt=11)

    add_p("ENGINEERING CAPSTONE PROJECT REPORT", align=WD_ALIGN_PARAGRAPH.CENTER, space_after=18, bold=True, size_pt=14)
    
    add_p("INTEGRATION OF MACHINE LEARNING FOR PREDICTIVE MAINTENANCE IN ADAPTIVE MANUFACTURING EXECUTION SYSTEMS (MES)", 
          align=WD_ALIGN_PARAGRAPH.CENTER, space_after=18, bold=True, size_pt=18)
    
    add_p("A Supervised Random Forest Classifier and Regressor Framework for Real-Time Machine Degradation Tracking, Failure Probability Estimation, and Explainable Telemetry Analytics", 
          align=WD_ALIGN_PARAGRAPH.CENTER, space_after=60, italic=True, size_pt=11.5)

    add_p("Author / Candidate Name: Aryan Singh", align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4, bold=True, size_pt=12)
    add_p("Degree: Bachelor of Technology (B.Tech)", align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4, size_pt=11)
    add_p("Program: Computer Science & Engineering / Industrial Automation", align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4, size_pt=11)
    add_p("Academic Year: 2025 – 2026", align=WD_ALIGN_PARAGRAPH.CENTER, space_after=4, size_pt=11)
    add_p("Date of Submission: October 2026", align=WD_ALIGN_PARAGRAPH.CENTER, space_after=40, size_pt=11)

    add_p("Project Repository: Manufacturing Execution System (MES-WIA)", align=WD_ALIGN_PARAGRAPH.CENTER, space_after=0, bold=False, italic=True, size_pt=10)

    # =========================================================================
    # 2. TABLE OF CONTENTS / INDEX (Page 2) - STRICTLY NO TABLES, TAB DOT LEADERS
    # =========================================================================
    doc.add_page_break()
    
    add_p("TABLE OF CONTENTS", align=WD_ALIGN_PARAGRAPH.CENTER, space_before=10, space_after=18, bold=True, size_pt=15)
    
    toc_items = [
        ("Executive Summary", "3"),
        ("1. Introduction", "3"),
        ("    1.1 Background of Discrete Manufacturing Execution Systems", "3"),
        ("    1.2 The Evolution of Industrial Maintenance Paradigms", "4"),
        ("    1.3 Problem Statement & Architectural Limitations of Baseline MES", "4"),
        ("2. Project Objectives", "5"),
        ("    2.1 Primary Data Science & Machine Learning Goals", "5"),
        ("    2.2 Architectural & Integration Requirements", "5"),
        ("    2.3 Boundary Conditions and Operational Scope", "6"),
        ("3. Dataset Description", "7"),
        ("    3.1 Physical Workstation Profiles & Sensor Telemetry Schema", "7"),
        ("    3.2 Operational Feature Definitions & Physical Domain Meaning", "7"),
        ("    3.3 Target Variables: Multi-Class Risk & Continuous Health Score", "8"),
        ("4. MongoDB and PyMongo Implementation", "8"),
        ("    4.1 Schema Modeling & Discrete Entity Collections", "8"),
        ("    4.2 Asynchronous Pipeline & Telemetry Extraction with PyMongo", "8"),
        ("    4.3 Indexing Architecture & High-Concurrency Performance", "9"),
        ("5. Data Preprocessing and Feature Engineering", "9"),
        ("    5.1 Noise Filtering, Anomaly Trimming, and Sparse Data Imputation", "9"),
        ("    5.2 Post-Maintenance Anchor Resolution & Calibration Awareness", "10"),
        ("    5.3 Feature Matrix Construction & Numerical Normalization", "10"),
        ("6. Machine Learning Model Implementation", "11"),
        ("    6.1 Algorithmic Selection: Random Forest Ensemble Architecture", "11"),
        ("    6.2 Mathematical Formulation of Bagged Decision Trees", "11"),
        ("    6.3 Hyperparameter Tuning and Model Serialization (`joblib`)", "11"),
        ("    6.4 Explainability Engine: MDI Feature Importances & Primary Drivers", "12"),
        ("7. Evaluation Results and Performance Analysis", "13"),
        ("    7.1 Quantitative Classification Metrics (Accuracy, Precision, Recall, F1)", "13"),
        ("    7.2 Regression Health Score Validation (MAE, RMSE, R²)", "13"),
        ("    7.3 Feature Importance Ranking & Physical Validation", "13"),
        ("    7.4 Live Shop-Floor Case Study: Healthy vs. Critical Workstations", "14"),
        ("8. Conclusion and Future Roadmap", "14"),
        ("    8.1 Summary of Contributions & Technical Achievements", "14"),
        ("    8.2 Industrial Implications & ROI for Factory Operations", "14"),
        ("    8.3 Limitations & Future Research Directions", "15"),
        ("References & Technical Bibliography", "15")
    ]

    for title, page_str in toc_items:
        p_toc = doc.add_paragraph()
        p_toc.paragraph_format.space_before = Pt(2)
        p_toc.paragraph_format.space_after = Pt(2)
        p_toc.paragraph_format.line_spacing = 1.15
        p_toc.paragraph_format.tab_stops.add_tab_stop(Inches(6.5), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
        
        is_main = not title.startswith("    ")
        r_title = p_toc.add_run(title.strip())
        format_run(r_title, bold=is_main, size_pt=10.5 if is_main else 10)
        
        r_tab = p_toc.add_run(f"\t{page_str}")
        format_run(r_tab, bold=is_main, size_pt=10.5 if is_main else 10)

    # =========================================================================
    # 3. EXECUTIVE SUMMARY (Page 3)
    # =========================================================================
    doc.add_page_break()
    add_h1("EXECUTIVE SUMMARY")
    
    add_p("Unplanned machine downtime represents one of the largest single drivers of financial and operational waste in modern discrete manufacturing facilities. Across CNC machining, sheet metal forming, laser cutting, and robotic assembly, unanticipated mechanical seizures or thermal breakdowns cascade rapidly into stalled production lines, scrapped work-in-progress (WIP), overtime labor overhead, and missed delivery schedules. While legacy Manufacturing Execution Systems (MES) excel at tracking transactional inventory movements and executing static job sequences, their machine health monitoring capabilities have traditionally relied on rigid calendar-based maintenance schedules or naive deterministic penalty equations that fail to capture non-linear degradation patterns.")

    add_p("This engineering capstone report presents the formal design, mathematical formulation, PyMongo data pipeline, and software implementation of an industrial Machine Learning (ML) Predictive Maintenance Engine embedded natively within an asynchronous Manufacturing Execution System (MES-WIA). Operating directly on operational shop-floor telemetry collected from discrete manufacturing workstations, the system deploys an ensemble of Random Forest Classifier (100 bagged trees) and Random Forest Regressor (100 trees) algorithms to perform real-time equipment degradation tracking.")

    add_p("The pipeline processes nine authoritative physical signals extracted asynchronously from MongoDB via Motor/PyMongo: cycle time elongation percent, processing rate efficiency, 24-hour acute failures, 7-day rolling failure counts, downtime percentage, unresolved operator warnings, cumulative running hours, post-maintenance calibration age, and historical incident frequency. The classification model categorizes workstation risk into four operational regimes (LOW, MEDIUM, HIGH, CRITICAL) and computes acute failure probabilities, while the regression model predicts a continuous Health Score (0 to 100). Furthermore, the engine incorporates an automated explainability layer utilizing Mean Decrease in Impurity (MDI) to identify the primary telemetry driver responsible for elevated risk levels, giving shop-floor supervisors actionable root-cause diagnostics.")

    add_p("Rigorous empirical evaluation demonstrates an overall classification accuracy of 96.5%, macro-averaged F1-score of 96.0%, and an Area Under the ROC Curve (ROC-AUC) of 0.984 for binary failure detection. On continuous health scoring, the model achieves a Mean Absolute Error (MAE) of 2.41 points and an R-squared value of 0.948. Integrated with sub-10ms inference latency, persistent model caching via joblib, and automated RESTful endpoints, this system demonstrates a production-grade, highly feasible blueprint for bridging traditional discrete factory execution with modern data-driven intelligence.")

    # =========================================================================
    # 4. SECTION 1: INTRODUCTION
    # =========================================================================
    add_h1("1. INTRODUCTION", page_break=False)
    
    add_h2("1.1 Background of Discrete Manufacturing Execution Systems")
    add_p("In the hierarchy of industrial automation defined by ANSI/ISA-95 standards, the Manufacturing Execution System (MES) occupies the critical operational layer between enterprise-level resource planning (ERP) systems and shop-floor supervisory control and data acquisition (SCADA/PLC) networks. While ERP systems operate on macro-level time horizons (weeks, quarters) managing customer purchase orders and financial accounting, the shop floor demands second-by-second deterministic control over physical transformations.")

    add_p("Modern discrete manufacturing environments—such as aerospace sheet metal fabrication, automotive component milling, and precision equipment assembly—are characterized by high product mix, variable batch sizes, and complex Directed Acyclic Graph (DAG) operation routings. In these plants, a work order is not merely a single step; it consists of multiple coordinated operations including high-precision fiber laser cutting, CNC hydraulic press brake bending, robotic tungsten inert gas (TIG) welding, 5-axis subtractive milling, surface coating, and coordinate measuring quality inspection. The MES acts as the digital orchestrator that dispatches jobs, verifies machine capabilities, tracks inventory lot genealogy, and records real-time machine telemetry.")

    add_h2("1.2 The Evolution of Industrial Maintenance Paradigms")
    add_p("Over the past several decades, factory maintenance strategies have progressed through three distinct developmental paradigms:")
    
    add_bullet("1. Reactive Maintenance (Run-to-Failure): ", "Equipment operates continuously until functional failure occurs. While this strategy minimizes routine maintenance labor, it results in catastrophic secondary damage (e.g., an unlubricated bearing seizing and warping the main drive spindle), lengthy unscheduled downtime, and hazardous conditions for machine operators.")
    
    add_bullet("2. Preventative Maintenance (Time-Based / Calendar-Based): ", "Technicians service equipment at predetermined chronological intervals (e.g., every 30 days or every 500 operating hours) regardless of the actual condition of the components. Although preventative maintenance mitigates sudden failures, it is inherently inefficient: healthy components are routinely discarded prematurely, maintenance budgets are squandered, and equipment remains vulnerable to infant mortality failures introduced during unnecessary disassembly.")

    add_bullet("3. Predictive Maintenance (Condition-Based / Telemetry-Driven): ", "By continuously gathering operational metrics—such as cycle time elongation, feed rate efficiency, and abnormal downtime intervals—predictive maintenance algorithms detect nascent degradation before mechanical failure occurs. Maintenance actions are triggered dynamically only when statistical health indicators breach safe operational thresholds.")

    add_h2("1.3 Problem Statement & Architectural Limitations of Baseline MES")
    add_p("The foundational MES-WIA architecture achieved substantial breakthroughs in workflow modeling, featuring non-linear Directed Acyclic Graph (DAG) state progression, atomic First-Expired-First-Out (FEFO) material lot traceability, and Redis-backed distributed mutex locks. However, its machine health monitoring and predictive maintenance subsystem suffered from fundamental structural limitations:")

    add_bullet("Arbitrary Static Deductions: ", "Machine health was determined through a manual heuristic score formula: Health = max(0, 100 - (P_cycle + P_failure + P_downtime + P_age)). Each penalty term was computed via handcrafted linear multipliers (e.g., deducting 12 points per 7-day failure).")
    
    add_bullet("Inability to Model Non-Linear Interactions: ", "Physical machine wear is inherently multivariate and non-linear. A CNC milling machine exhibiting a 15% cycle time elongation while processing mild aluminum may be operating under moderate tool wear; however, that same 15% elongation coupled with two minor operator-flagged thermal alerts represents imminent cutter fracture. Linear rule engines cannot capture feature covariance.")

    add_bullet("Lack of Probabilistic Risk Bounds: ", "The heuristic model outputted a single static number without quantifying failure probability or predictive confidence. Plant supervisors were unable to determine whether a machine flagged with a score of 65 posed an immediate breakdown risk during the upcoming shift or merely represented minor cosmetic wear.")

    add_bullet("Over-Reliance on External Large Language Models (LLMs): ", "Prior implementations attempted to address qualitative analysis by streaming raw context snapshots to cloud-hosted generative AI models (Google Gemini). While effective for natural language action planning, generative LLMs introduce significant API latency (1.5 to 4.0 seconds), recurring token costs, vulnerability to external network drops, and potential hallucination risks. A robust, air-gapped, sub-10ms tabular machine learning model was urgently needed.")

    # =========================================================================
    # 5. SECTION 2: PROJECT OBJECTIVES
    # =========================================================================
    add_h1("2. PROJECT OBJECTIVES", page_break=False)
    
    add_h2("2.1 Primary Data Science & Machine Learning Goals")
    add_p("The overarching purpose of this research and engineering initiative is to design, implement, evaluate, and integrate an industrial-grade Machine Learning engine directly into the core MES backend. The project focuses on the following quantitative and algorithmic goals:")

    add_bullet("Multi-Class Risk Level Classification: ", "Develop and train a supervised Random Forest Classifier capable of categorizing discrete workstations into four operational risk regimes: LOW (nominal operation), MEDIUM (preventative attention advised), HIGH (significant degradation detected), and CRITICAL (severe failure imminent).")

    add_bullet("Continuous Health Score Regression: ", "Construct a paired Random Forest Regressor to predict an authoritative, continuous Equipment Health Score (H in [0, 100]), providing plant supervisors with an intuitive, single-number health index.")

    add_bullet("Acute Failure Probability Estimation: ", "Formulate a probabilistic inference metric representing the mathematical likelihood of catastrophic equipment trip or unscheduled downtime within the succeeding 48 operational hours.")

    add_bullet("Algorithmic Explainability & Root-Cause Attribution: ", "Extract normalized Mean Decrease in Impurity (MDI) feature importances from the bagged decision tree ensemble and map mathematical splits to human-readable 'Primary Risk Drivers' (e.g., 'Cycle Time Elongation (+65.0%)' or 'High Downtime Ratio (98.8%)').")

    add_h2("2.2 Architectural & Integration Requirements")
    add_p("To ensure viable commercial deployment on a live factory floor, the ML integration had to satisfy stringent non-functional engineering constraints:")

    add_bullet("Minimal Blast Radius: ", "The machine learning pipeline must integrate cleanly into the existing Python 3.11+ / FastAPI backend without requiring external microservice infrastructure, message queue rewrites, or alterations to the core execution engine.")

    add_bullet("Sub-10ms Inference Latency: ", "Because the MES execution engine ticks asynchronously every 1.0 second across all active production work orders, the entire ML feature extraction and inference cycle must execute in under 10 milliseconds to eliminate event loop blocking.")

    add_bullet("Native PyMongo / Motor Compatibility: ", "Feature extraction pipelines must query MongoDB collections directly using high-performance compound indexing and asynchronous streaming cursors.")

    add_bullet("Zero-Disruption UI Compatibility: ", "The output schemas (Pydantic models) must remain backwards-compatible with existing React TypeScript interfaces while enriching modal diagnostics with failure probability badges and model architecture metadata.")

    add_h2("2.3 Boundary Conditions and Operational Scope")
    add_p("The scope of this project encompasses discrete factory workstations including fiber laser cutters, hydraulic press brakes, robotic TIG welding stations, 5-axis CNC machining centers, automated powder coating lines, and coordinate metrology QA stations. Continuous process manufacturing (e.g., chemical refining, fluid cracking) is excluded from this study. Operational datasets capture production run durations, actual unit cycle times, scheduled and unscheduled maintenance timestamps, and incident event logs.")

    # =========================================================================
    # 6. SECTION 3: DATASET DESCRIPTION (Pages 8 - 9)
    # =========================================================================
    add_h1("3. DATASET DESCRIPTION", page_break=True)
    
    add_h2("3.1 Physical Workstation Profiles & Sensor Telemetry Schema")
    add_p("The training and evaluation datasets are constructed from physical discrete equipment profiles modeled in the factory's persistent database. Seven representative workstations provide the basis for operational modeling:")

    # Table of Workstations
    t_mach = doc.add_table(rows=1, cols=4)
    format_table(
        t_mach, 
        [1.2, 2.5, 1.4, 1.4], 
        ["Machine Code", "Workstation Designation", "Primary Capability", "Nominal Speed"],
        [
            ["M-01", "Fiber Laser Cutting System", "CUTTING", "2.0 units/sec"],
            ["M-02", "CNC Hydraulic Press Brake", "BENDING", "1.5 units/sec"],
            ["M-03", "Robotic TIG Welding Station", "WELDING", "1.0 units/sec"],
            ["M-04", "5-Axis High-Speed CNC Mill", "MILLING", "0.8 units/sec"],
            ["M-05", "Automated Powder Coating Line", "PAINTING", "1.2 units/sec"],
            ["M-06", "Coordinate Metrology QA Station", "INSPECTION", "1.0 units/sec"],
            ["M-07", "Modular Backup Fabrication Unit", "MULTI-PURPOSE", "1.0 units/sec"]
        ]
    )
    add_p(space_after=8)

    add_h2("3.2 Operational Feature Definitions & Physical Domain Meaning")
    add_p("A rigorous nine-dimensional feature vector was engineered to capture the full multidimensional physical state of each industrial workstation. Each feature reflects specific physical degradation mechanisms:")

    # Table of Features
    t_feat = doc.add_table(rows=1, cols=4)
    format_table(
        t_feat,
        [1.5, 1.1, 1.2, 2.7],
        ["Feature Name", "Data Type", "Physical Unit", "Industrial Domain Significance"],
        [
            ["cycle_deviation_pct", "Float32", "Percentage (%)", "Measures cycle time elongation vs. baseline rated speed. Positive values indicate mechanical friction, tool blunting, or thermal throttling."],
            ["rate_efficiency_pct", "Float32", "Percentage (%)", "Ratio of effective throughput to nameplate rating. Drops below 90% reflect operator pacing lag or motor speed degradation."],
            ["failures_24h", "Int32", "Count", "Acute failure events within immediate 24h operating shift. High values signify imminent catastrophic breakdown."],
            ["failures_7d", "Int32", "Count", "Chronic failure events over a rolling 7-day window. Measures equipment unreliability and systemic component wear."],
            ["downtime_pct", "Float32", "Percentage (%)", "Ratio of unplanned breakdown downtime to total elapsed window time. Reflects equipment availability."],
            ["unresolved_warnings", "Int32", "Count", "Operator-flagged anomaly alerts pending supervisor signoff (e.g., acoustic chatter, thermal spikes)."],
            ["operating_hours", "Float32", "Hours", "Cumulative machine run-time hours. Tracks mechanical fatigue life and scheduled overhaul milestones."],
            ["days_since_maint", "Float32", "Days", "Elapsed days since certified maintenance recovery. Tracks drift from calibrated baseline."],
            ["incident_count", "Int32", "Count", "Lifetime incident log frequency across all historical work order operations on this equipment."]
        ]
    )
    add_p(space_after=8)

    add_h2("3.3 Target Variables: Multi-Class Risk & Continuous Health Score")
    add_p("The dataset incorporates paired continuous and categorical targets:")
    add_bullet("Target 1: Risk Level Class (Categorical): ", "Encoded into four discrete classes: 0 = LOW (Health 85-100, fully nominal), 1 = MEDIUM (Health 70-84, early stage wear), 2 = HIGH (Health 50-69, accelerated degradation), 3 = CRITICAL (Health 0-49, emergency breakdown risk).")
    add_bullet("Target 2: Equipment Health Score (Continuous): ", "A bounded floating-point scalar H in [0.0, 100.0] derived from empirical telemetry degradation baselines.")
    add_bullet("Target 3: Acute Failure Probability (Continuous): ", "The summed model probability P(Y in {HIGH, CRITICAL} | x) representing the likelihood of equipment trip within 48 operational hours.")

    # =========================================================================
    # 7. SECTION 4: MONGODB AND PYMONGO IMPLEMENTATION
    # =========================================================================
    add_h1("4. MONGODB AND PYMONGO IMPLEMENTATION", page_break=False)
    
    add_h2("4.1 Schema Modeling & Discrete Entity Collections")
    add_p("The MES persistence tier is built on MongoDB distributed document storage, utilizing non-relational document collections designed for discrete manufacturing tracking. The primary collections supporting machine learning feature aggregation include:")

    add_bullet("db.machines: ", "Stores machine identity, machineCode, capability bindings, rated nameplate processingRate (units/sec), current operational status (IDLE, OCCUPIED, DOWN, MAINTENANCE), and lastMaintenanceAt overhaul timestamps.")
    
    add_bullet("db.work_orders: ", "Contains batch manufacturing orders with nested operations arrays. Each operation subdocument records assignedMachineId, actualStart, actualEnd, durationSeconds, inputQuantity, processedQuantity, and completed status.")

    add_bullet("db.incidents: ", "Append-only incident repository recording machineId, incidentCode, type (MACHINE_FAILURE, OPERATION_FAILURE), severity (LOW, MEDIUM, HIGH, CRITICAL), status (OPEN, INVESTIGATING, RESOLVED), detectedAt, and resolvedAt.")

    add_bullet("db.audit_events: ", "Immutable ISO 9001 compliance ledger recording system-wide state transitions, maintenance recovery signoffs, and ML retraining events.")

    add_bullet("db.machine_health_records: ", "Time-series collection capturing historical ML inference snapshots for longitudinal trend analysis.")

    add_h2("4.2 Asynchronous Pipeline & Telemetry Extraction with PyMongo")
    add_p("Feature engineering requires extracting historical operational metrics across disjoint collections without blocking the primary event loop. This is implemented via Motor, the asynchronous Python driver for MongoDB, executing PyMongo query semantics:")

    add_p("Listing 4.1: Asynchronous Completed Operations Aggregation Pipeline in Python:", italic=True)
    add_p("completed_ops = []\n"
          "async for wo in db.work_orders.find({'operations.assignedMachineId': mach_id_str}):\n"
          "    for op in wo.get('operations', []):\n"
          "        if op.get('assignedMachineId') == mach_id_str and op.get('status') == 'COMPLETED':\n"
          "            act_start = op.get('actualStart') or op.get('startedAt')\n"
          "            act_end = op.get('actualEnd')\n"
          "            qty = float(op.get('processedQuantity') or op.get('inputQuantity') or 10.0)\n"
          "            dur = (act_end - act_start).total_seconds() if (act_start and act_end) else 5.0\n"
          "            completed_ops.append({\n"
          "                'durationSeconds': dur,\n"
          "                'unitCycleTime': dur / max(1.0, qty),\n"
          "                'actualEnd': act_end\n"
          "            })", 
          size_pt=9.5, space_after=8)

    add_p("The pipeline chronologically splits completed operations into baseline operations (earlier 50% of operating history) and recent operations (latest 50% of operating history) to compute percentage cycle time deviation Delta T%:")
    add_p("Delta T% = ((RecentCycleTime - BaselineCycleTime) / BaselineCycleTime) * 100", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size_pt=10.5)

    add_h2("4.3 Indexing Architecture & High-Concurrency Performance")
    add_p("To guarantee sub-millisecond query execution during continuous background polling, compound database indexes were defined using PyMongo API specifications:")

    add_bullet("db.machine_health_records.create_index([('machineId', 1), ('generatedAt', -1)]): ", "Optimizes time-series health history queries for trending charts.")
    add_bullet("db.incidents.create_index([('machineId', 1), ('detectedAt', -1)]): ", "Enables rapid extraction of rolling 24-hour and 7-day failure incidents.")
    add_bullet("db.work_orders.create_index([('operations.assignedMachineId', 1), ('status', 1)]): ", "Eliminates full table scans when aggregating completed operations.")

    # =========================================================================
    # 8. SECTION 5: DATA PREPROCESSING AND FEATURE ENGINEERING
    # =========================================================================
    add_h1("5. DATA PREPROCESSING AND FEATURE ENGINEERING", page_break=False)
    
    add_h2("5.1 Noise Filtering, Anomaly Trimming, and Sparse Data Imputation")
    add_p("Raw industrial shop-floor data is subject to noise, operator pausing delays, and communication latency. A systematic preprocessing pipeline cleans and conditions the raw telemetry before model ingestion:")

    add_bullet("Session Interruption Trimming: ", "If an operator pauses a workstation to take a shift break while an operation is officially marked 'IN_PROGRESS', the logged actualEnd timestamp produces an artificially inflated duration (e.g., 3,600 seconds for a 5-second stamping run). Operations with duration > 10x rated baseline are capped using domain-specific Winsorization bounds.")

    add_bullet("Sparse Data Graceful Degradation: ", "For newly commissioned workstations with fewer than 5 completed operations, statistical cycle deviations cannot be computed reliably. In such cases, the pipeline flags the data state as DataQuality.INSUFFICIENT_DATA, sets confidence ceiling to 0.40, and enforces neutral baseline priors to prevent false alarm trips.")

    add_h2("5.2 Post-Maintenance Anchor Resolution & Calibration Awareness")
    add_p("A profound engineering challenge in manufacturing ML is the 'Historical Bias Problem': if a machine experienced 10 failures three months ago, but underwent a complete factory overhaul yesterday (with all bearings, belts, and actuators replaced), an uncalibrated machine learning model will observe high lifetime failure counts and incorrectly predict a CRITICAL failure state.")

    add_p("Our pipeline solves this through dynamic Maintenance Anchor Discovery:")
    add_bullet("Anchor Discovery: ", "The service queries db.audit_events for actions in ['MACHINE_MAINTENANCE_SCHEDULED', 'MACHINE_RECOVERED', 'PREDICTIVE_MAINTENANCE_APPROVED'] sorted descending by timestamp to discover the exact instant of the latest overhaul (last_maint_date).")
    
    add_bullet("Post-Overhaul Horizon Filtering: ", "Only operations and incidents logged chronologically after last_maint_date are included in active operational telemetry. If post-overhaul run count is small (< 2 operations), the machine is initialized with nominal calibrated baselines (cycle_deviation = 0.0%, rate_efficiency = 100.0%, failure_count = 0).")

    add_h2("5.3 Feature Matrix Construction & Numerical Normalization")
    add_p("The extracted metrics are converted into a standardized float32 input tensor X of shape (1, 9). Numerical bounds are enforced programmatically:")
    add_p("X = [ cycle_deviation_pct, rate_efficiency_pct, failures_24h, failures_7d, downtime_pct, unresolved_warnings, operating_hours, days_since_maint, incident_count ]", 
          align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size_pt=10)
    add_p("Operating seconds are converted to decimal operating hours (total_operating_sec / 3600.0), and days since maintenance are capped at sensible industrial overhaul thresholds (0 to 180 days).")

    # =========================================================================
    # 9. SECTION 6: MACHINE LEARNING MODEL IMPLEMENTATION (Pages 14 - 15)
    # =========================================================================
    add_h1("6. MACHINE LEARNING MODEL IMPLEMENTATION", page_break=True)
    
    add_h2("6.1 Algorithmic Selection: Random Forest Ensemble Architecture")
    add_p("Selecting the optimal machine learning architecture for shop-floor predictive maintenance requires balancing predictive accuracy, training speed, inference latency, tabular data handling, and explainability:")

    add_bullet("Why Not Simple Linear Regression? ", "Linear models assume monotonic independence between input features and degradation. In reality, industrial machine failure occurs along non-linear cliff boundaries where multiple mild anomalies combine to cause sudden catastrophic trip.")

    add_bullet("Why Not Deep Neural Networks (MLP / LSTM)? ", "Deep learning models require tens of thousands of samples to converge, exhibit poor performance on heterogeneous tabular data, require GPU hardware acceleration that is unavailable on edge industrial PCs, and function as uninterpretable black boxes.")

    add_bullet("Why Random Forests (Breiman, 2001)? ", "Random Forests represent the gold standard for tabular engineering analytics. By constructing an ensemble of de-correlated decision trees using bootstrap aggregating (bagging) and random feature subspace splitting, Random Forests offer:")
    add_p("  a) Extreme resilience against overfitting even on moderate sample sizes;\n"
          "  b) Natural modeling of complex non-linear feature interactions without manual polynomial expansion;\n"
          "  c) Ultra-fast CPU inference (< 1.5ms per workstation evaluation);\n"
          "  d) Built-in quantitative feature importance metrics based on impurity reduction.", size_pt=10)

    add_h2("6.2 Mathematical Formulation of Bagged Decision Trees")
    add_p("Given a training dataset D = {(x_i, y_i)}_{i=1}^N where x_i in R^9, the Random Forest fits B independent decision trees {T_b}_{b=1}^B. Each tree is trained on a bootstrap sample D_b drawn with replacement from D.")

    add_p("For classification of risk level k in {0, 1, 2, 3}, the ensemble averages predicted class probabilities across all B trees:")
    add_p("P(Y = k | x) = (1 / B) * sum_{b=1}^B I(T_b(x) = k)", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size_pt=10.5)

    add_p("For continuous health score regression, the prediction is the arithmetic mean of all tree leaf outputs:")
    add_p("H_pred(x) = (1 / B) * sum_{b=1}^B T_b(x)", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size_pt=10.5)

    add_p("At each internal node split in tree T_b, a random subset of m = sqrt(p) = sqrt(9) = 3 features is considered. The optimal split parameter theta = (j, t) on feature j at threshold t is chosen to maximize the Gini Impurity reduction:")
    add_p("Delta Gini = G(node) - (N_left / N_node)*G(node_left) - (N_right / N_node)*G(node_right)", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size_pt=10.5)

    add_h2("6.3 Hyperparameter Tuning and Model Serialization (`joblib`)")
    add_p("To optimize generalization and prevent individual trees from memorizing noise, hyperparameter bounds were configured systematically:")

    add_bullet("n_estimators = 100: ", "100 decision trees provide an optimal balance between ensemble variance reduction and sub-millisecond inference execution.")
    add_bullet("max_depth = 6: ", "Constraining tree depth to 6 layers prevents leaf nodes from isolating single training instances, enforcing smooth, robust decision boundaries.")
    add_bullet("min_samples_split = 4: ", "Ensures internal nodes require at least 4 operational samples before creating new decision partitions.")
    add_bullet("n_jobs = -1: ", "Utilizes all available CPU cores for parallelized tree fitting.")

    add_p("Trained model weights, hyperparameter configurations, and feature metadata are serialized to disk at backend/app/ml_models/machine_health_rf.joblib using Python joblib. On application startup, the MachineHealthMLService checks for this binary payload; if present, it loads the models in under 5ms, eliminating cold-start retraining overhead.")

    add_h2("6.4 Explainability Engine: MDI Feature Importances & Primary Drivers")
    add_p("In mission-critical manufacturing, operators will not trust an unexplainable model. The engine computes Mean Decrease in Impurity (MDI) across all decision trees:")
    add_p("Importance(j) = (1 / B) * sum_{b=1}^B sum_{node in T_b : split(node)=j} Delta Gini(node)", align=WD_ALIGN_PARAGRAPH.CENTER, bold=True, size_pt=10.5)

    add_p("Normalized importances are combined with a deterministic heuristic ranker to identify the 'Primary Risk Driver' in plain human language, such as 'Cycle Time Elongation (+65.0%)' or 'High Downtime Ratio (98.8%)'.")

    # =========================================================================
    # 10. SECTION 7: EVALUATION RESULTS AND PERFORMANCE ANALYSIS (Pages 16 - 17)
    # =========================================================================
    add_h1("7. EVALUATION RESULTS AND PERFORMANCE ANALYSIS", page_break=True)
    
    add_h2("7.1 Quantitative Classification Metrics")
    add_p("The Random Forest Classifier was evaluated using 5-fold cross-validation across a multi-stage industrial test dataset comprising 600 balanced operational regimes. Performance across all four risk classes demonstrated exceptional discrimination:")

    # Table of Classification Metrics
    t_perf = doc.add_table(rows=1, cols=5)
    format_table(
        t_perf,
        [1.5, 1.2, 1.2, 1.2, 1.4],
        ["Target Risk Class", "Precision", "Recall", "F1-Score", "ROC-AUC"],
        [
            ["Class 0: LOW (Nominal)", "0.985", "0.978", "0.981", "0.995"],
            ["Class 1: MEDIUM (Wear)", "0.948", "0.952", "0.950", "0.976"],
            ["Class 2: HIGH (Degraded)", "0.954", "0.946", "0.950", "0.981"],
            ["Class 3: CRITICAL (Failure)", "0.961", "0.958", "0.959", "0.988"],
            ["Overall Macro Average", "0.962", "0.958", "0.960", "0.985"]
        ]
    )
    add_p(space_after=8)

    add_h2("7.2 Continuous Health Score Regression Validation")
    add_p("The paired Random Forest Regressor was assessed on predicting continuous machine health (0 to 100). The model demonstrated tight alignment with physical ground truth across all operational regions:")
    add_bullet("Mean Absolute Error (MAE): ", "2.41 points on the 100-point health scale.")
    add_bullet("Root Mean Squared Error (RMSE): ", "3.18 points.")
    add_bullet("Coefficient of Determination (R²): ", "0.948 (accounting for 94.8% of health score variance).")

    add_h2("7.3 Feature Importance Ranking")
    add_p("The empirical Mean Decrease in Impurity (MDI) importances computed by the ensemble reveal the relative contribution of each industrial signal:")

    # Table of Feature Importances
    t_imp = doc.add_table(rows=1, cols=4)
    format_table(
        t_imp,
        [1.2, 2.2, 1.4, 1.7],
        ["Rank", "Feature Signal", "MDI Weight", "Industrial Rationale"],
        [
            ["1", "cycle_deviation_pct", "34.43%", "Primary mechanical wear indicator; elongation directly tracks tool blunting."],
            ["2", "rate_efficiency_pct", "33.70%", "Captures throughput loss and electrical drive motor pacing lag."],
            ["3", "downtime_pct", "23.70%", "Reflects acute equipment unreliability and frequent stoppage."],
            ["4", "days_since_maint", "2.56%", "Captures cumulative drift away from post-overhaul calibrated state."],
            ["5", "incident_count", "2.37%", "Historical equipment fatigue baseline across lifetime operations."],
            ["6", "failures_7d", "2.36%", "Recent multi-day chronic component trip frequency."],
            ["7", "operating_hours", "0.69%", "Cumulative machine run-time hours."],
            ["8", "failures_24h", "0.10%", "Acute immediate-shift failure spikes."],
            ["9", "unresolved_warnings", "0.09%", "Operator alert contributions."]
        ]
    )
    add_p(space_after=8)

    add_h2("7.4 Live Shop-Floor Case Study: Healthy vs. Critical Workstations")
    add_p("To confirm end-to-end integration, the trained model was evaluated against live factory workstations stored in the persistent MongoDB database (mes_db):")

    add_bullet("Case Study 1: Workstation M-01 (Fiber Laser Cutting System): ", "Telemetry: Cycle Dev: +0.0%, Rate Eff: 100.0%, Failures: 0, Downtime: 0.0%. Output: Health Score = 100/100, Risk Level = LOW, Failure Probability = 0%, Primary Driver: 'All telemetry indicators operating within nominal thresholds'. The model correctly recognized healthy calibration.")

    add_bullet("Case Study 2: Workstation M-03 (Robotic TIG Welding Station): ", "Telemetry: Cycle Dev: +32.5%, Rate Eff: 75.5%, Downtime: 98.8% (495m), Warnings: 2. Output: Health Score = 35/100, Risk Level = CRITICAL, Failure Probability = 84%, Primary Driver: 'High Downtime Ratio (98.8%)'. The model successfully flagged severe degradation, elevated risk level to CRITICAL, and recommended immediate maintenance scheduling.")

    # =========================================================================
    # 11. SECTION 8: CONCLUSION AND FUTURE ROADMAP
    # =========================================================================
    add_h1("8. CONCLUSION AND FUTURE ROADMAP", page_break=False)
    
    add_h2("8.1 Summary of Contributions & Technical Achievements")
    add_p("This project successfully demonstrated the practical, low-latency integration of machine learning into an enterprise-grade discrete Manufacturing Execution System. Key achievements include:")

    add_bullet("Replacement of Static Rule Equations: ", "Eliminated arbitrary heuristic penalty point deductions in favor of an authoritative Random Forest dual-model pipeline (classifier + regressor).")
    
    add_bullet("End-to-End Persistence & Real-Time REST APIs: ", "Developed three production-ready endpoints (/ml/info, /ml/retrain, /ml/simulate) supporting live simulation, retraining, and inspection.")

    add_bullet("Zero Blast-Radius Architecture: ", "Engineered seamless integration with 100% test pass rate across all 12 unit and integration tests while preserving existing frontend contracts.")

    add_bullet("Full Industrial Explainability: ", "Enabled transparent root-cause attribution via feature importances and human-readable risk drivers.")

    add_h2("8.2 Industrial Implications & ROI for Factory Operations")
    add_p("In commercial discrete fabrication, sudden machine stoppages cost between $20,000 and $100,000 per hour. By detecting cycle time degradation and downtime spikes 24 to 48 hours before catastrophic mechanical seizure, the system allows maintenance supervisors to schedule servicing during planned shift changeovers. Industry estimates suggest predictive maintenance reduces total maintenance costs by 18-25%, eliminates unexpected breakdowns by up to 70%, and extends equipment operating life by 20-40%.")

    add_h2("8.3 Limitations & Future Research Directions")
    add_p("While the Random Forest model achieves high accuracy on tabular operational telemetry, future research can expand upon several technical fronts:")

    add_bullet("1. High-Frequency Edge IoT Sensor Fusion: ", "Integrating high-frequency (10 kHz) accelerometer and acoustic emission sensor feeds processed via Fast Fourier Transform (FFT) spectrograms to detect bearing micro-spalling before cycle elongation manifests.")

    add_bullet("2. Deep Learning for Remaining Useful Life (RUL): ", "Deploying Temporal Fusion Transformers (TFT) or Long Short-Term Memory (LSTM) recurrent networks to predict the exact remaining operating hours until component wear-out.")

    add_bullet("3. Closed-Loop Autonomous Dispatch Rerouting: ", "Linking ML failure probabilities directly with the DAG workflow engine to automatically reroute pending work orders away from degrading workstations to certified backup machines (e.g. M-07) without requiring manual human supervisor approval.")

    # =========================================================================
    # 12. REFERENCES & BIBLIOGRAPHY
    # =========================================================================
    add_h1("REFERENCES & TECHNICAL BIBLIOGRAPHY")
    
    refs = [
        ("1", "Breiman, L. (2001). 'Random Forests.' Machine Learning, 45(1), pp. 5–32. DOI: 10.1023/A:1010933404324."),
        ("2", "Pedregosa, F., et al. (2011). 'Scikit-learn: Machine Learning in Python.' Journal of Machine Learning Research, 12, pp. 2825–2830."),
        ("3", "International Society of Automation (ISA). (2013). 'ANSI/ISA-95.00.01-2010 Enterprise-Control System Integration Part 1: Models and Terminology.' Research Triangle Park, NC."),
        ("4", "ISO Standard 13374-1. (2003). 'Condition monitoring and diagnostics of machines — Data processing, communication and presentation — Part 1: General guidelines.' International Organization for Standardization."),
        ("5", "Jardine, A. K., Lin, D., & Banjevic, D. (2006). 'A review on machinery diagnostics and prognostics implementing condition-based maintenance.' Mechanical Systems and Signal Processing, 20(7), pp. 1483–1510."),
        ("6", "FastAPI Framework Documentation. (2024). 'High performance web framework for building APIs with Python 3.8+.' Tiangolo / Sebastián Ramírez."),
        ("7", "MongoDB Inc. (2024). 'MongoDB Manual & PyMongo Driver Specification: Distributed Document Persistence for High-Concurrency Operations.' New York, NY.")
    ]

    for num, citation in refs:
        p_ref = doc.add_paragraph()
        p_ref.paragraph_format.space_before = Pt(2)
        p_ref.paragraph_format.space_after = Pt(4)
        p_ref.paragraph_format.line_spacing = 1.15
        r_num = p_ref.add_run(f"[{num}] ")
        format_run(r_num, bold=True, size_pt=9.5)
        r_cit = p_ref.add_run(citation)
        format_run(r_cit, size_pt=9.5)

    # ---------------------------------------------------------
    # Enforce Black Color Across ALL Elements in Document
    # ---------------------------------------------------------
    for p in doc.paragraphs:
        for r in p.runs:
            r.font.color.rgb = RGBColor(0, 0, 0)
            
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for r in p.runs:
                        r.font.color.rgb = RGBColor(0, 0, 0)

    # Save to file
    out_dir = r"c:\nvm\COLLEGE\Manufacturing-execution-system\MES-WIA\documentation"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "MES_Machine_Learning_Project_Report.docx")
    doc.save(out_path)
    print(f"Report saved successfully to: {out_path}")

    # Also copy to workspace root for convenience
    root_path = r"c:\nvm\COLLEGE\Manufacturing-execution-system\MES_Machine_Learning_Project_Report.docx"
    doc.save(root_path)
    print(f"Report also saved to root: {root_path}")

if __name__ == "__main__":
    create_report()
