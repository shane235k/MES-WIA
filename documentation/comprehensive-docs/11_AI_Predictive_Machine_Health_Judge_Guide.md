# AI Predictive Machine Health — Comprehensive Judge Guide

## 1. Overview

The Adaptive MES uses a software-derived predictive maintenance system to estimate machine health from real manufacturing execution data.

It does not pretend to have IoT sensors. It derives machine-health signals from:
- Machine configuration and nominal processing rates
- Completed work-order operations
- Actual operation start/end times
- Processed quantities
- Machine failure incidents
- Downtime and recovery timestamps
- Operator warnings
- Maintenance events
- Material reservations and inventory lots

The architecture separates:
1. Deterministic backend calculations — numerical metrics and health score.
2. Gemini AI reasoning — diagnosis, failure-mode interpretation, explanations, and maintenance recommendations.

Gemini cannot override numerical calculations or directly mutate machine state.

---

## 2. Overall Health Score

The machine health score is deterministic and bounded from 0 to 100.

$$
H = \max(0, \min(100, \operatorname{round}(100-P_{total})))
$$

Where:

$$
P_{total}=P_{cycle}+P_{efficiency}+P_{failures}+P_{downtime}+P_{warnings}+P_{overdue}
$$

The score starts at 100 and loses points when measurable degradation or reliability problems are detected.

---

## 3. Cycle-Time Degradation

### Data Source

Cycle-time history comes from `work_orders.operations`.

The system selects operations where:

```text
assignedMachineId == machine._id
status == COMPLETED
```

For each completed operation it uses:
- `actualStart`
- `actualEnd`
- `processedQuantity`

Actual elapsed cycle time:

$$
Cycle\ Time=actualEnd-actualStart
$$

### Baseline and Recent Performance

Completed operations are ordered chronologically and divided into:

```text
Older 50%  -> Historical baseline
Newer 50%  -> Recent performance
```

Then:

$$
Baseline\ Cycle\ Time=average(older\ cycle\ times)
$$

$$
Recent\ Cycle\ Time=average(newer\ cycle\ times)
$$

### Degradation

$$
Cycle\ Degradation\ \%=
\frac{Recent\ Cycle\ Time-Baseline\ Cycle\ Time}
{Baseline\ Cycle\ Time}\times100
$$

Example:

```text
Baseline = 10 seconds
Recent   = 13 seconds
Degradation = 30%
```

### Penalty

No penalty is applied until degradation exceeds 10%.

$$
P_{cycle}=
\begin{cases}
0,&\Delta_{cycle}\le10\%\\
\min(30,(\Delta_{cycle}-10)\times0.8),&\Delta_{cycle}>10\%
\end{cases}
$$

For 30% degradation:

$$
(30-10)\times0.8=16
$$

Cycle penalty = 16 points.

---

## 4. Processing Rate Efficiency

### Configured Rate

The machine's nominal processing rate comes directly from:

```text
machines.processingRate
```

### Actual Rate

From completed operations in `work_orders.operations`:

```text
assignedMachineId == machine._id
status == COMPLETED
```

Use:

```text
quantityCompleted
durationSeconds
```

Then:

$$
Actual\ Processing\ Rate=
\frac{\sum quantityCompleted}
{\sum durationSeconds}
$$

### Efficiency

Compare observed rate with the configured machine rate:

$$
Processing\ Efficiency\ \%=
\frac{Actual\ Processing\ Rate}
{Configured\ Processing\ Rate}\times100
$$

Example:

```text
Configured = 2.0 units/sec
Actual     = 1.4 units/sec
Efficiency = 70%
```

### Penalty

$$
P_{efficiency}=
\begin{cases}
0,&E_{rate}\ge90\%\\
\min(25,(90-E_{rate})\times0.75),&E_{rate}<90\%
\end{cases}
$$

For 70% efficiency:

$$
(90-70)\times0.75=15
$$

Efficiency penalty = 15 points.

---

## 5. Failure Frequency

### Data Source

Failure information comes from:

```text
incidents
```

For the selected machine:

```text
machineId == machine._id
```

Relevant failure types:

```text
MACHINE_FAILURE
MACHINE_DOWN
OPERATION_FAILURE
```

Timestamp:

```text
detectedAt
```

### Failure Windows

```text
Failure Count 24h = failures detected within last 24 hours
Failure Count 7d  = failures detected within last 7 days
Failure Count 30d = failures detected within last 30 days
```

### Penalty

$$
P_{failures}=\min(35,(N_{fail,7d}\times12)+(N_{fail,24h}\times10))
$$

