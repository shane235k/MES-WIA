import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from bson import ObjectId

from app.core.database import get_db
from app.schemas.machine_health import (
    RiskLevel, DataQuality, TrendDirection,
    MachineHealthMetrics, HealthScoreBreakdownItem, HealthTrends,
    ProblematicMaterialCorrelation, MachineHealthAssessment,
    MachineHealthSummary
)
from app.schemas.machine import MachineStatus

logger = logging.getLogger(__name__)

class MachineHealthService:
    @staticmethod
    async def ensure_indexes():
        """Ensure indexes on machine_health_records collection."""
        try:
            db = get_db()
            await db.machine_health_records.create_index([("machineId", 1), ("generatedAt", -1)])
            await db.machine_health_records.create_index([("riskLevel", 1)])
            await db.machine_health_records.create_index([("generatedAt", -1)])
        except Exception as e:
            logger.warning(f"Could not create indexes on machine_health_records: {e}")

    @staticmethod
    async def get_machine_health_metrics(
        machine_id: str,
        time_window_days: int = 30
    ) -> MachineHealthAssessment:
        """
        Gathers historical operational data across MES collections and computes
        authoritative deterministic machine health metrics and health score.
        """
        db = get_db()
        await MachineHealthService.ensure_indexes()

        # 1. Fetch Machine document
        mach_query = {}
        if ObjectId.is_valid(machine_id):
            mach_query = {"$or": [{"_id": ObjectId(machine_id)}, {"machineCode": machine_id}]}
        else:
            mach_query = {"machineCode": machine_id}

        machine = await db.machines.find_one(mach_query)
        if not machine:
            raise ValueError(f"Machine '{machine_id}' not found")

        mach_id_str = str(machine["_id"])
        mach_code = machine.get("machineCode", "UNKNOWN")
        mach_name = machine.get("name", "Workstation")
        mach_type = machine.get("type", "GENERIC")
        configured_rate = float(machine.get("processingRate") or 1.0)
        current_status = machine.get("status", MachineStatus.IDLE.value)
        location = machine.get("location")

        now = datetime.utcnow()
        window_start = now - timedelta(days=time_window_days)
        window_24h = now - timedelta(hours=24)
        window_7d = now - timedelta(days=7)

        # 2. Gather Historical Completed Operations assigned to this machine
        # Search all work_orders with completed operations on this machine
        completed_ops = []
        async for wo in db.work_orders.find({
            "operations.assignedMachineId": mach_id_str
        }):
            wo_id = str(wo["_id"])
            wo_code = wo.get("workOrderCode")
            for op in wo.get("operations", []):
                if (op.get("assignedMachineId") == mach_id_str or op.get("assignedMachineCode") == mach_code) and op.get("status") == "COMPLETED":
                    act_start = op.get("actualStart") or op.get("startedAt")
                    act_end = op.get("actualEnd")
                    in_qty = float(op.get("processedQuantity") or op.get("inputQuantity") or wo.get("quantity", 10.0))
                    
                    dur_sec = None
                    if act_start and act_end:
                        dur_sec = max(1.0, (act_end - act_start).total_seconds())
                    elif op.get("durationSeconds"):
                        dur_sec = float(op.get("durationSeconds"))

                    completed_ops.append({
                        "workOrderId": wo_id,
                        "workOrderCode": wo_code,
                        "operationId": op.get("operationId"),
                        "name": op.get("name", ""),
                        "actualStart": act_start,
                        "actualEnd": act_end or now,
                        "durationSeconds": dur_sec or 5.0,
                        "unitCycleTime": (dur_sec or 5.0) / max(1.0, in_qty),
                        "quantity": in_qty,
                        "requiredMaterials": op.get("requiredMaterials", [])
                    })

        # Sort completed operations chronologically
        completed_ops.sort(key=lambda x: x["actualEnd"] if x["actualEnd"] else now)
        data_points = len(completed_ops)

        # 2. Discover Latest Maintenance Overhaul Anchor
        last_maint_date = machine.get("lastMaintenanceAt")
        recent_maint_count = 0
        async for aud in db.audit_events.find({
            "entityId": mach_id_str,
            "action": {"$in": ["MACHINE_MAINTENANCE_SCHEDULED", "MACHINE_RECOVERED", "PREDICTIVE_MAINTENANCE_APPROVED"]}
        }).sort("timestamp", -1):
            recent_maint_count += 1
            if not last_maint_date:
                last_maint_date = aud.get("timestamp")

        days_since_maint = round((now - last_maint_date).total_seconds() / 86400, 1) if last_maint_date else None
        maint_overdue = bool(machine.get("status") == MachineStatus.MAINTENANCE.value and machine.get("maintenanceEstimatedEnd") and machine.get("maintenanceEstimatedEnd") < now)

        # 3. Calculate Operational Metrics with Post-Maintenance Calibration Awareness
        total_processed_qty = sum(o["quantity"] for o in completed_ops)
        total_operating_sec = sum(o["durationSeconds"] for o in completed_ops)

        if data_points > 0:
            # If maintenance occurred, evaluate post-maintenance operations
            post_maint_ops = [o for o in completed_ops if o["actualEnd"] >= last_maint_date] if last_maint_date else completed_ops

            if last_maint_date and len(post_maint_ops) >= 2:
                # Machine has run multiple ops since overhaul -> Evaluate fresh performance
                baseline_cycle_time = round(1.0 / configured_rate, 2)
                recent_cycle_time = sum(o["unitCycleTime"] for o in post_maint_ops) / len(post_maint_ops)
                average_cycle_time = sum(o["durationSeconds"] for o in post_maint_ops) / max(1.0, sum(o["quantity"] for o in post_maint_ops))
                cycle_deviation_pct = round(((recent_cycle_time - baseline_cycle_time) / baseline_cycle_time) * 100, 2) if baseline_cycle_time > 0 else 0.0
                actual_processing_rate = round(sum(o["quantity"] for o in post_maint_ops) / max(1.0, sum(o["durationSeconds"] for o in post_maint_ops)), 4)
                rate_efficiency_pct = round((actual_processing_rate / configured_rate) * 100, 2) if configured_rate > 0 else 100.0
            elif last_maint_date and len(post_maint_ops) < 2:
                # Freshly overhauled machine -> Nominal calibrated baseline
                baseline_cycle_time = round(1.0 / configured_rate, 2)
                recent_cycle_time = baseline_cycle_time
                average_cycle_time = baseline_cycle_time
                cycle_deviation_pct = 0.0
                actual_processing_rate = configured_rate
                rate_efficiency_pct = 100.0
            else:
                # General historical average split
                split_idx = max(1, data_points // 2)
                older_ops = completed_ops[:split_idx]
                recent_ops = completed_ops[split_idx:] if split_idx < data_points else completed_ops

                baseline_cycle_time = sum(o["unitCycleTime"] for o in older_ops) / len(older_ops)
                recent_cycle_time = sum(o["unitCycleTime"] for o in recent_ops) / len(recent_ops)
                average_cycle_time = total_operating_sec / max(1.0, total_processed_qty)
                cycle_deviation_pct = round(((recent_cycle_time - baseline_cycle_time) / baseline_cycle_time) * 100, 2) if baseline_cycle_time > 0 else 0.0
                actual_processing_rate = round(total_processed_qty / total_operating_sec, 4) if total_operating_sec > 0 else configured_rate
                rate_efficiency_pct = round((actual_processing_rate / configured_rate) * 100, 2) if configured_rate > 0 else 100.0
        else:
            baseline_cycle_time = round(1.0 / configured_rate, 2)
            recent_cycle_time = baseline_cycle_time
            average_cycle_time = baseline_cycle_time
            cycle_deviation_pct = 0.0
            actual_processing_rate = configured_rate
            rate_efficiency_pct = 100.0

        # 4. Gather Failure Incidents with Maintenance Overhaul Resolution Filter
        incident_cursor = db.incidents.find({
            "$or": [
                {"machineId": mach_id_str},
                {"machineCode": mach_code}
            ]
        })

        incidents = []
        async for inc in incident_cursor:
            incidents.append(inc)

        failure_incidents = [i for i in incidents if i.get("type") in ["MACHINE_FAILURE", "MACHINE_DOWN", "OPERATION_FAILURE"]]
        total_failure_count = len(failure_incidents)

        # Active failures: Only failures occurring AFTER last maintenance, OR failures that are still UNRESOLVED
        active_failures = [
            i for i in failure_incidents
            if (i.get("status") in ["OPEN", "ACTION_REQUIRED", "PENDING_REVIEW", "INVESTIGATING"]) or
               (last_maint_date is None or (i.get("detectedAt") or i.get("reportedAt", now)) >= last_maint_date)
        ]

        failures_24h = sum(1 for i in active_failures if (i.get("detectedAt") or i.get("reportedAt", now)) >= window_24h)
        failures_7d = sum(1 for i in active_failures if (i.get("detectedAt") or i.get("reportedAt", now)) >= window_7d)
        failures_30d = sum(1 for i in active_failures if (i.get("detectedAt") or i.get("reportedAt", now)) >= window_start)

        # Downtime calculation
        downtime_durations = []
        for inc in failure_incidents:
            t_start = inc.get("detectedAt") or inc.get("reportedAt")
            t_end = inc.get("resolvedAt") or (now if inc.get("status") in ["OPEN", "ACTION_REQUIRED", "INVESTIGATING"] else t_start)
            if t_start and t_end:
                d_sec = max(0.0, (t_end - t_start).total_seconds())
                downtime_durations.append(d_sec)

        total_downtime_sec = sum(downtime_durations)
        avg_downtime_sec = (total_downtime_sec / len(downtime_durations)) if downtime_durations else 0.0
        max_downtime_sec = max(downtime_durations) if downtime_durations else 0.0

        # If maintenance was completed, compute active post-overhaul downtime ratio
        if last_maint_date and not active_failures:
            downtime_pct = 0.0
        else:
            downtime_pct = round((total_downtime_sec / max(1.0, total_operating_sec + total_downtime_sec)) * 100, 2)

        # MTBF & MTTR
        mtbf_sec = round(total_operating_sec / total_failure_count, 2) if total_failure_count > 0 else (total_operating_sec if total_operating_sec > 0 else None)
        mttr_sec = round(avg_downtime_sec, 2) if total_failure_count > 0 else None

        # 5. Gather Operator Warnings
        op_warnings = [
            i for i in incidents 
            if "Operator Report" in i.get("title", "") or i.get("status") == "PENDING_REVIEW" or i.get("reportedBy") != "SYSTEM"
        ]
        warnings_24h = sum(1 for w in op_warnings if (w.get("reportedAt") or now) >= window_24h)
        warnings_7d = sum(1 for w in op_warnings if (w.get("reportedAt") or now) >= window_7d)
        unresolved_warnings = sum(1 for w in op_warnings if w.get("status") in ["PENDING_REVIEW", "OPEN", "ACTION_REQUIRED"])
        recent_incident_count = len(incidents)

        # 6. Material Traceability Correlation (Phase 6 link: Machine -> WorkOrder -> Reservation -> Lot -> Spec)
        problematic_materials = await MachineHealthService._correlate_materials_with_failures(
            mach_id_str=mach_id_str,
            mach_code=mach_code,
            incidents=failure_incidents
        )

        mat_incident_count = sum(pm.incidentCount for pm in problematic_materials)
        mat_scrap_count = sum(pm.scrapCount for pm in problematic_materials)

        # 7. Evaluate Data Sufficiency
        if data_points < 5 and not last_maint_date:
            data_quality = DataQuality.INSUFFICIENT_DATA
            confidence_ceiling = 0.40
        elif data_points < 15:
            data_quality = DataQuality.LIMITED_DATA
            confidence_ceiling = 0.70
        elif data_points < 30:
            data_quality = DataQuality.SUFFICIENT_DATA
            confidence_ceiling = 0.90
        else:
            data_quality = DataQuality.STRONG_HISTORY
            confidence_ceiling = 1.00

        # 8. Deterministic Health Score Calculation (100-point transparent penalty model)
        breakdown: List[HealthScoreBreakdownItem] = []
        total_penalty = 0.0

        if data_quality == DataQuality.INSUFFICIENT_DATA and not last_maint_date:
            breakdown.append(HealthScoreBreakdownItem(
                signal="DATA_QUALITY_NOTICE",
                value=f"{data_points} completed operations",
                penalty=0.0,
                explanation="Sparse historical runtime records. Operating with default neutral baseline assessment."
            ))
            health_score = 85
        else:
            # Post-Maintenance Overhaul Notice
            if days_since_maint is not None and days_since_maint <= 14.0 and current_status != MachineStatus.DOWN.value and not active_failures:
                breakdown.append(HealthScoreBreakdownItem(
                    signal="POST_MAINTENANCE_CALIBRATION",
                    value=f"Overhauled {days_since_maint}d ago",
                    penalty=0.0,
                    explanation="Equipment serviced and calibrated. Operating under fresh post-maintenance baseline."
                ))

            # Penalty A: Cycle time degradation (> 10% slower)
            if cycle_deviation_pct > 10.0:
                p_cycle = min(30.0, round((cycle_deviation_pct - 10.0) * 0.8, 1))
                total_penalty += p_cycle
                breakdown.append(HealthScoreBreakdownItem(
                    signal="CYCLE_TIME_DEGRADATION",
                    value=f"+{cycle_deviation_pct}% vs baseline",
                    penalty=p_cycle,
                    explanation=f"Recent operations average {recent_cycle_time:.1f}s vs baseline {baseline_cycle_time:.1f}s."
                ))

            # Penalty B: Processing rate efficiency loss (< 90% efficiency)
            if rate_efficiency_pct < 90.0:
                p_eff = min(25.0, round((90.0 - rate_efficiency_pct) * 0.75, 1))
                total_penalty += p_eff
                breakdown.append(HealthScoreBreakdownItem(
                    signal="PROCESSING_RATE_LOSS",
                    value=f"{rate_efficiency_pct}% nominal efficiency",
                    penalty=p_eff,
                    explanation=f"Effective processing rate of {actual_processing_rate:.2f} u/s is below configured {configured_rate:.2f} u/s."
                ))

            # Penalty C: Recent failures (7d and 24h)
            if failures_7d > 0:
                p_fail = min(35.0, float(failures_7d * 12 + failures_24h * 10))
                total_penalty += p_fail
                breakdown.append(HealthScoreBreakdownItem(
                    signal="RECENT_FAILURES",
                    value=f"{failures_7d} active failures in 7 days ({failures_24h} in last 24h)",
                    penalty=p_fail,
                    explanation="Elevated active failure frequency during recent operating shifts."
                ))

            # Penalty D: Downtime percentage (> 5%)
            if downtime_pct > 5.0:
                p_down = min(20.0, round((downtime_pct - 5.0) * 1.2, 1))
                total_penalty += p_down
                breakdown.append(HealthScoreBreakdownItem(
                    signal="HIGH_DOWNTIME_RATIO",
                    value=f"{downtime_pct}% downtime ratio",
                    penalty=p_down,
                    explanation=f"Accumulated {total_downtime_sec/60:.1f} minutes of unplanned downtime."
                ))

            # Penalty E: Unresolved operator warnings
            if unresolved_warnings > 0:
                p_warn = min(20.0, float(unresolved_warnings * 8))
                total_penalty += p_warn
                breakdown.append(HealthScoreBreakdownItem(
                    signal="OPERATOR_WARNINGS",
                    value=f"{unresolved_warnings} unresolved warning(s)",
                    penalty=p_warn,
                    explanation="Operators logged equipment anomalies requiring review."
                ))

            # Penalty F: Overdue maintenance
            if maint_overdue:
                p_maint = 15.0
                total_penalty += p_maint
                breakdown.append(HealthScoreBreakdownItem(
                    signal="MAINTENANCE_OVERDUE",
                    value="Maintenance window expired",
                    penalty=p_maint,
                    explanation="Scheduled repair period exceeded without recovery signoff."
                ))

            health_score = max(0, min(100, int(round(100.0 - total_penalty))))

        # 9. Determine Risk Level from Authoritative Deterministic Metrics
        if current_status == MachineStatus.DOWN.value or failures_24h >= 2 or cycle_deviation_pct >= 50.0 or health_score < 50:
            risk_level = RiskLevel.CRITICAL
            maint_attention = True
        elif health_score < 70 or failures_7d >= 2 or cycle_deviation_pct >= 25.0 or unresolved_warnings >= 2:
            risk_level = RiskLevel.HIGH
            maint_attention = True
        elif health_score < 85 or cycle_deviation_pct >= 12.0 or unresolved_warnings >= 1 or downtime_pct >= 8.0:
            risk_level = RiskLevel.MEDIUM
            maint_attention = True
        else:
            risk_level = RiskLevel.LOW
            maint_attention = False

        # 10. Trends
        t_cycle = TrendDirection.DEGRADING if cycle_deviation_pct > 10.0 else (TrendDirection.IMPROVING if cycle_deviation_pct < -5.0 else TrendDirection.STABLE)
        t_rate = TrendDirection.DEGRADING if rate_efficiency_pct < 90.0 else (TrendDirection.IMPROVING if rate_efficiency_pct > 105.0 else TrendDirection.STABLE)
        t_fail = TrendDirection.INCREASING if failures_7d > 1 else TrendDirection.STABLE
        t_down = TrendDirection.INCREASING if downtime_pct > 10.0 else TrendDirection.STABLE

        metrics = MachineHealthMetrics(
            completedOperations=data_points,
            totalProcessedQuantity=round(total_processed_qty, 2),
            totalOperatingSeconds=round(total_operating_sec, 2),
            averageCycleTime=round(average_cycle_time, 2),
            baselineCycleTime=round(baseline_cycle_time, 2),
            cycleTimeDeviationPercent=cycle_deviation_pct,
            configuredProcessingRate=configured_rate,
            actualProcessingRate=actual_processing_rate,
            processingRateEfficiencyPercent=rate_efficiency_pct,
            failureCount24h=failures_24h,
            failureCount7d=failures_7d,
            failureCount30d=failures_30d,
            totalFailureCount=total_failure_count,
            totalDowntimeSeconds=round(total_downtime_sec, 2),
            downtimePercentage=downtime_pct,
            averageDowntimeSeconds=round(avg_downtime_sec, 2),
            maxDowntimeSeconds=round(max_downtime_sec, 2),
            mtbfSeconds=mtbf_sec,
            mttrSeconds=mttr_sec,
            operatorWarnings24h=warnings_24h,
            operatorWarnings7d=warnings_7d,
            unresolvedOperatorWarnings=unresolved_warnings,
            recentIncidentCount=recent_incident_count,
            daysSinceLastMaintenance=days_since_maint,
            recentMaintenanceCount=recent_maint_count,
            maintenanceOverdue=maint_overdue,
            materialRelatedIncidentCount=mat_incident_count,
            materialRelatedScrapCount=mat_scrap_count,
            problematicMaterials=problematic_materials
        )

        return MachineHealthAssessment(
            machineId=mach_id_str,
            machineCode=mach_code,
            machineName=mach_name,
            machineType=mach_type,
            location=location,
            status=current_status,
            healthScore=health_score,
            riskLevel=risk_level,
            maintenanceAttention=maint_attention,
            dataQuality=data_quality,
            dataPoints=data_points,
            confidenceCeiling=confidence_ceiling,
            metrics=metrics,
            healthScoreBreakdown=breakdown,
            trends=HealthTrends(
                cycleTime=t_cycle,
                processingRate=t_rate,
                failureFrequency=t_fail,
                downtime=t_down
            ),
            aiAssessment=None,
            generatedAt=now
        )

    @staticmethod
    async def _correlate_materials_with_failures(
        mach_id_str: str,
        mach_code: str,
        incidents: List[Dict[str, Any]]
    ) -> List[ProblematicMaterialCorrelation]:
        """
        Phase 6 Relational Traceability:
        Correlates machine incidents with materials, inventory lots, and specifications.
        """
        db = get_db()
        material_incidents_map = {}

        for inc in incidents:
            wo_id = inc.get("workOrderId")
            op_id = inc.get("operationId")
            if not wo_id:
                continue

            # Look up material reservations for this work order and operation
            res_query = {"workOrderId": str(wo_id)}
            if op_id:
                res_query["operationId"] = op_id

            async for res_doc in db.material_reservations.find(res_query):
                m_id = str(res_doc.get("materialId", ""))
                lot_id = str(res_doc.get("lotId", ""))
                spec_id = str(res_doc.get("specificationId", ""))

                if not m_id:
                    continue

                if m_id not in material_incidents_map:
                    # Fetch material, lot, and spec details
                    mat = await db.materials.find_one({"_id": ObjectId(m_id)}) if ObjectId.is_valid(m_id) else None
                    lot = await db.inventory_lots.find_one({"_id": ObjectId(lot_id)}) if (lot_id and ObjectId.is_valid(lot_id)) else None
                    spec = await db.material_specifications.find_one({"_id": ObjectId(spec_id)}) if (spec_id and ObjectId.is_valid(spec_id)) else None

                    material_incidents_map[m_id] = {
                        "materialId": m_id,
                        "materialCode": mat.get("materialCode") if mat else "RAW",
                        "materialName": mat.get("name") if mat else "Material",
                        "specificationId": spec_id,
                        "specificationCode": spec.get("specificationCode") if spec else None,
                        "grade": spec.get("grade") if spec else (lot.get("grade") if lot else None),
                        "lotNumber": lot.get("lotNumber") if lot else None,
                        "supplier": lot.get("supplier") if lot else None,
                        "incidentCount": 0,
                        "scrapCount": 0
                    }

                material_incidents_map[m_id]["incidentCount"] += 1

        # Check scrap transactions associated with this machine's operations
        async for tx in db.material_transactions.find({"transactionType": "SCRAP"}):
            m_id = str(tx.get("materialId", ""))
            if m_id in material_incidents_map:
                material_incidents_map[m_id]["scrapCount"] += 1

        correlations = []
        for m_data in material_incidents_map.values():
            if m_data["incidentCount"] > 0:
                obs_parts = [f"Potential correlation detected: {m_data['incidentCount']} incident(s) occurred while processing {m_data['materialName']}"]
                if m_data.get("grade"):
                    obs_parts.append(f"(Grade: {m_data['grade']})")
                if m_data.get("lotNumber"):
                    obs_parts.append(f"from Lot {m_data['lotNumber']}")
                if m_data.get("supplier"):
                    obs_parts.append(f"supplied by {m_data['supplier']}")
                obs_parts.append(". Note: Statistical correlation only, not confirmed causation.")

                correlations.append(ProblematicMaterialCorrelation(
                    materialId=m_data["materialId"],
                    materialCode=m_data["materialCode"],
                    materialName=m_data["materialName"],
                    specificationId=m_data["specificationId"],
                    specificationCode=m_data["specificationCode"],
                    grade=m_data["grade"],
                    lotNumber=m_data["lotNumber"],
                    supplier=m_data["supplier"],
                    incidentCount=m_data["incidentCount"],
                    scrapCount=m_data["scrapCount"],
                    observation=" ".join(obs_parts)
                ))

        return correlations

    @staticmethod
    async def save_health_assessment(assessment: MachineHealthAssessment) -> Dict[str, Any]:
        """Persist structured assessment into append-only db.machine_health_records."""
        db = get_db()
        record_doc = assessment.model_dump()
        record_doc["generatedAt"] = datetime.utcnow()
        res = await db.machine_health_records.insert_one(record_doc)
        record_doc["_id"] = str(res.inserted_id)
        record_doc["id"] = str(res.inserted_id)
        return record_doc

    @staticmethod
    async def get_health_history(machine_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieve chronological history of health assessments for trend visualization."""
        db = get_db()
        mach_query = {}
        if ObjectId.is_valid(machine_id):
            mach_query = {"$or": [{"machineId": machine_id}, {"machineCode": machine_id}]}
        else:
            mach_query = {"machineCode": machine_id}

        records = []
        cursor = db.machine_health_records.find(mach_query).sort("generatedAt", -1).limit(limit)
        async for doc in cursor:
            doc["id"] = str(doc["_id"])
            doc["_id"] = str(doc["_id"])
            records.append(doc)

        # Return ascending order for time series chart
        records.reverse()
        return records

    @staticmethod
    async def get_all_machines_health_summary() -> List[MachineHealthSummary]:
        """Fetch lightweight health summaries across all factory workstations."""
        db = get_db()
        summaries = []

        async for mach in db.machines.find():
            m_id = str(mach["_id"])
            try:
                assessment = await MachineHealthService.get_machine_health_metrics(m_id, time_window_days=30)
                
                # Check for last saved assessment
                last_rec = await db.machine_health_records.find_one(
                    {"machineId": m_id},
                    sort=[("generatedAt", -1)]
                )
                last_at = last_rec.get("generatedAt") if last_rec else None

                summaries.append(MachineHealthSummary(
                    machineId=m_id,
                    machineCode=mach.get("machineCode", "M-XX"),
                    machineName=mach.get("name", "Workstation"),
                    machineType=mach.get("type", "GENERIC"),
                    status=mach.get("status", "IDLE"),
                    healthScore=assessment.healthScore,
                    riskLevel=assessment.riskLevel,
                    dataQuality=assessment.dataQuality,
                    maintenanceAttention=assessment.maintenanceAttention,
                    cycleTimeDeviationPercent=assessment.metrics.cycleTimeDeviationPercent,
                    processingRateEfficiencyPercent=assessment.metrics.processingRateEfficiencyPercent,
                    lastAssessmentAt=last_at,
                    activeIncidentId=mach.get("currentIncidentId"),
                    maintenanceEstimatedEnd=mach.get("maintenanceEstimatedEnd")
                ))
            except Exception as e:
                logger.error(f"Error computing health summary for machine {m_id}: {e}")

        return summaries

    @staticmethod
    async def get_maintenance_alerts() -> List[Dict[str, Any]]:
        """Return machines requiring supervisor review or predictive maintenance attention."""
        summaries = await MachineHealthService.get_all_machines_health_summary()
        alerts = [
            s.model_dump() for s in summaries 
            if s.maintenanceAttention or s.riskLevel in [RiskLevel.HIGH, RiskLevel.CRITICAL] or s.status == MachineStatus.DOWN.value
        ]
        return alerts
