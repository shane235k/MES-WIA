# Adaptive Manufacturing Execution System (MES)
## Complete Product Capabilities, Functionality Catalog & Operator Guide
### Document ID: `10_PRODUCT_FUNCTIONALITY_AND_FEATURE_CATALOG`

---

# 1. Executive Product Overview

**Adaptive MES** is an enterprise-grade, end-to-end discrete manufacturing software platform designed to manage, monitor, coordinate, and synchronize all operations on the factory floor in real time.

It bridges the gap between **high-level enterprise planning** and **physical shop-floor execution**, providing complete digital visibility across raw material lots, visual workflow scheduling, workstation health, certified operator pairing, quality compliance, and AI-assisted breakdown triage.

```
+───────────────────────────────────────────────────────────────────────────────────────────────────+
|                                    THE ADAPTIVE MES PRODUCT SUITE                                 |
+───────────────────────────────────────────────────────────────────────────────────────────────────+
|                                                                                                   |
|   1. ADMIN WEB DASHBOARD (Plant Control Tower)                                                    |
|      A centralized web application for plant supervisors, manufacturing engineers, and operations |
|      managers to schedule batches, monitor digital twin telemetry, and oversee compliance.        |
|                                                                                                   |
|   2. OPERATOR CLIENT (Desktop Workstation Terminal)                                               |
|      A ruggedized, distraction-free desktop interface mounted at each factory workstation for      |
|      certified machine operators to run batches, monitor timers, and dispatch emergency alerts.    |
|                                                                                                   |
|   3. REAL-TIME EVENT & MUTEX BUS                                                                  |
|      High-speed bi-directional synchronization layer keeping all screens in sync with zero lag.   |
|                                                                                                   |
+───────────────────────────────────────────────────────────────────────────────────────────────────+
```

---

# 2. Admin Web Dashboard: Complete Feature Matrix

The Admin Web Dashboard acts as the central nerve center of the manufacturing facility, organized into **nine dedicated operational modules**:

---

## 2.1 Executive Dashboard & Plant Digital Twin
* **Live Factory KPI Gauges**: Real-time visualization of plant-wide **Overall Equipment Effectiveness (OEE)**, combining Availability, Performance, and Quality into a single unified health metric.
* **Shop-Floor Digital Twin Grid**: Visual status cards for every factory machine (`IDLE`, `OCCUPIED`, `DOWN`, `MAINTENANCE`) showing active work orders, processing speeds, and operator assignments.
* **Operational Counters**: Live counters for total units manufactured, active work orders in progress, scrap percentages, and unaddressed incident alerts.
* **Emergency Simulation Controls**: One-click machine failure simulation tools allowing plant managers to test disaster recovery and AI failover paths in real time.

---

## 2.2 Visual DAG Workflow Designer
* **Interactive ReactFlow Canvas**: Drag-and-drop graphical canvas allowing process engineers to build, inspect, and modify multi-step manufacturing routes.
* **Parallel Branching (Fork & Join)**: Full support for non-linear workflows (e.g. cutting two metal components on separate machines in parallel, bending each, and merging them at a welding station).
* **Live In-Place State Animation**: As batches run on the factory floor, the canvas nodes animate in real-time:
  * Running nodes pulse with live countdown timers (`42s remaining`) and SVG circular progress bars.
  * Blocked nodes turn Red with explicit reason banners (`[BLOCKED: MACHINE DOWN]`).
  * Material shortages display Amber warning banners (`[WAITING FOR MATERIAL: SS304]`).
  * Completed nodes turn Green with checkmark badges.
* **Manual Shop-Floor Overrides**: Interactive node-level controls allowing supervisors to **Pause an individual step**, **Resume a paused step**, or **Reroute an operation** to a backup machine directly from the graph.
* **Automatic Mathematical Validation**: Automatically checks that the workflow contains no circular dependency deadlocks before saving.

---

## 2.3 Work Order Management & Conversational AI Planner
* **Batch Lifecycle Management**: Full control to create, schedule, start, pause, resume, cancel, and archive production work orders.
* **Step-by-Step Progress Tracking**: Interactive pills showing operation sequence progress, input/output quantities, and remaining duration.
* **Live Bill of Materials (BOM) & Costing Modal**:
  * Inspects all allocated raw material lots with heat numbers and storage bin locations.
  * Calculates the **exact material acquisition cost** of the batch based on the specific warehouse lots locked for production.
* **Conversational AI Work Order Planner**:
  * An interactive AI chat assistant where supervisors can schedule production using natural language (e.g., *"Schedule a rush batch of 50 Solar Brackets for Friday with high priority"*).
  * The AI automatically extracts product IDs, workflow routes, quantities, and due dates, prompts for missing fields, and generates a ready-to-run work order draft.

---