Example:

```text
2 failures in last 7 days
1 of those within 24 hours
```

$$
(2\times12)+(1\times10)=34
$$

Failure penalty = 34 points, capped at 35.

---

## 6. Downtime

### Data Source

Downtime is derived from `incidents`.

Fields:

```text
detectedAt
resolvedAt
```

For each resolved failure:

$$
Incident\ Downtime=resolvedAt-detectedAt
$$

Total:

$$
Total\ Downtime=\sum(resolvedAt-detectedAt)
$$

### Downtime Percentage

$$
Downtime\ \%=
\frac{Total\ Downtime}{Total\ Analysis\ Time}\times100
$$

Example:

```text
Analysis window = 100 hours
Downtime        = 12 hours
Downtime        = 12%
```

### Penalty

$$
P_{downtime}=
\begin{cases}
0,&D_{pct}\le5\%\\
\min(20,(D_{pct}-5)\times1.2),&D_{pct}>5\%
\end{cases}
$$

For 12% downtime:

$$
(12-5)\times1.2=8.4
$$

Downtime penalty = 8.4 points.

---

## 7. Operator Warning Penalty

Operator observations are stored through the incident system.

Find incidents:

```text
machineId == machine._id
```

with unresolved statuses such as:

```text
PENDING_REVIEW
OPEN
ACTION_REQUIRED
```

These represent warnings that have not yet been cleared.

### Penalty

$$
P_{warnings}=\min(20,N_{unresolved\ warnings}\times8)
$$

Example:

```text
3 unresolved warnings
3 × 8 = 24
```

The penalty is capped at 20 points.

---

## 8. Maintenance Overdue Penalty

Current maintenance state is available in:

```text
machines.status
machines.maintenanceEstimatedEnd
machines.maintenanceDurationMinutes
machines.maintenanceReason
```

Condition:

```text
machine.status == MAINTENANCE
AND
current time > maintenanceEstimatedEnd
```

Then:

$$
P_{overdue}=15
$$

Otherwise:

$$
P_{overdue}=0
$$

---

## 9. MTTR — Mean Time To Repair

MTTR measures how long machines take to recover from failures.

Source:

```text
incidents
```

For every resolved failure:

$$
Repair\ Time=resolvedAt-detectedAt
$$

Then:

$$
MTTR=
\frac{\sum Repair\ Time}
{Number\ of\ Resolved\ Failures}
$$

Example:

```text
Failure 1 = 30 minutes
Failure 2 = 50 minutes
Failure 3 = 40 minutes
```

$$
MTTR=\frac{30+50+40}{3}=40\ minutes
$$

---

## 10. MTBF — Mean Time Between Failures

MTBF represents average operating time between failures.

$$
MTBF=
\frac{Total\ Operating\ Time}
{Number\ of\ Failures}
$$

Operating history comes from machine-assigned operations and execution history.

Failure history comes from `incidents`.

Therefore:

```text
work_orders.operations
        ↓
operating history

incidents
        ↓
failure history

operating history + failure history
        ↓
MTBF
```

Higher MTBF generally indicates better reliability.

---

## 11. Actual Processing Rate — Complete Flow

Fetch completed operations from:

```text
work_orders.operations
```

Filter:

```text
assignedMachineId == machine._id
status == COMPLETED
```

Use:

```text
quantityCompleted
durationSeconds
```

Calculate:

$$
Actual\ Rate=
\frac{\sum quantityCompleted}
{\sum durationSeconds}
$$

Compare against:

```text
machines.processingRate
```

Then:

$$
Efficiency=
\frac{Actual\ Rate}
{Configured\ Rate}\times100
$$

---

## 12. Material Correlation

Material correlation is not itself a health-score penalty. It is a traceability and reasoning signal.

The Phase 6 traceability chain is:

```text
Incident
   ↓
Work Order
   ↓
Operation
   ↓
Material Reservation
   ↓
Inventory Lot
   ↓
Material
   ↓
Material Specification
```

Relevant collections:

```text
incidents
work_orders
material_reservations
inventory_lots
materials
material_specifications
material_transactions
```

Example:

```text
Machine M-03
      ↓
Machine incidents
      ↓
Affected Work Orders
      ↓
Operations
      ↓
Consumed Material Lots
      ↓
LOT-SS304-002
      ↓
SS304 / 2mm sheet
```

The system can tell Gemini:

> Several incidents occurred while processing SS304 2mm material from LOT-SS304-002.

### Important Engineering Rule

This is a correlation, not proof of causation.

The AI must not claim:

> SS304 caused the machine failure.

unless evidence actually establishes causality.

A valid conclusion is:

> A recurring association exists between the machine incidents and operations using SS304 2mm material from LOT-SS304-002.

---

## 13. Data Quality

The system evaluates how much historical evidence exists.

| Completed Operations | Data Quality |
|---:|---|
| `< 5` | `INSUFFICIENT_DATA` |
| `5–14` | `LIMITED_DATA` |
| `15–29` | `SUFFICIENT_DATA` |
| `30+` | `STRONG_HISTORY` |

Data quality does not directly subtract health points. It indicates how trustworthy the assessment is.

Example:

```text
Health Score: 91
Data Quality: INSUFFICIENT_DATA
```

Meaning:

> The available data looks healthy, but there is not enough history to make a strong predictive claim.

---

## 14. Complete Data-Fetch Map

| Metric / Input | Collection | Fields Used |
|---|---|---|
| Configured machine rate | `machines` | `processingRate` |
| Machine identity | `machines` | `_id`, `machineCode`, `name`, `type` |
| Completed operations | `work_orders` | `operations.assignedMachineId`, `operations.status` |
| Actual start | `work_orders` | `operations.actualStart` |
| Actual end | `work_orders` | `operations.actualEnd` |
| Processed quantity | `work_orders` | `operations.processedQuantity` / `quantityCompleted` |
| Operation duration | `work_orders` | `operations.durationSeconds` |
| Failure count | `incidents` | `machineId`, `type`, `detectedAt` |
| Failure recovery | `incidents` | `detectedAt`, `resolvedAt` |
| Operator warnings | `incidents` | `machineId`, `status`, reporting metadata |
| Maintenance events | `audit_events` / `machines` | maintenance audit actions, maintenance timestamps |
| Material correlation | `material_reservations` | `workOrderId`, `operationId`, `lotId`, `materialId` |
| Physical lot | `inventory_lots` | `lotNumber`, `materialId`, `specificationId`, `supplier`, `heatNumber` |
| Material specification | `material_specifications` | `grade`, `form`, dimensions |
| Material transactions | `material_transactions` | `workOrderId`, `operationId`, `lotId`, `transactionType`, `scrapReason` |

---

## 15. Complete Calculation Pipeline

```text
                         MongoDB
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
          ▼                 ▼                 ▼
      machines        work_orders        incidents
          │                 │                 │
    processingRate     operations       failures
          │                 │                 │
          │        ┌────────┼────────┐        │
          │        │        │        │        │
          │        ▼        ▼        ▼        ▼
          │     cycle     actual   quantity  downtime
          │     times      rate
          │        │        │        │        │
          └────────┴────────┴────────┴────────┘
                            │
                            ▼
                 MachineHealthService
                            │
          ┌─────────────────┼──────────────────┐
          │                 │                  │
          ▼                 ▼                  ▼
    Cycle Penalty    Efficiency Penalty   Failure Penalty
          │                 │                  │
          └─────────────────┼──────────────────┘
                            │
              ┌─────────────┼──────────────┐
              ▼             ▼              ▼
        Downtime        Warnings       Maintenance
         Penalty         Penalty          Penalty
              │             │              │
              └─────────────┼──────────────┘
                            ▼
                     Total Penalty
                            │
                            ▼
                 100 - Total Penalty
                            │
                            ▼
                    HEALTH SCORE
                      0 — 100
                            │
                            ▼
              Sanitized health context
                            │
                            ▼
                        Gemini
                            │
              ┌─────────────┼──────────────┐
              ▼             ▼              ▼
         Diagnosis     Failure Mode    Explanation
              │             │              │
              └─────────────┼──────────────┘
                            ▼
                  Maintenance Recommendation
                            │
                            ▼
                     Admin Approval
                            │
                            ▼
                   Safe Tool Registry
                            │
                            ▼
                Authoritative MES Service
```

---

## 16. What Gemini Actually Does

Gemini is not the calculator.

The backend calculates:

```text
Health Score
Cycle Degradation
Processing Efficiency
Failure Frequency
Downtime
MTBF
MTTR
Data Quality
Material Correlations
```

Gemini receives those already-calculated values and performs higher-level reasoning.

Example backend context:

```json
{
  "healthScore": 58,
  "cycleTimeDeviationPercent": 31.4,
  "processingRateEfficiencyPercent": 72,
  "failureCount7d": 2,
  "mttrSeconds": 2400,
  "operatorWarnings": 1,
  "problematicMaterials": [
    "SS304 2mm / LOT-SS304-002"
  ]
}
```

