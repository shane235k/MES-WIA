import React, { useState, useEffect } from 'react';
import { 
  X, AlertTriangle, ShieldCheck, Activity, Wrench, 
  Sparkles, CheckCircle2, AlertOctagon, 
  BarChart2, Layers, RefreshCw
} from 'lucide-react';

interface ProblematicMaterial {
  materialId: string;
  materialCode?: string;
  materialName: string;
  grade?: string;
  lotNumber?: string;
  supplier?: string;
  incidentCount: number;
  scrapCount: number;
  observation: string;
}

interface HealthMetrics {
  completedOperations: number;
  totalProcessedQuantity: number;
  totalOperatingSeconds: number;
  averageCycleTime: number;
  baselineCycleTime: number;
  cycleTimeDeviationPercent: number;
  configuredProcessingRate: number;
  actualProcessingRate: number;
  processingRateEfficiencyPercent: number;
  failureCount24h: number;
  failureCount7d: number;
  failureCount30d: number;
  totalFailureCount: number;
  totalDowntimeSeconds: number;
  downtimePercentage: number;
  averageDowntimeSeconds: number;
  maxDowntimeSeconds: number;
  mtbfSeconds?: number;
  mttrSeconds?: number;
  operatorWarnings24h: number;
  operatorWarnings7d: number;
  unresolvedOperatorWarnings: number;
  recentIncidentCount: number;
  daysSinceLastMaintenance?: number;
  recentMaintenanceCount: number;
  maintenanceOverdue: boolean;
  materialRelatedIncidentCount: number;
  materialRelatedScrapCount: number;
  problematicMaterials: ProblematicMaterial[];
}

interface ScoreBreakdownItem {
  signal: string;
  value: string;
  penalty: number;
  explanation: string;
}

interface AIFinding {
  signal: string;
  observation: string;
  importance: string;
}

interface AIAction {
  priority: string;
  action: string;
  reason: string;
  toolName?: string;
  parameters?: Record<string, any>;
}

interface AIAssessment {
  summary: string;
  failureMode: string;
  diagnosisConfidence: number;
  findings: AIFinding[];
  recommendedActions: AIAction[];
  recommendedMaintenanceWindow: string;
  materialCorrelationNote?: string;
  proposedToolCalls?: any[];
}

interface MachineAssessment {
  machineId: string;
  machineCode: string;
  machineName: string;
  machineType: string;
  location?: string;
  status: string;
  healthScore: number;
  riskLevel: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  maintenanceAttention: boolean;
  dataQuality: 'INSUFFICIENT_DATA' | 'LIMITED_DATA' | 'SUFFICIENT_DATA' | 'STRONG_HISTORY';
  dataPoints: number;
  confidenceCeiling: number;
  metrics: HealthMetrics;
  healthScoreBreakdown: ScoreBreakdownItem[];
  trends: {
    cycleTime: string;
    processingRate: string;
    failureFrequency: string;
    downtime: string;
  };
  aiAssessment?: AIAssessment | null;
  generatedAt: string;
}

interface HistoryRecord {
  id: string;
  healthScore: number;
  riskLevel: string;
  dataQuality: string;
  generatedAt: string;
  aiAssessment?: {
    failureMode?: string;
    summary?: string;
  };
}

interface AIPredictiveMaintenanceModalProps {
  machineId: string;
  onClose: () => void;
  onMaintenanceScheduled?: () => void;
}