## 2.4 Raw Material & Inventory Lot Traceability (Phase 6)
* **Master Material Catalog**: Catalog management for raw metals, fasteners, chemical coatings, and electronic components.
* **Granular Inventory Lot Management**: Tracks individual physical warehouse batches with:
  * Unique Lot Numbers and Supplier Batch Codes.
  * Metallurgical Heat Numbers and Quality Certificates.
  * Storage Bay / Aisle / Bin Locations.
  * Expiration Dates for perishable goods and Unit Acquisition Costs.
* **3-Tier Stock Transparency**: Every material card displays physical **Quantity On-Hand**, locked **Quantity Reserved**, and net uncommitted **Quantity Available**.
* **Stock Receipts & Adjustments**: Warehouse managers can receive new vendor shipments or log physical cycle count adjustments.
* **Full Supply Chain Genealogy**:
  * **Backward Traceability**: Trace from a finished product serial number back through the work order to the exact supplier raw material heat lot.
  * **Forward Traceability (Recall Containment)**: Trace from a contaminated raw material lot forward to instantly identify every downstream work order, product batch, and customer shipment.

---

## 2.5 Workstation & Equipment Dispatch
* **Equipment Registry**: Configuration of machine business codes, machine types, location bays, availability toggles, and calibrated throughput rates (units/second).
* **Standardized Capability Catalog**: Defines process qualifications (`CUTTING`, `BENDING`, `WELDING`, `MILLING`, `PAINTING`, `INSPECTION`) that machines can perform.
* **Multi-Purpose Machine Support**: Configures advanced equipment (e.g. 5-Axis CNC machining centers) capable of executing multiple distinct manufacturing processes.
* **Automated Maintenance Scheduling**: Set repair downtime duration; the system locks the machine in `MAINTENANCE` and **automatically returns it to `IDLE`** when the repair window elapses.

---

## 2.6 Predictive Maintenance & Machine Health Analytics (Phase 8)
* **Continuous Health Scoring ($0 - 100$)**: Evaluates machine sensor telemetry against baseline rates to calculate a live health score.
* **Risk Classification Badges**: Color-coded risk indicators (`LOW`, `MEDIUM`, `HIGH`) warning of impending mechanical failure.
* **Telemetry Performance Analytics**: Inspects cycle time elongation percentages ($\Delta T\%$), actual vs baseline throughput efficiency, MTBF (Mean Time Between Failures), and MTTR (Mean Time to Repair).
* **AI Predictive Maintenance Reasoner**:
  * Click `[Generate AI Predictive Plan]` to have Google Gemini diagnose mechanical wear patterns (e.g. hydraulic valve seal degradation, laser optic fouling).
  * Provides root cause hypotheses, urgency levels, and recommended maintenance checklists with a one-click `[Schedule Maintenance]` button.

---

## 2.7 Incident Management & AI Root Cause Analysis (RCA)
* **Centralized Incident Triage Feed**: Real-time list of all shop-floor breakdowns, emergency stops, and operator problem alerts.
* **Severity Scoring**: Classified by urgency (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).
* **Automated Machine Quarantine**: Machine failures automatically transition the equipment to `DOWN` and pause affected production batches.
* **AI Root Cause Analysis (RCA) Modal**:
  * Streams real-time Google Gemini reasoning diagnosing the root cause.
  * Features a **Local Ollama Safety Verification Badge** verifying that proposed recovery actions comply with plant safety constraints.
  * Displays proposed recovery steps (`pause_operation`, `reroute_operation`, `schedule_maintenance`) with an interactive **`[Approve & Execute Plan]`** button.

---

## 2.8 Operator & Terminal Access Management
* **Certified Operator Registry**: Profile management for certified machine operators, employee IDs, skill levels, and department assignments.
* **One-Time QR / Activation Code Generator**: Supervisors generate time-stamped pairing codes (e.g. `ACT-OP001-X9K2L1`) to authorize shop-floor desktop terminals.
* **Terminal Approval Controls**: Displays incoming pairing requests with `[Approve]` and `[Reject]` buttons.
* **Session Revocation**: One-click termination of active terminal sessions.

---

## 2.9 Process Audit & Compliance Trail
* **Immutable Chronological Log**: Tamper-proof record of every shop-floor event, machine transition, user action, and AI proposal.
* **Multi-Faceted Filtering**: Filter audit records by Process Executions, Work Orders, Workstations, Users, or Products.
* **Full-Text Search & JSON Inspector**: Search across actions, actor IDs, or entity IDs with interactive expandable JSON metadata inspectors.

---

# 3. Operator Desktop Client: Workstation Terminal Guide

The **Operator Client** is a purpose-built desktop application designed for rugged shop-floor touchscreens. It strips away complex navigation, giving operators a focused, distraction-free environment to execute production orders safely.

```
+───────────────────────────────────────────────────────────────────────────────────────────────────+
|                                  OPERATOR CLIENT SCREEN FLOW                                      |
+───────────────────────────────────────────────────────────────────────────────────────────────────+
|                                                                                                   |
|  [ 1. ZERO-TRUST LOCK SCREEN ]  ──► [ 2. PENDING APPROVAL ]  ──► [ 3. ACTIVE DASHBOARD ]          |
|  • Station Locked               • Awaiting Supervisor Approval • Live Cycle Countdown (42s)       |
|  • Enter Activation Code        • Shows Employee & Station ID  • Work Order Code & Part Name      |
|                                                                • [Step Complete] & [Report Alert] |
|                                                                                                   |
+───────────────────────────────────────────────────────────────────────────────────────────────────+
```