Gemini can reason:

> The machine is showing significant performance degradation. The combination of increasing cycle time, reduced processing efficiency, repeated recent failures, and an operator warning suggests elevated maintenance risk.

It can identify a plausible failure mode and recommend:

```text
Schedule preventive maintenance within the next 24 hours.
Inspect tooling and mechanical components.
Review operations involving the correlated material lot.
```

But Gemini cannot directly change:

```text
machine.status
```

or schedule maintenance by itself.

---

## 17. Why This Architecture Matters

The system separates measurement from interpretation.

### Deterministic backend

Responsible for:

- Mathematical calculations
- Database queries
- Historical aggregation
- Health score
- MTBF
- MTTR
- Processing efficiency
- Cycle degradation
- Downtime
- Failure counts
- Data quality
- Material traceability

These values are reproducible. The same database state produces the same numerical result.

### Gemini

Responsible for:

- Explaining what signals mean
- Identifying plausible failure modes
- Correlating multiple signals
- Producing human-readable diagnostics
- Suggesting preventive actions
- Explaining why maintenance may be appropriate

This makes the AI an engineering reasoning layer rather than an uncontrolled source of numerical truth.

---

## 18. Example — Healthy Machine

Suppose:

```text
Baseline cycle time = 5.0 sec
Recent cycle time   = 5.1 sec

Configured rate     = 2.0 units/sec
Actual rate         = 1.96 units/sec

7-day failures      = 0
24-hour failures    = 0

Downtime            = 1%
Warnings            = 0
```

Cycle degradation:

$$
\frac{5.1-5.0}{5.0}\times100=2\%
$$

Since 2% < 10%:

```text
Cycle Penalty = 0
```

Efficiency:

$$
\frac{1.96}{2.0}\times100=98\%
$$

Since 98% > 90%:

```text
Efficiency Penalty = 0
```

Also:

```text
Failure Penalty = 0
Downtime Penalty = 0
Warning Penalty = 0
Maintenance Penalty = 0
```

Therefore:

$$
H=100
$$

The machine is healthy based on the available evidence.

---

## 19. Example — Degrading Machine

Suppose:

```text
Baseline cycle time = 8 sec
Recent cycle time   = 12 sec
```

Then:

$$
\frac{12-8}{8}\times100=50\%
$$

Cycle penalty:

$$
(50-10)\times0.8=32
$$

Capped at:

```text
30 points
```

Suppose additionally:

```text
Processing efficiency = 72%
2 failures in 7 days
1 failure in last 24 hours
Downtime = 12%
1 unresolved operator warning
```

Efficiency penalty:

$$
(90-72)\times0.75=13.5
$$

Failure penalty:

$$
(2\times12)+(1\times10)=34
$$

Downtime penalty:

$$
(12-5)\times1.2=8.4
$$

Warning penalty:

$$
1\times8=8
$$

Total:

$$
30+13.5+34+8.4+8=93.9
$$

Health:

$$
100-93.9=6.1
$$

Rounded:

```text
Health Score = 6
```

This demonstrates how multiple independent signals combine into an extreme-risk result.

---

## 20. Maintenance and Historical Data

A maintenance event does not erase historical failures.

Historical incidents remain valuable because they are part of the machine's reliability history.

After maintenance, the machine should demonstrate recovery through new operating data:

```text
Maintenance completed
        ↓
Machine recovered
        ↓
New operations run
        ↓
Cycle time improves
        ↓
Processing efficiency improves
        ↓
No new failures
        ↓
Health score naturally recovers
```

This preserves historical truth while allowing current machine condition to improve.

A future enhancement can use a maintenance cutoff/baseline reset so that post-maintenance performance is evaluated separately from pre-maintenance degradation.

---

## 21. Judge-Friendly Summary

The predictive maintenance feature can be explained in one sentence:

> **The MES continuously turns ordinary production records into measurable machine-health signals, uses deterministic mathematics to calculate a reproducible health score, and then uses Gemini to interpret those signals and recommend safe maintenance actions.**

The complete architecture is:

```text
MES DATA
   ↓
DETERMINISTIC MATHEMATICS
   ↓
HEALTH SCORE + RELIABILITY METRICS
   ↓
GEMINI REASONING
   ↓
DIAGNOSIS + RECOMMENDATION
   ↓
ADMIN APPROVAL
   ↓
SAFE MES ACTION
```

There are no fabricated IoT readings, no random health scores, and no direct AI database mutations.

The result is an explainable AI maintenance system where every numerical conclusion can be traced back to actual MES records.
