import { useState, useEffect } from 'react';
import {
  Brain,
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  ShieldAlert,
  ArrowRight,
  RefreshCw,
  Terminal,
  Activity,
  Check,
  X,
  Play,
  HelpCircle,
  ChevronRight,
  Zap
} from 'lucide-react';

export interface AIInvestigationFinding {
  summary: string;
  observations: string[];
  affectedResources: string[];
  affectedOperations: string[];
  possibleImpact: string;
  confidence: number;
  recommendation?: string;
}

export interface AIToolAction {
  tool: string;
  version: string;
  parameters: Record<string, any>;
  reason: string;
  expectedEffect: string;
}

export interface AIActionPlan {
  summary: string;
  actions: AIToolAction[];
}

export interface AIOllamaVerification {
  status: 'VALID' | 'INVALID' | 'UNAVAILABLE';
  explanation: string;
  invalidSteps?: string[];
}

export interface AIOperationData {
  id: string;
  operationId: string;
  incidentId: string;
  incidentCode?: string;
  workOrderId?: string;
  workOrderCode?: string;
  machineId?: string;
  machineCode?: string;
  status: string;
  investigation?: AIInvestigationFinding;
  actionPlan?: AIActionPlan;
  toolCalls?: AIToolAction[];
  ollamaVerification?: AIOllamaVerification;
  executionResults?: any[];
  failureReason?: string;
  requestedBy: string;
  approvedBy?: string;
  createdAt: string;
  updatedAt: string;
  completedAt?: string;
}

interface AIInvestigationModalProps {
  isOpen: boolean;
  onClose: () => void;
  incidentId: string;
  incidentCode: string;
  onSuccess?: () => void;
}

