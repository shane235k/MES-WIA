from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.base import PyObjectId, BaseSchemaModel

class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class DataQuality(str, Enum):
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    LIMITED_DATA = "LIMITED_DATA"
    SUFFICIENT_DATA = "SUFFICIENT_DATA"
    STRONG_HISTORY = "STRONG_HISTORY"

class TrendDirection(str, Enum):
    IMPROVING = "IMPROVING"
    STABLE = "STABLE"
    DEGRADING = "DEGRADING"
    INCREASING = "INCREASING"
    DECREASING = "DECREASING"

class ProblematicMaterialCorrelation(BaseModel):
    materialId: str
    materialCode: Optional[str] = None
    materialName: str
    specificationId: Optional[str] = None
    specificationCode: Optional[str] = None
    grade: Optional[str] = None
    lotNumber: Optional[str] = None
    supplier: Optional[str] = None
    incidentCount: int = 0
    scrapCount: int = 0
    observation: str

class MachineHealthMetrics(BaseModel):
    # Operational metrics
    completedOperations: int = Field(default=0, description="Total operations completed on this machine")
    totalProcessedQuantity: float = Field(default=0.0, description="Total finished units produced")
    totalOperatingSeconds: float = Field(default=0.0, description="Cumulative running time")
    averageCycleTime: float = Field(default=0.0, description="Mean seconds per operation in recent window")
    baselineCycleTime: float = Field(default=0.0, description="Historical baseline seconds per operation")
    cycleTimeDeviationPercent: float = Field(default=0.0, description="Percentage deviation from baseline (positive = slower)")
    configuredProcessingRate: float = Field(default=1.0, description="Nominal units per second configured on machine")
    actualProcessingRate: float = Field(default=1.0, description="Observed effective units per second")
    processingRateEfficiencyPercent: float = Field(default=100.0, description="Actual vs configured rate efficiency percentage")

    # Reliability metrics
    failureCount24h: int = Field(default=0)
    failureCount7d: int = Field(default=0)
    failureCount30d: int = Field(default=0)
    totalFailureCount: int = Field(default=0)
    totalDowntimeSeconds: float = Field(default=0.0)
    downtimePercentage: float = Field(default=0.0, description="Downtime as percentage of total elapsed window")
    averageDowntimeSeconds: float = Field(default=0.0)
    maxDowntimeSeconds: float = Field(default=0.0)
    mtbfSeconds: Optional[float] = Field(default=None, description="Mean Operating Time Between Failures")
    mttrSeconds: Optional[float] = Field(default=None, description="Mean Time To Recovery / Repair")

    # Warning signals
    operatorWarnings24h: int = Field(default=0)
    operatorWarnings7d: int = Field(default=0)
    unresolvedOperatorWarnings: int = Field(default=0)
    recentIncidentCount: int = Field(default=0)

    # Maintenance metrics
    daysSinceLastMaintenance: Optional[float] = Field(default=None)
    recentMaintenanceCount: int = Field(default=0)
    maintenanceOverdue: bool = Field(default=False)

    # Material traceability correlations
    materialRelatedIncidentCount: int = Field(default=0)
    materialRelatedScrapCount: int = Field(default=0)
    problematicMaterials: List[ProblematicMaterialCorrelation] = Field(default_factory=list)

class HealthScoreBreakdownItem(BaseModel):
    signal: str = Field(..., description="Signal identifier e.g. CYCLE_TIME_DEGRADATION, RECENT_FAILURES")
    value: str = Field(..., description="Observed metric value string")
    penalty: float = Field(..., ge=0.0, description="Deduction points applied to health score")
    explanation: str = Field(..., description="Human-readable justification for the score contribution")

class AIPredictiveMaintenanceFinding(BaseModel):
    signal: str
    observation: str
    importance: str = "MEDIUM"  # LOW, MEDIUM, HIGH, CRITICAL

class AIPredictiveMaintenanceAction(BaseModel):
    priority: str = "HIGH"  # IMMEDIATE, HIGH, MEDIUM, LOW
    action: str
    reason: str
    toolName: Optional[str] = "schedule_maintenance"
    parameters: Dict[str, Any] = Field(default_factory=dict)

class AIPredictiveMaintenanceAssessment(BaseModel):
    summary: str = Field(..., description="Concise qualitative summary of machine health condition")
    failureMode: str = Field(..., description="Plausible mechanical/thermal/electrical degradation pattern or NORMAL")
    diagnosisConfidence: float = Field(default=0.85, ge=0.0, le=1.0)
    findings: List[AIPredictiveMaintenanceFinding] = Field(default_factory=list)
    recommendedActions: List[AIPredictiveMaintenanceAction] = Field(default_factory=list)
    recommendedMaintenanceWindow: str = Field(default="ROUTINE", description="IMMEDIATE | WITHIN_24_HOURS | NEXT_SCHEDULED_SHIFT | ROUTINE")
    materialCorrelationNote: Optional[str] = None
    proposedToolCalls: List[Dict[str, Any]] = Field(default_factory=list)

class HealthTrends(BaseModel):
    cycleTime: TrendDirection = TrendDirection.STABLE
    processingRate: TrendDirection = TrendDirection.STABLE
    failureFrequency: TrendDirection = TrendDirection.STABLE
    downtime: TrendDirection = TrendDirection.STABLE

class MachineHealthAssessment(BaseModel):
    machineId: str
    machineCode: str
    machineName: str
    machineType: str
    location: Optional[str] = None
    status: str = "IDLE"
    
    # Authoritative Backend Scoring
    healthScore: int = Field(..., ge=0, le=100, description="Authoritative 0-100 deterministic health score")
    riskLevel: RiskLevel = Field(..., description="Deterministic categorical risk")
    maintenanceAttention: bool = Field(default=False, description="Flag indicating machine warrants supervisor review")
    
    # Data Quality & Transparency
    dataQuality: DataQuality = Field(..., description="Sufficiency of historical operations evaluated")
    dataPoints: int = Field(default=0, description="Number of completed operations analyzed")
    confidenceCeiling: float = Field(default=1.0, ge=0.0, le=1.0)
    
    metrics: MachineHealthMetrics
    healthScoreBreakdown: List[HealthScoreBreakdownItem] = Field(default_factory=list)
    trends: HealthTrends = Field(default_factory=HealthTrends)
    
    # AI Qualitative Assessment
    aiAssessment: Optional[AIPredictiveMaintenanceAssessment] = None
    generatedAt: datetime = Field(default_factory=datetime.utcnow)

class MachineHealthRecordInDB(MachineHealthAssessment, BaseSchemaModel):
    id: Optional[PyObjectId] = Field(None, alias="_id")

class MachineHealthSummary(BaseModel):
    machineId: str
    machineCode: str
    machineName: str
    machineType: str
    status: str
    healthScore: int
    riskLevel: RiskLevel
    dataQuality: DataQuality
    maintenanceAttention: bool
    cycleTimeDeviationPercent: float
    processingRateEfficiencyPercent: float
    lastAssessmentAt: Optional[datetime] = None
    activeIncidentId: Optional[str] = None
    maintenanceEstimatedEnd: Optional[datetime] = None