export const AIPredictiveMaintenanceModal: React.FC<AIPredictiveMaintenanceModalProps> = ({
  machineId,
  onClose,
  onMaintenanceScheduled
}) => {
  const [assessment, setAssessment] = useState<MachineAssessment | null>(null);
  const [history, setHistory] = useState<HistoryRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [assessingAI, setAssessingAI] = useState<boolean>(false);
  const [executingAction, setExecutingAction] = useState<boolean>(false);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const fetchMetrics = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch(`${API_URL}/api/predictive-maintenance/machines/${machineId}`);
      if (!res.ok) throw new Error('Failed to load machine health metrics');
      const data = await res.json();
      setAssessment(data);

      // Fetch history
      const histRes = await fetch(`${API_URL}/api/predictive-maintenance/machines/${machineId}/history?limit=10`);
      if (histRes.ok) {
        const histData = await histRes.json();
        setHistory(histData);
      }
    } catch (err: any) {
      setError(err.message || 'Error loading predictive maintenance data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (machineId) {
      fetchMetrics();
    }
  }, [machineId]);

  const handleRunAiAssessment = async () => {
    try {
      setAssessingAI(true);
      setError(null);
      const res = await fetch(`${API_URL}/api/predictive-maintenance/machines/${machineId}/assess`, {
        method: 'POST'
      });
      if (!res.ok) throw new Error('Failed to run AI health assessment');
      const updated = await res.json();
      setAssessment(updated);

      // Refresh history
      const histRes = await fetch(`${API_URL}/api/predictive-maintenance/machines/${machineId}/history?limit=10`);
      if (histRes.ok) {
        const histData = await histRes.json();
        setHistory(histData);
      }
    } catch (err: any) {
      setError(err.message || 'AI assessment failed');
    } finally {
      setAssessingAI(false);
    }
  };

  const handleApproveMaintenance = async (action: AIAction) => {
    if (!assessment) return;
    try {
      setExecutingAction(true);
      setError(null);
      const res = await fetch(`${API_URL}/api/predictive-maintenance/machines/${assessment.machineId}/approve-action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tool: action.toolName || 'schedule_maintenance',
          parameters: {
            durationMinutes: action.parameters?.durationMinutes || 45,
            reason: action.reason || `Approved AI Predictive Maintenance on ${assessment.machineCode}`
          },
          adminId: 'ADMIN'
        })
      });

      const resData = await res.json();
      if (!res.ok) throw new Error(resData.detail || 'Failed to approve maintenance action');

      setActionSuccess(`Maintenance successfully scheduled for ${assessment.machineCode} (${action.parameters?.durationMinutes || 45} mins).`);
      if (onMaintenanceScheduled) onMaintenanceScheduled();
      fetchMetrics();
    } catch (err: any) {
      setError(err.message || 'Action approval failed');
    } finally {
      setExecutingAction(false);
    }
  };

  const getRiskBadge = (risk: string) => {
    switch (risk) {
      case 'CRITICAL':
        return (
          <span className="px-3 py-1 bg-red-50 border border-red-200 text-red-700 font-bold rounded-full text-xs flex items-center gap-1.5 font-mono">
            <AlertOctagon className="w-3.5 h-3.5 text-red-600" />
            <span>CRITICAL RISK</span>
          </span>
        );
      case 'HIGH':
        return (
          <span className="px-3 py-1 bg-orange-50 border border-orange-200 text-orange-800 font-semibold rounded-full text-xs flex items-center gap-1.5 font-mono">
            <AlertTriangle className="w-3.5 h-3.5 text-orange-600" />
            <span>HIGH RISK</span>
          </span>
        );
      case 'MEDIUM':
        return (
          <span className="px-3 py-1 bg-amber-50 border border-amber-200 text-amber-800 font-semibold rounded-full text-xs flex items-center gap-1.5 font-mono">
            <Activity className="w-3.5 h-3.5 text-amber-600" />
            <span>MEDIUM RISK</span>
          </span>
        );
      default:
        return (
          <span className="px-3 py-1 bg-emerald-50 border border-emerald-200 text-emerald-800 font-semibold rounded-full text-xs flex items-center gap-1.5 font-mono">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
            <span>HEALTHY / LOW RISK</span>
          </span>
        );
    }
  };

  const getDataQualityBadge = (quality: string) => {
    switch (quality) {
      case 'STRONG_HISTORY':
        return <span className="px-2.5 py-0.5 bg-zinc-100 text-zinc-800 border border-zinc-200 rounded text-xs font-mono">Strong History (30+ ops)</span>;
      case 'SUFFICIENT_DATA':
        return <span className="px-2.5 py-0.5 bg-zinc-100 text-zinc-800 border border-zinc-200 rounded text-xs font-mono">Sufficient Data (15+ ops)</span>;
      case 'LIMITED_DATA':
        return <span className="px-2.5 py-0.5 bg-zinc-100 text-zinc-800 border border-zinc-200 rounded text-xs font-mono">Limited Data (5-14 ops)</span>;
      default:
        return <span className="px-2.5 py-0.5 bg-zinc-100 text-zinc-600 border border-zinc-200 rounded text-xs font-mono">Insufficient Data (&lt;5 ops)</span>;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs animate-fadeIn">
      <div className="bg-white border border-zinc-200 rounded-2xl w-full max-w-4xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden text-zinc-900">
        
        {/* Header */}
        <div className="px-6 py-4 border-b border-zinc-200 flex items-center justify-between bg-white">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-zinc-100 border border-zinc-200 rounded-xl text-zinc-900">
              <Sparkles className="w-5 h-5 text-zinc-900" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-zinc-900 tracking-tight">
                  AI Predictive Machine Health & Maintenance
                </h2>
                <span className="text-xs px-2 py-0.5 bg-zinc-100 text-zinc-700 rounded-md font-mono border border-zinc-200">
                  {assessment?.machineCode || '...'}
                </span>
              </div>
              <p className="text-xs text-zinc-500 mt-0.5">
                Deterministic MES telemetry, cycle degradation metrics, and safe tool execution
              </p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-1.5 text-zinc-400 hover:text-zinc-700 rounded-lg hover:bg-zinc-100 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          {loading ? (
            <div className="py-20 flex flex-col items-center justify-center text-zinc-500 gap-3">
              <RefreshCw className="w-8 h-8 animate-spin text-zinc-900" />
              <p className="text-xs font-mono font-medium">Calculating deterministic machine telemetry & health metrics...</p>
            </div>
          ) : error ? (
            <div className="p-4 bg-rose-50 border border-rose-200 rounded-xl text-rose-800 flex items-start gap-3 text-xs">
              <AlertTriangle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />
              <div>
                <h4 className="font-bold text-sm">Error Loading Machine Health</h4>
                <p className="mt-1 text-rose-700">{error}</p>
                <button 
                  onClick={fetchMetrics}
                  className="mt-3 px-3 py-1 bg-rose-100 hover:bg-rose-200 text-rose-900 rounded-md transition-colors font-medium cursor-pointer"
                >
                  Retry Analysis
                </button>
              </div>
            </div>
          ) : assessment ? (
            <>
              {/* Success notification banner */}
              {actionSuccess && (
                <div className="p-3.5 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-900 flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2.5 font-medium">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span>{actionSuccess}</span>
                  </div>
                  <button 
                    onClick={() => setActionSuccess(null)}
                    className="text-xs text-emerald-700 hover:underline ml-4 cursor-pointer"
                  >
                    Dismiss
                  </button>
                </div>
              )}

              {/* SECTION 1: DETERMINISTIC HEALTH SCORE HEADER CARD */}
              <div className="bg-zinc-50 border border-zinc-200 rounded-xl p-5 relative overflow-hidden">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="flex items-start gap-4">
                    {/* Score Box */}
                    <div className={`w-20 h-20 rounded-2xl flex flex-col items-center justify-center font-bold border shadow-xs ${
                      assessment.healthScore >= 85 
                        ? 'bg-emerald-50 border-emerald-200 text-emerald-800' 
                        : assessment.healthScore >= 70
                        ? 'bg-amber-50 border-amber-200 text-amber-800'
                        : assessment.healthScore >= 50
                        ? 'bg-orange-50 border-orange-200 text-orange-800'
                        : 'bg-rose-50 border-rose-200 text-rose-800'
                    }`}>
                      <span className="text-2xl font-black font-mono">{assessment.healthScore}</span>
                      <span className="text-[10px] uppercase tracking-wider text-zinc-500 font-mono">/ 100</span>
                    </div>

                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="text-base font-bold text-zinc-900">{assessment.machineName}</h3>
                        {getRiskBadge(assessment.riskLevel)}
                      </div>
                      <p className="text-xs text-zinc-500 mt-1">
                        Type: <span className="text-zinc-800 font-mono font-medium">{assessment.machineType}</span> | Location: <span className="text-zinc-800">{assessment.location || 'Factory Floor'}</span> | Status: <span className="text-zinc-900 font-semibold">{assessment.status}</span>
                      </p>
                      <div className="flex items-center gap-2 mt-2.5">
                        {getDataQualityBadge(assessment.dataQuality)}
                        <span className="text-xs text-zinc-400 font-mono">
                          {assessment.dataPoints} completed ops analyzed
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* AI Quick Assess Button */}
                  <div className="flex flex-col items-end justify-center">
                    <button
                      onClick={handleRunAiAssessment}
                      disabled={assessingAI}
                      className="px-4 py-2 bg-zinc-900 hover:bg-zinc-800 text-white font-medium rounded-xl text-xs flex items-center gap-2 shadow-xs transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                    >
                      {assessingAI ? (
                        <>
                          <RefreshCw className="w-3.5 h-3.5 animate-spin text-white" />
                          <span>Running Gemini Diagnostic...</span>
                        </>
                      ) : (
                        <>
                          <Sparkles className="w-3.5 h-3.5 text-zinc-300" />
                          <span>{assessment.aiAssessment ? 'Re-Run AI Diagnosis' : 'Run Gemini AI Diagnosis'}</span>
                        </>
                      )}
                    </button>
                    {assessment.generatedAt && (
                      <span className="text-[10px] text-zinc-400 mt-1.5 font-mono">
                        Last metric update: {new Date(assessment.generatedAt).toLocaleTimeString()}
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* SECTION 2: OPERATIONAL & RELIABILITY METRICS GRID */}
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <BarChart2 className="w-4 h-4 text-zinc-500" />
                  <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-500">
                    Deterministic Operational Telemetry
                  </h4>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {/* Metric 1: Cycle Time Deviation */}
                  <div className="bg-white border border-zinc-200 rounded-xl p-3.5 shadow-2xs">
                    <span className="text-[11px] text-zinc-500 font-medium">Cycle Time Trend</span>
                    <div className="flex items-baseline justify-between mt-1">
                      <span className={`text-base font-bold font-mono ${
                        assessment.metrics.cycleTimeDeviationPercent > 15 
                          ? 'text-rose-700' 
                          : assessment.metrics.cycleTimeDeviationPercent > 5 
                          ? 'text-amber-700' 
                          : 'text-emerald-700'
                      }`}>
                        {assessment.metrics.cycleTimeDeviationPercent > 0 ? '+' : ''}
                        {assessment.metrics.cycleTimeDeviationPercent}%
                      </span>
                      <span className="text-[10px] text-zinc-400 font-mono">
                        {assessment.metrics.averageCycleTime}s avg
                      </span>
                    </div>
                    <span className="text-[10px] text-zinc-400 block mt-0.5 font-mono">
                      Baseline: {assessment.metrics.baselineCycleTime}s
                    </span>
                  </div>

                  {/* Metric 2: Rate Efficiency */}
                  <div className="bg-white border border-zinc-200 rounded-xl p-3.5 shadow-2xs">
                    <span className="text-[11px] text-zinc-500 font-medium">Processing Efficiency</span>
                    <div className="flex items-baseline justify-between mt-1">
                      <span className={`text-base font-bold font-mono ${
                        assessment.metrics.processingRateEfficiencyPercent < 80
                          ? 'text-rose-700'
                          : assessment.metrics.processingRateEfficiencyPercent < 95
                          ? 'text-amber-700'
                          : 'text-emerald-700'
                      }`}>
                        {assessment.metrics.processingRateEfficiencyPercent}%
                      </span>
                      <span className="text-[10px] text-zinc-400 font-mono">
                        {assessment.metrics.actualProcessingRate} u/s
                      </span>
                    </div>
                    <span className="text-[10px] text-zinc-400 block mt-0.5 font-mono">
                      Nominal: {assessment.metrics.configuredProcessingRate} u/s
                    </span>
                  </div>

                  {/* Metric 3: Failure Incidents */}
                  <div className="bg-white border border-zinc-200 rounded-xl p-3.5 shadow-2xs">
                    <span className="text-[11px] text-zinc-500 font-medium">Recent Failures</span>
                    <div className="flex items-baseline justify-between mt-1">
                      <span className={`text-base font-bold font-mono ${
                        assessment.metrics.failureCount7d > 1 
                          ? 'text-rose-700' 
                          : assessment.metrics.failureCount7d > 0 
                          ? 'text-amber-700' 
                          : 'text-zinc-800'
                      }`}>
                        {assessment.metrics.failureCount7d}
                      </span>
                      <span className="text-[10px] text-zinc-400 font-mono">
                        {assessment.metrics.failureCount24h} in 24h
                      </span>
                    </div>
                    <span className="text-[10px] text-zinc-400 block mt-0.5 font-mono">
                      Total historical: {assessment.metrics.totalFailureCount}
                    </span>
                  </div>

                  {/* Metric 4: MTBF & MTTR */}
                  <div className="bg-white border border-zinc-200 rounded-xl p-3.5 shadow-2xs">
                    <span className="text-[11px] text-zinc-500 font-medium">MTBF / MTTR</span>
                    <div className="flex items-baseline justify-between mt-1">
                      <span className="text-xs font-bold font-mono text-zinc-800">
                        {assessment.metrics.mtbfSeconds ? `${Math.round(assessment.metrics.mtbfSeconds)}s` : 'N/A'}
                      </span>
                      <span className="text-xs font-bold font-mono text-zinc-600">
                        {assessment.metrics.mttrSeconds ? `${Math.round(assessment.metrics.mttrSeconds / 60)}m` : '0m'}
                      </span>
                    </div>
                    <span className="text-[10px] text-zinc-400 block mt-0.5 font-mono">
                      Downtime: {assessment.metrics.downtimePercentage}% ({Math.round(assessment.metrics.totalDowntimeSeconds / 60)}m)
                    </span>
                  </div>
                </div>
              </div>

              {/* SECTION 3: DETERMINISTIC HEALTH PENALTY BREAKDOWN */}
              {assessment.healthScoreBreakdown && assessment.healthScoreBreakdown.length > 0 && (
                <div className="bg-zinc-50 border border-zinc-200 rounded-xl p-4">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-500 mb-2.5">
                    Health Score Derivation Breakdown
                  </h4>
                  <div className="space-y-2">
                    {assessment.healthScoreBreakdown.map((item, idx) => (
                      <div key={idx} className="flex items-center justify-between text-xs py-1 border-b border-zinc-200/80 last:border-0">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-zinc-800 font-medium">{item.signal}</span>
                          <span className="text-zinc-400">({item.value})</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="text-zinc-500 text-[11px]">{item.explanation}</span>
                          {item.penalty > 0 ? (
                            <span className="text-rose-700 font-mono font-bold">-{item.penalty} pts</span>
                          ) : (
                            <span className="text-zinc-400 font-mono">0 pts</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* SECTION 4: PHASE 6 MATERIAL TRACEABILITY CORRELATION */}
              {assessment.metrics.problematicMaterials && assessment.metrics.problematicMaterials.length > 0 && (
                <div className="bg-zinc-50 border border-zinc-200 rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Layers className="w-4 h-4 text-zinc-700" />
                    <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-700">
                      Material Traceability Correlation (Phase 6)
                    </h4>
                  </div>
                  <div className="space-y-2">
                    {assessment.metrics.problematicMaterials.map((mat, idx) => (
                      <div key={idx} className="p-3 bg-white border border-zinc-200 rounded-lg text-xs">
                        <div className="flex items-center justify-between font-medium text-zinc-900">
                          <span className="font-bold">{mat.materialName} ({mat.materialCode || 'RAW'})</span>
                          <span className="text-amber-800 font-mono bg-amber-50 px-2 py-0.5 rounded border border-amber-200 font-bold">
                            {mat.incidentCount} incidents | {mat.scrapCount} scraps
                          </span>
                        </div>
                        <p className="text-zinc-600 text-[11px] mt-1 italic">
                          {mat.observation}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* SECTION 5: GEMINI AI QUALITATIVE DIAGNOSIS */}
              {assessment.aiAssessment ? (
                <div className="bg-white border border-zinc-300 rounded-xl p-5 space-y-4 shadow-xs">
                  <div className="flex items-center justify-between border-b border-zinc-200 pb-3">
                    <div className="flex items-center gap-2.5">
                      <Sparkles className="w-5 h-5 text-zinc-900" />
                      <div>
                        <h4 className="text-sm font-bold text-zinc-900 tracking-tight">
                          Gemini Qualitative Diagnostic Synthesis
                        </h4>
                        <span className="text-[11px] text-zinc-500">
                          Pattern: <span className="text-zinc-900 font-mono font-semibold">{assessment.aiAssessment.failureMode}</span> (Confidence: {Math.round(assessment.aiAssessment.diagnosisConfidence * 100)}%)
                        </span>
                      </div>
                    </div>
                    <div className="px-2.5 py-1 bg-zinc-100 border border-zinc-200 text-zinc-800 text-xs rounded-lg font-mono">
                      Window: {assessment.aiAssessment.recommendedMaintenanceWindow}
                    </div>
                  </div>

                  {/* Summary */}
                  <p className="text-xs leading-relaxed text-zinc-800 bg-zinc-50 p-3 rounded-lg border border-zinc-200 font-medium">
                    {assessment.aiAssessment.summary}
                  </p>

                  {/* Findings */}
                  {assessment.aiAssessment.findings && assessment.aiAssessment.findings.length > 0 && (
                    <div>
                      <h5 className="text-[11px] font-bold uppercase tracking-wider text-zinc-500 mb-2">
                        Key Empirical Findings
                      </h5>
                      <div className="space-y-1.5">
                        {assessment.aiAssessment.findings.map((f, idx) => (
                          <div key={idx} className="flex items-start gap-2 text-xs p-2 bg-zinc-50 rounded border border-zinc-200">
                            <span className={`px-1.5 py-0.5 text-[10px] font-mono rounded font-semibold ${
                              f.importance === 'CRITICAL' || f.importance === 'HIGH'
                                ? 'bg-rose-100 text-rose-800 border border-rose-200'
                                : 'bg-zinc-200 text-zinc-700'
                            }`}>
                              {f.signal}
                            </span>
                            <span className="text-zinc-700">{f.observation}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Recommended Preventive Actions */}
                  {assessment.aiAssessment.recommendedActions && assessment.aiAssessment.recommendedActions.length > 0 && (
                    <div>
                      <h5 className="text-[11px] font-bold uppercase tracking-wider text-zinc-500 mb-2">
                        Recommended Maintenance Actions
                      </h5>
                      <div className="space-y-2">
                        {assessment.aiAssessment.recommendedActions.map((act, idx) => (
                          <div key={idx} className="p-3 bg-zinc-50 border border-zinc-200 rounded-lg flex items-center justify-between gap-4">
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-semibold text-zinc-900">{act.action}</span>
                                <span className="text-[10px] px-2 py-0.5 bg-zinc-200 text-zinc-800 rounded font-mono font-bold">
                                  {act.priority}
                                </span>
                              </div>
                              <p className="text-[11px] text-zinc-500 mt-1">{act.reason}</p>
                            </div>

                            {/* Safe Maintenance Approval Button */}
                            <button
                              onClick={() => handleApproveMaintenance(act)}
                              disabled={executingAction || assessment.status === 'MAINTENANCE'}
                              className="px-3.5 py-2 bg-zinc-900 hover:bg-zinc-800 text-white font-medium rounded-lg text-xs flex items-center gap-1.5 whitespace-nowrap shadow-xs transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                            >
                              {executingAction ? (
                                <>
                                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                                  <span>Executing...</span>
                                </>
                              ) : assessment.status === 'MAINTENANCE' ? (
                                <>
                                  <CheckCircle2 className="w-3.5 h-3.5" />
                                  <span>In Maintenance</span>
                                </>
                              ) : (
                                <>
                                  <Wrench className="w-3.5 h-3.5" />
                                  <span>Approve & Schedule ({act.parameters?.durationMinutes || 45}m)</span>
                                </>
                              )}
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="p-8 bg-zinc-50 border border-dashed border-zinc-300 rounded-xl text-center">
                  <Sparkles className="w-8 h-8 text-zinc-400 mx-auto mb-2" />
                  <h4 className="text-sm font-semibold text-zinc-900">Gemini AI Diagnosis Not Yet Run</h4>
                  <p className="text-xs text-zinc-500 max-w-md mx-auto mt-1 mb-4">
                    Run an AI diagnostic check to synthesize cycle trends, identify plausible failure modes, and generate safe preventive maintenance recommendations.
                  </p>
                  <button
                    onClick={handleRunAiAssessment}
                    disabled={assessingAI}
                    className="px-4 py-2 bg-zinc-900 hover:bg-zinc-800 text-white font-medium text-xs rounded-lg inline-flex items-center gap-2 transition-colors cursor-pointer"
                  >
                    {assessingAI ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                    <span>Run Gemini AI Diagnosis</span>
                  </button>
                </div>
              )}

              {/* SECTION 6: HISTORICAL HEALTH ASSESSMENTS TREND */}
              {history.length > 0 && (
                <div className="bg-zinc-50 border border-zinc-200 rounded-xl p-4">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-zinc-500">
                      Assessment History & Health Trend
                    </h4>
                    <span className="text-[10px] text-zinc-400 font-mono">
                      {history.length} assessment snapshot(s)
                    </span>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                    {history.map((rec, idx) => (
                      <div key={idx} className="p-2.5 bg-white border border-zinc-200 rounded-lg text-center shadow-2xs">
                        <span className="text-[10px] text-zinc-400 block font-mono">
                          {new Date(rec.generatedAt).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                        </span>
                        <span className={`text-base font-bold font-mono block my-0.5 ${
                          rec.healthScore >= 85 ? 'text-emerald-700' : rec.healthScore >= 70 ? 'text-amber-700' : 'text-rose-700'
                        }`}>
                          {rec.healthScore}
                        </span>
                        <span className="text-[9px] text-zinc-500 block truncate font-mono">
                          {rec.riskLevel}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : null}
        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 border-t border-zinc-200 flex items-center justify-between bg-zinc-50">
          <span className="text-[11px] text-zinc-400 font-mono">
            Deterministic MES scoring & safe tool execution protocol
          </span>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-zinc-900 hover:bg-zinc-800 text-white font-medium rounded-xl text-xs transition-colors cursor-pointer"
          >
            Close
          </button>
        </div>

      </div>
    </div>
  );
};

export default AIPredictiveMaintenanceModal;