---

## 3.1 Terminal Pairing & Station Security
1. **Zero-Trust Station Lock**: When the application launches on an unpaired terminal, it displays the **Activation Screen**.
2. **Code Entry**: The operator enters the one-time activation code provided by their supervisor (e.g. `ACT-OP001-9X8K2L`).
3. **Pending Approval Screen**: The terminal connects to the server and displays a waiting screen.
4. **Instant Unlock**: As soon as the supervisor clicks `[Approve]` in the Admin Web, the terminal receives a WebSocket event and **instantly unlocks without refreshing**.
5. **Persistent Reboot Resilience**: The 32-byte session token is saved in persistent storage. If the terminal is powered down or restarted at shift end, reopening the application immediately restores the approved session without asking for a code again.

---

## 3.2 Active Work Order Execution View
* **Focused Production Screen**: Displays only the active operation assigned to that operator and workstation.
* **Synchronized Cycle Timer**: Shows a live countdown timer ticking down in seconds matching the physical machine processing rate.
* **Batch Details**: Clear display of the Work Order Code (e.g. `WO-1004`), Part Description, Step Sequence, and Input Quantity.
* **One-Click Step Confirmation**: Operator confirms completion, automatically advancing the batch in the central state machine and triggering inventory consumption.

---

## 3.3 Emergency Shop-Floor Problem Dispatch
If a machine jams, a laser optic fails, or material arrives damaged:
1. The operator clicks the prominent **`[Report Problem]`** button.
2. An emergency modal opens with the current workstation and work order pre-filled.
3. The operator types a short description of the issue and clicks `[Dispatch Alert]`.
4. **Instant Central Escalation**: The alert immediately creates an incident in the Admin Web, marks the machine `DOWN`, flags the DAG node Red, and notifies the plant supervisor.

---

## 3.4 My Reports History Drawer
Accessible via the top bar, operators can open a slide-out drawer showing the full history of all incident reports and problem dispatches submitted from their terminal, along with current resolution statuses.

---

# 4. Cross-Platform Connectivity & Synchronization

The Admin Web Dashboard and Operator Client work as a single synchronized organism:

```
+───────────────────────────────────────────────────────────────────────────────────────────────────+
|                              CROSS-PLATFORM INTERACTION SCENARIOS                                 |
+───────────────────────────────────────────────────────────────────────────────────────────────────+
|                                                                                                   |
|  SCENARIO A: BATCH START & STATION UNLOCK                                                         |
|  1. Supervisor starts WO-1004 in Admin Web.                                                       |
|  2. Execution Engine locks raw materials (FEFO) and assigns Machine M-01 & Operator OP-001.       |
|  3. WebSocket pushes WORK_ORDER_STARTED.                                                          |
|  4. Admin Web node turns Blue; Operator Terminal screen unlocks and begins countdown timer!       |
|                                                                                                   |
|  SCENARIO B: EMERGENCY BREAKDOWN & AI FAILOVER                                                    |
|  1. Operator reports machine jam on terminal screen.                                              |
|  2. Backend acquires Redis lock, sets Machine M-01 to DOWN, and pauses Operation 10.             |
|  3. Admin Web node turns Red with [BLOCKED: MACHINE DOWN] banner.                                 |
|  4. Supervisor clicks "Investigate with AI" -> Gemini + Ollama propose reroute to Machine M-04.  |
|  5. Supervisor clicks [Approve & Execute Plan].                                                   |
|  6. Transferred job instantly appears on Machine M-04's terminal screen to continue production!   |
|                                                                                                   |
+───────────────────────────────────────────────────────────────────────────────────────────────────+
```

---

# 5. Summary Table: What Adaptive MES Delivers to Plant Stakeholders

| Stakeholder Role | Primary Value & Capabilities Delivered |
| :--- | :--- |
| **Plant Managers & Executives** | Live OEE gauges, plant utilization metrics, real-time units manufactured counters, scrap rate monitoring, and automated regulatory compliance trails. |
| **Process & Manufacturing Engineers** | Visual DAG workflow designer, flexible parallel branching (fork/join), automated cycle detection, and dynamic equipment capability routing. |
| **Maintenance Supervisors** | Continuous predictive machine health scoring ($0-100$), MTBF/MTTR tracking, cycle time degradation alerts, and AI-assisted predictive maintenance planning. |
| **Warehouse & Supply Chain Managers** | Granular lot-level tracking (heat numbers, expiry dates, supplier batches), FEFO/FIFO inventory allocation, and complete forward/backward recall traceability. |
| **Shop-Floor Machine Operators** | Distraction-free touchscreen terminal, zero-password QR pairing, live operation countdown timers, and one-click emergency problem dispatching. |