export default function AIInvestigationModal({
  isOpen,
  onClose,
  incidentId,
  incidentCode,
  onSuccess
}: AIInvestigationModalProps) {
  const [aiOp, setAiOp] = useState<AIOperationData | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'INVESTIGATION' | 'ACTION_PLAN' | 'VERIFICATION' | 'EXECUTION'>('INVESTIGATION');
  const [aiStatus, setAiStatus] = useState<{ aiEnabled: boolean; isSimulationMode: boolean; model: string } | null>(null);

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const fetchAiStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/api/ai/status`);
      if (res.ok) {
        const data = await res.json();
        setAiStatus(data);
      }
    } catch (e) {
      console.warn('Could not fetch AI status:', e);
    }
  };

  const toggleAiMode = async () => {
    try {
      const res = await fetch(`${API_URL}/api/ai/simulation-mode`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setAiStatus(data);
      }
    } catch (e) {
      console.error('Failed to toggle AI mode:', e);
    }
  };

  // Fetch or initialize AI Operation for this incident
  const fetchActiveAIOperation = async () => {
    if (!incidentId) return;
    try {
      setLoading(true);
      setError(null);
      await fetchAiStatus();
      const res = await fetch(`${API_URL}/api/ai/operations/incident/${incidentId}`);
      if (res.ok) {
        const data = await res.json();
        if (data) {
          setAiOp(data);
          // Auto switch tab based on lifecycle
          if (data.status === 'AI_EXECUTION_COMPLETE' || data.status === 'AI_EXECUTING' || data.status === 'AI_EXECUTION_FAILED') {
            setActiveTab('EXECUTION');
          } else if (data.ollamaVerification) {
            setActiveTab('VERIFICATION');
          } else if (data.actionPlan) {
            setActiveTab('ACTION_PLAN');
          } else {
            setActiveTab('INVESTIGATION');
          }
          return;
        }
      }
      await startInvestigation();
    } catch (err: any) {
      setError(err.message || 'Failed to fetch AI operations state');
    } finally {
      setLoading(false);
    }
  };

  const startInvestigation = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch(`${API_URL}/api/ai/investigate/${incidentId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ requestedBy: 'ADMIN' })
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Investigation failed');
      }
      const data = await res.json();
      setAiOp(data);
      setActiveTab('INVESTIGATION');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const generateActionPlan = async () => {
    if (!aiOp) return;
    setActiveTab('ACTION_PLAN');
    try {
      setActionLoading(true);
      setError(null);
      const res = await fetch(`${API_URL}/api/ai/operations/${aiOp.id}/generate-action-plan`, {
        method: 'POST'
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Action planning failed');
      }
      const data = await res.json();
      setAiOp(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const verifyWithOllama = async () => {
    if (!aiOp) return;
    setActiveTab('VERIFICATION');
    try {
      setActionLoading(true);
      setError(null);
      const res = await fetch(`${API_URL}/api/ai/operations/${aiOp.id}/verify-ollama`, {
        method: 'POST'
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Ollama verification failed');
      }
      const data = await res.json();
      setAiOp(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const reinvestigateWithFeedback = async () => {
    if (!aiOp) return;
    setActiveTab('INVESTIGATION');
    try {
      setActionLoading(true);
      setError(null);
      const res = await fetch(`${API_URL}/api/ai/operations/${aiOp.id}/reinvestigate-with-feedback`, {
        method: 'POST'
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Feedback refinement failed');
      }
      const data = await res.json();
      setAiOp(data);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  const approveAndExecute = async () => {
    if (!aiOp) return;
    setActiveTab('EXECUTION');
    try {
      setActionLoading(true);
      setError(null);
      const res = await fetch(`${API_URL}/api/ai/operations/${aiOp.id}/approve-execute`, {
        method: 'POST'
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Execution failed');
      }
      const data = await res.json();
      setAiOp(data);
      if (onSuccess) onSuccess();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setActionLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen && incidentId) {
      fetchActiveAIOperation();
    }
  }, [isOpen, incidentId]);

  useEffect(() => {
    if (!isOpen || !incidentId) return;

    const wsUrl = `${API_URL.replace(/^http/, 'ws')}/api/ws/execution`;
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (
          msg.type === 'AI_OPERATION_UPDATED' &&
          msg.data?.incidentId === incidentId
        ) {
          setAiOp(msg.data);
        }
      } catch (e) {
        console.error('WS parse error:', e);
      }
    };

    return () => ws.close();
  }, [isOpen, incidentId]);

  if (!isOpen) return null;

  const isExecuted = aiOp?.status === 'AI_EXECUTION_COMPLETE';
  const isExecuting = aiOp?.status === 'AI_EXECUTING';
  const isFailed = aiOp?.status === 'AI_EXECUTION_FAILED';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs animate-fadeIn">
      <div className="bg-white border border-zinc-200 rounded-2xl w-full max-w-4xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden">
        
        <div className="px-6 py-4 border-b border-zinc-100 bg-white flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-zinc-900 flex items-center justify-center shadow-xs text-white">
              <Brain className="w-4 h-4 text-zinc-100" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold text-zinc-900 tracking-tight">
                  AI Operations Layer
                </h2>
                <span className="px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-zinc-100 text-zinc-800 border border-zinc-200">
                  {incidentCode}
                </span>
                {aiOp && (
                  <span className="text-xs font-mono text-zinc-400">
                    [{aiOp.operationId}]
                  </span>
                )}
              </div>
              <p className="text-xs text-zinc-500 font-normal mt-0.5">
                Deterministic Safe Tool Orchestration & Automated Action Planning
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            <button
              onClick={fetchActiveAIOperation}
              disabled={loading || actionLoading}
              title="Refresh State"
              className="p-1.5 text-zinc-400 hover:text-zinc-700 bg-zinc-100 hover:bg-zinc-200 rounded-lg transition-colors cursor-pointer"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${(loading || actionLoading) ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={onClose}
              className="p-1.5 text-zinc-400 hover:text-zinc-700 bg-zinc-100 hover:bg-zinc-200 rounded-lg transition-colors cursor-pointer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="px-6 py-2.5 bg-zinc-50 border-b border-zinc-200 flex items-center justify-between text-xs">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setActiveTab('INVESTIGATION')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                activeTab === 'INVESTIGATION'
                  ? 'bg-zinc-900 text-white font-semibold shadow-xs'
                  : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100'
              }`}
            >
              <Activity className="w-3.5 h-3.5" />
              <span>1. Investigation</span>
              {aiOp?.investigation && (
                <Check className="w-3 h-3 text-emerald-500" />
              )}
            </button>

            <ChevronRight className="w-3 h-3 text-zinc-400" />

            <button
              onClick={() => setActiveTab('ACTION_PLAN')}
              disabled={!aiOp?.investigation}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                !aiOp?.investigation
                  ? 'opacity-40 cursor-not-allowed text-zinc-400'
                  : activeTab === 'ACTION_PLAN'
                  ? 'bg-zinc-900 text-white font-semibold shadow-xs'
                  : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>2. Action Plan</span>
              {aiOp?.actionPlan && (
                <Check className="w-3 h-3 text-emerald-500" />
              )}
            </button>

            <ChevronRight className="w-3 h-3 text-zinc-400" />

            <button
              onClick={() => setActiveTab('VERIFICATION')}
              disabled={!aiOp?.actionPlan}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                !aiOp?.actionPlan
                  ? 'opacity-40 cursor-not-allowed text-zinc-400'
                  : activeTab === 'VERIFICATION'
                  ? 'bg-zinc-900 text-white font-semibold shadow-xs'
                  : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100'
              }`}
            >
              <Terminal className="w-3.5 h-3.5" />
              <span>3. Verification</span>
              {aiOp?.ollamaVerification && (
                <span className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${
                  aiOp.ollamaVerification.status === 'VALID' ? 'bg-emerald-100 text-emerald-800' :
                  aiOp.ollamaVerification.status === 'INVALID' ? 'bg-rose-100 text-rose-800' :
                  'bg-amber-100 text-amber-800'
                }`}>
                  {aiOp.ollamaVerification.status}
                </span>
              )}
            </button>

            <ChevronRight className="w-3 h-3 text-zinc-400" />

            <button
              onClick={() => setActiveTab('EXECUTION')}
              disabled={!aiOp?.actionPlan}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                !aiOp?.actionPlan
                  ? 'opacity-40 cursor-not-allowed text-zinc-400'
                  : activeTab === 'EXECUTION'
                  ? 'bg-zinc-900 text-white font-semibold shadow-xs'
                  : 'text-zinc-600 hover:text-zinc-900 hover:bg-zinc-100'
              }`}
            >
              <Play className="w-3.5 h-3.5" />
              <span>4. Execution & Audit</span>
              {isExecuted && <CheckCircle2 className="w-3 h-3 text-emerald-500" />}
              {isFailed && <AlertTriangle className="w-3 h-3 text-rose-500" />}
            </button>
          </div>

          <div className="flex items-center gap-2.5">
            {/* Quick Engine Simulation Mode Toggle */}
            <button
              onClick={toggleAiMode}
              title={aiStatus?.isSimulationMode ? "AI is in Outage Simulation Mode. Click to switch to Live Gemini." : "AI is Live via Gemini. Click to simulate AI outage / fallback mode."}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-[11px] font-mono border transition-all cursor-pointer ${
                aiStatus?.isSimulationMode
                  ? 'bg-amber-100/70 border-amber-300 text-amber-900 hover:bg-amber-200'
                  : 'bg-emerald-50 border-emerald-200 text-emerald-800 hover:bg-emerald-100'
              }`}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${aiStatus?.isSimulationMode ? 'bg-amber-500 animate-pulse' : 'bg-emerald-500'}`} />
              <span>{aiStatus?.isSimulationMode ? 'Fallback Mode' : `Live (${aiStatus?.model || 'Gemini'})`}</span>
            </button>

            <span className="text-zinc-500 font-mono text-[11px]">
              Status:{' '}
              <span className={`font-bold ${
                isExecuted ? 'text-emerald-700' :
                isFailed ? 'text-rose-700' :
                isExecuting ? 'text-amber-700 animate-pulse' :
                'text-zinc-800'
              }`}>
                {aiOp?.status || 'INITIALIZING'}
              </span>
            </span>
          </div>
        </div>

        {aiStatus?.isSimulationMode && (
          <div className="mx-6 mt-3 px-3.5 py-2 rounded-lg bg-amber-50/90 border border-amber-200/80 flex items-center justify-between text-amber-900 text-xs">
            <div className="flex items-center gap-2 font-mono text-[11px]">
              <Zap className="w-3.5 h-3.5 text-amber-600 shrink-0" />
              <span className="font-bold">AI Outage Simulation:</span>
              <span className="text-amber-800">Deterministic fallback recovery engine is active.</span>
            </div>
            <button
              onClick={startInvestigation}
              disabled={loading || actionLoading}
              className="text-[10px] font-bold uppercase tracking-wider text-amber-900 hover:underline cursor-pointer"
            >
              Re-Analyze
            </button>
          </div>
        )}

        {error && (
          <div className="mx-6 mt-4 p-3 rounded-lg bg-rose-50 border border-rose-200 flex items-start gap-2 text-rose-800 text-xs">
            <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            <div className="flex-1">
              <span className="font-semibold block font-mono text-[11px]">Error Encounted</span>
              <span>{error}</span>
            </div>
            <button onClick={() => setError(null)} className="text-rose-500 hover:text-rose-700">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        <div className="p-6 overflow-y-auto flex-1 space-y-6">
          {loading ? (
            <div className="py-20 flex flex-col items-center justify-center text-zinc-500 space-y-3">
              <RefreshCw className="w-8 h-8 animate-spin text-zinc-900" />
              <div className="text-center font-mono">
                <p className="text-xs font-bold text-zinc-800">
                  {aiStatus?.isSimulationMode
                    ? 'Executing Deterministic Investigation Engine...'
                    : 'Dispatching Telemetry Snapshot to Gemini AI...'}
                </p>
                <p className="text-[11px] text-zinc-400 mt-1">
                  Synthesizing root cause, equipment impact, and downstream DAG dependencies.
                </p>
              </div>
            </div>
          ) : !aiOp ? (
            <div className="text-center py-16 text-zinc-500 text-xs font-mono space-y-3">
              <Brain className="w-8 h-8 text-zinc-300 mx-auto" />
              <p>No active AI operation found for this incident.</p>
              <button
                onClick={startInvestigation}
                className="px-4 py-2 bg-zinc-900 text-white rounded-lg text-xs font-sans hover:bg-zinc-800 cursor-pointer"
              >
                Start Investigation
              </button>
            </div>
          ) : (
            <>
              {activeTab === 'INVESTIGATION' && (
                <div className="space-y-4 animate-fadeIn">
                  {actionLoading ? (
                    <div className="py-16 bg-zinc-50 border border-zinc-200 rounded-2xl flex flex-col items-center justify-center text-center space-y-3">
                      <RefreshCw className="w-7 h-7 text-zinc-900 animate-spin" />
                      <div>
                        <h4 className="text-xs font-bold text-zinc-900">Re-evaluating Incident Diagnosis with Gemini</h4>
                        <p className="text-[11px] text-zinc-500 mt-1 max-w-sm">
                          Synthesizing root cause and refining recommendation to resolve Ollama verification critique...
                        </p>
                      </div>
                    </div>
                  ) : aiOp.investigation ? (
                    <>
                      <div className="p-4 rounded-xl bg-zinc-50 border border-zinc-200">
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-semibold text-zinc-900 uppercase tracking-wider">
                              Diagnostic Synthesis
                            </span>
                            {aiOp.ollamaVerification && (
                              <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-zinc-200 text-zinc-800 font-semibold border border-zinc-300">
                                Feedback-Refined
                              </span>
                            )}
                          </div>
                          <span className="px-2.5 py-0.5 rounded-full bg-white text-zinc-800 text-xs font-mono border border-zinc-200 font-semibold shadow-2xs">
                            {Math.round(aiOp.investigation.confidence * 100)}% Confidence
                          </span>
                        </div>
                        <p className="text-sm font-semibold text-zinc-900 leading-snug">
                          {aiOp.investigation.summary}
                        </p>
                        {aiOp.investigation.recommendation && (
                          <div className="mt-3 pt-3 border-t border-zinc-200 text-xs flex items-start gap-2">
                            <strong className="text-zinc-900 shrink-0">Recommendation:</strong>
                            <span className="text-zinc-700">{aiOp.investigation.recommendation}</span>
                          </div>
                        )}
                      </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="p-4 rounded-xl bg-white border border-zinc-200 shadow-xs">
                      <h4 className="text-xs font-semibold text-zinc-900 uppercase tracking-wider flex items-center gap-1.5 mb-3">
                        <Activity className="w-3.5 h-3.5 text-zinc-700" />
                        <span>Telemetry Observations</span>
                      </h4>
                      <ul className="space-y-2">
                        {aiOp.investigation.observations?.map((obs, idx) => (
                          <li key={idx} className="flex items-start gap-2 text-xs text-zinc-700">
                            <span className="w-1.5 h-1.5 rounded-full bg-zinc-900 mt-1.5 shrink-0" />
                            <span>{obs}</span>
                          </li>
                        ))}
                      </ul>
                    </div>

                    <div className="p-4 rounded-xl bg-white border border-zinc-200 shadow-xs">
                      <h4 className="text-xs font-semibold text-zinc-900 uppercase tracking-wider flex items-center gap-1.5 mb-3">
                        <ShieldAlert className="w-3.5 h-3.5 text-amber-600" />
                        <span>Downstream Impact & Delays</span>
                      </h4>
                      <p className="text-xs text-zinc-700 leading-relaxed">
                        {aiOp.investigation.possibleImpact || 'No severe downstream bottlenecks detected in active schedule.'}
                      </p>

                      <div className="mt-4 pt-3 border-t border-zinc-100 grid grid-cols-2 gap-2 text-xs">
                        <div>
                          <span className="text-zinc-500 block text-[11px]">Affected Equipment</span>
                          <div className="flex flex-wrap gap-1 mt-1">
                            {aiOp.investigation.affectedResources?.map((res, i) => (
                              <span key={i} className="px-2 py-0.5 rounded bg-zinc-100 text-zinc-800 text-[11px] font-mono border border-zinc-200">
                                {res}
                              </span>
                            ))}
                          </div>
                        </div>
                        <div>
                          <span className="text-zinc-500 block text-[11px]">Halted Operations</span>
                          <div className="flex flex-wrap gap-1 mt-1">
                            {aiOp.investigation.affectedOperations?.map((op, i) => (
                              <span key={i} className="px-2 py-0.5 rounded bg-rose-50 text-rose-800 border border-rose-200 text-[11px] font-mono font-semibold">
                                {op}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-4 border-t border-zinc-200">
                    <p className="text-xs text-zinc-500">
                      Phase 1 Complete. Generate deterministic safe recovery tools sequence.
                    </p>
                    <button
                      onClick={generateActionPlan}
                      disabled={actionLoading}
                      className="px-4 py-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-white font-medium text-xs shadow-xs flex items-center gap-1.5 transition-colors cursor-pointer"
                    >
                      {actionLoading ? (
                        <>
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                          <span>Synthesizing Tool Sequence...</span>
                        </>
                      ) : (
                        <>
                          <span>Generate Action Plan</span>
                          <ArrowRight className="w-3.5 h-3.5" />
                        </>
                      )}
                    </button>
                  </div>
                    </>
                  ) : null}
                </div>
              )}

              {activeTab === 'ACTION_PLAN' && (
                <div className="space-y-4 animate-fadeIn">
                  {actionLoading && !aiOp?.actionPlan ? (
                    <div className="py-16 bg-zinc-50 border border-zinc-200 rounded-2xl flex flex-col items-center justify-center text-center space-y-3">
                      <RefreshCw className="w-7 h-7 text-zinc-900 animate-spin" />
                      <div>
                        <h4 className="text-xs font-bold text-zinc-900">Synthesizing Recovery Action Plan with Gemini</h4>
                        <p className="text-[11px] text-zinc-500 mt-1 max-w-sm">
                          Mapping safe registered tools (reassign machine, reschedule workflow, quarantine lot) to resolve the incident...
                        </p>
                      </div>
                    </div>
                  ) : !aiOp?.actionPlan ? (
                    <div className="text-center py-12 space-y-3">
                      <Sparkles className="w-8 h-8 text-zinc-400 mx-auto" />
                      <div>
                        <h4 className="text-xs font-semibold text-zinc-900">Action Plan Not Yet Generated</h4>
                        <p className="text-[11px] text-zinc-500 mt-0.5">Synthesize a mapped safe tool recovery sequence.</p>
                      </div>
                      <button
                        onClick={generateActionPlan}
                        disabled={actionLoading}
                        className="px-4 py-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-white font-medium text-xs transition-colors inline-flex items-center gap-1.5 cursor-pointer"
                      >
                        {actionLoading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                        <span>Synthesize Safe Tool Sequence</span>
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="p-4 rounded-xl bg-zinc-50 border border-zinc-200 flex items-center justify-between">
                        <div>
                          <div className="text-xs font-semibold text-zinc-900 uppercase tracking-wider">
                            Mapped Safe Tool Execution Sequence
                          </div>
                          <p className="text-xs text-zinc-700 mt-1">
                            {aiOp.actionPlan.summary}
                          </p>
                        </div>
                        <span className="px-2.5 py-0.5 rounded-md bg-zinc-100 border border-zinc-200 text-zinc-800 text-xs font-mono font-semibold">
                          {aiOp.actionPlan.actions?.length || 0} Safe Tools
                        </span>
                      </div>

                      <div className="space-y-2.5">
                        {aiOp.actionPlan.actions?.map((act, index) => (
                          <div
                            key={index}
                            className="p-4 rounded-xl bg-white border border-zinc-200 hover:border-zinc-300 shadow-xs transition-colors flex items-start gap-3.5"
                          >
                            <div className="w-6 h-6 rounded-md bg-zinc-900 text-white font-mono text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
                              {index + 1}
                            </div>

                            <div className="flex-1 space-y-2">
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                  <span className="font-mono text-xs font-bold text-zinc-900 bg-zinc-100 px-2 py-0.5 rounded border border-zinc-200">
                                    {act.tool}
                                  </span>
                                  <span className="text-[10px] font-mono text-zinc-400">
                                    v{act.version || '1.0'}
                                  </span>
                                </div>
                                <span className="text-[11px] text-emerald-700 font-mono font-medium">
                                  {act.expectedEffect}
                                </span>
                              </div>

                              <p className="text-xs text-zinc-700">
                                <span className="font-semibold text-zinc-900">Reason:</span> {act.reason}
                              </p>

                              <div className="p-2.5 rounded-lg bg-zinc-50 border border-zinc-200 font-mono text-[11px] text-zinc-800">
                                <div className="text-[10px] uppercase text-zinc-500 font-semibold mb-1">
                                  Tool Parameters
                                </div>
                                <pre className="whitespace-pre-wrap overflow-x-auto text-zinc-900 text-[11px]">
                                  {JSON.stringify(act.parameters, null, 2)}
                                </pre>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>

                      <div className="flex items-center justify-between pt-4 border-t border-zinc-200">
                        <button
                          onClick={verifyWithOllama}
                          disabled={actionLoading}
                          className="px-3.5 py-2 rounded-lg bg-white hover:bg-zinc-50 text-zinc-700 font-medium text-xs border border-zinc-200 shadow-xs transition-colors flex items-center gap-1.5 cursor-pointer"
                        >
                          <Terminal className="w-3.5 h-3.5 text-zinc-600" />
                          <span>Verify with Ollama (Optional)</span>
                        </button>

                        <div className="flex items-center gap-2">
                          <button
                            onClick={approveAndExecute}
                            disabled={actionLoading || isExecuted}
                            className="px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 active:scale-98 text-white font-semibold text-xs shadow-xs flex items-center gap-1.5 transition-all cursor-pointer"
                          >
                            <ShieldAlert className="w-3.5 h-3.5" />
                            <span>Approve & Execute Recovery</span>
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'VERIFICATION' && (
                <div className="space-y-4 animate-fadeIn">
                  {actionLoading && !aiOp?.ollamaVerification ? (
                    <div className="py-16 bg-zinc-50 border border-zinc-200 rounded-2xl flex flex-col items-center justify-center text-center space-y-3">
                      <RefreshCw className="w-7 h-7 text-zinc-900 animate-spin" />
                      <div>
                        <h4 className="text-xs font-bold text-zinc-900">Verifying Recovery Plan with Ollama</h4>
                        <p className="text-[11px] text-zinc-500 mt-1 max-w-sm">
                          Dispatching proposed tool sequence to local mistral:latest model to check alignment with diagnostic findings...
                        </p>
                      </div>
                    </div>
                  ) : !aiOp?.ollamaVerification ? (
                    <div className="text-center py-12 space-y-3">
                      <Terminal className="w-8 h-8 text-zinc-400 mx-auto" />
                      <div>
                        <h4 className="text-xs font-semibold text-zinc-900">No Ollama Verification Run Yet</h4>
                        <p className="text-[11px] text-zinc-500 mt-0.5">
                          Verification checks correspondence between tool sequence and recommendations.
                        </p>
                      </div>
                      <button
                        onClick={verifyWithOllama}
                        disabled={actionLoading}
                        className="px-4 py-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-white font-medium text-xs transition-colors inline-flex items-center gap-1.5 cursor-pointer"
                      >
                        {actionLoading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Terminal className="w-3.5 h-3.5" />}
                        <span>Run Ollama Verification</span>
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className={`p-5 rounded-xl border ${
                        aiOp.ollamaVerification.status === 'VALID'
                          ? 'bg-emerald-50/70 border-emerald-200 text-emerald-900'
                          : aiOp.ollamaVerification.status === 'INVALID'
                          ? 'bg-rose-50/70 border-rose-200 text-rose-900'
                          : 'bg-amber-50/70 border-amber-200 text-amber-900'
                      }`}>
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs font-semibold uppercase tracking-wider">
                            Ollama Local Verification Result
                          </span>
                          <span className={`px-2.5 py-0.5 rounded-md text-xs font-bold font-mono uppercase ${
                            aiOp.ollamaVerification.status === 'VALID'
                              ? 'bg-emerald-100 text-emerald-800 border border-emerald-300'
                              : aiOp.ollamaVerification.status === 'INVALID'
                              ? 'bg-rose-100 text-rose-800 border border-rose-300'
                              : 'bg-amber-100 text-amber-800 border border-amber-300'
                          }`}>
                            {aiOp.ollamaVerification.status}
                          </span>
                        </div>

                        <p className="text-xs text-zinc-800 leading-relaxed font-sans">
                          {aiOp.ollamaVerification.explanation}
                        </p>

                        {aiOp.ollamaVerification.invalidSteps && aiOp.ollamaVerification.invalidSteps.length > 0 && (
                          <div className="mt-3 pt-3 border-t border-zinc-200 text-xs">
                            <span className="font-semibold text-rose-800 block mb-1">Flagged Step Discrepancies:</span>
                            <ul className="list-disc list-inside space-y-1 text-zinc-700 font-mono text-[11px]">
                              {aiOp.ollamaVerification.invalidSteps.map((step, idx) => (
                                <li key={idx}>
                                  {typeof step === 'object' ? JSON.stringify(step) : String(step)}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>

                      <div className="p-3 rounded-lg bg-zinc-50 border border-zinc-200 text-xs text-zinc-600 flex items-start gap-2">
                        <HelpCircle className="w-4 h-4 text-zinc-500 shrink-0 mt-0.5" />
                        <div>
                          <strong className="text-zinc-800 font-semibold">Advisory Boundary Note:</strong> Ollama verifies syntactic correspondence between the tool sequence and the recommendation. Final execution authorization resides exclusively with the Admin.
                        </div>
                      </div>

                      <div className="flex flex-col sm:flex-row sm:items-center justify-between pt-4 border-t border-zinc-200 gap-3">
                        <button
                          onClick={reinvestigateWithFeedback}
                          disabled={actionLoading}
                          className="px-4 py-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-white font-medium text-xs shadow-xs flex items-center justify-center gap-1.5 transition-all cursor-pointer"
                        >
                          <RefreshCw className={`w-3.5 h-3.5 ${actionLoading ? 'animate-spin' : ''}`} />
                          <span>Send Feedback to Gemini & Re-Analyze</span>
                        </button>

                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => setActiveTab('ACTION_PLAN')}
                            className="px-3.5 py-2 rounded-lg bg-white hover:bg-zinc-50 text-zinc-700 font-medium text-xs border border-zinc-200 shadow-xs transition-colors cursor-pointer"
                          >
                            <span>Review Action Plan</span>
                          </button>
                          <button
                            onClick={approveAndExecute}
                            disabled={actionLoading || isExecuted}
                            className="px-5 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 active:scale-98 text-white font-semibold text-xs shadow-xs flex items-center gap-1.5 transition-all cursor-pointer"
                          >
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>Confirm & Execute Plan</span>
                          </button>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'EXECUTION' && (
                <div className="space-y-4 animate-fadeIn">
                  {actionLoading && (!aiOp?.executionResults || aiOp.executionResults.length === 0) ? (
                    <div className="py-16 bg-zinc-50 border border-zinc-200 rounded-2xl flex flex-col items-center justify-center text-center space-y-3">
                      <RefreshCw className="w-7 h-7 text-zinc-900 animate-spin" />
                      <div>
                        <h4 className="text-xs font-bold text-zinc-900">Executing Shop-Floor Recovery</h4>
                        <p className="text-[11px] text-zinc-500 mt-1 max-w-sm">
                          Applying state transitions sequentially via safe backend tool services...
                        </p>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className={`p-4 rounded-xl border flex items-center justify-between ${
                        isExecuted
                          ? 'bg-emerald-50 border-emerald-200 text-emerald-900'
                          : isFailed
                          ? 'bg-rose-50 border-rose-200 text-rose-900'
                          : 'bg-zinc-50 border-zinc-200 text-zinc-900'
                      }`}>
                        <div className="flex items-center gap-3">
                          {isExecuted && <CheckCircle2 className="w-5 h-5 text-emerald-600" />}
                          {isFailed && <AlertTriangle className="w-5 h-5 text-rose-600" />}
                          {isExecuting && <RefreshCw className="w-5 h-5 text-zinc-900 animate-spin" />}
                          <div>
                            <h4 className="text-xs font-bold">
                              {isExecuted ? 'Recovery Action Plan Executed Successfully' :
                               isFailed ? 'Execution Interrupted on Error' :
                               'Executing Approved Safe Tools...'}
                            </h4>
                            <p className="text-[11px] text-zinc-600 mt-0.5">
                              {isExecuted ? `All ${aiOp?.executionResults?.length || 0} tools executed on live MES state.` :
                               isFailed ? aiOp?.failureReason :
                               'Applying state transitions sequentially via backend services.'}
                            </p>
                          </div>
                        </div>

                        {aiOp?.approvedBy && (
                          <span className="text-[11px] font-mono bg-white px-2.5 py-0.5 rounded border border-zinc-200 text-zinc-700">
                            Authorized: {aiOp.approvedBy}
                          </span>
                        )}
                      </div>

                      <div className="space-y-2">
                        <h4 className="text-xs font-semibold text-zinc-900 uppercase tracking-wider flex items-center gap-1.5">
                          <Terminal className="w-3.5 h-3.5 text-zinc-700" />
                          <span>Sequential Tool Execution Log</span>
                        </h4>

                        {aiOp?.executionResults && aiOp.executionResults.length > 0 ? (
                          <div className="space-y-2 font-mono text-xs">
                            {aiOp.executionResults.map((stepRes: any, i: number) => (
                              <div
                                key={i}
                                className="p-3 rounded-lg bg-zinc-50 border border-zinc-200 flex items-start justify-between gap-4"
                              >
                                <div className="flex items-start gap-2.5">
                                  <span className="text-emerald-700 font-bold">Step {stepRes.step || (i + 1)}:</span>
                                  <div>
                                    <span className="text-zinc-900 font-bold">{stepRes.tool}</span>
                                    <pre className="text-[11px] text-zinc-600 mt-1">
                                      {JSON.stringify(stepRes.parameters)}
                                    </pre>
                                  </div>
                                </div>
                                <span className="text-[10px] text-zinc-400 shrink-0">
                                  {stepRes.timestamp ? new Date(stepRes.timestamp).toLocaleTimeString() : 'Done'}
                                </span>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="p-4 rounded-lg bg-zinc-50 border border-zinc-200 text-zinc-500 text-xs text-center">
                            Awaiting execution dispatch. Click approve to run tools.
                          </div>
                        )}
                      </div>

                      <div className="flex items-center justify-end pt-4 border-t border-zinc-200">
                        <button
                          onClick={onClose}
                          className="px-4 py-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 text-white font-medium text-xs transition-colors cursor-pointer"
                        >
                          Close Window
                        </button>
                      </div>
                    </>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
