import { useState, useEffect } from 'react';
import { 
  HardHat, AlertTriangle, Cpu, Clock, 
  LogOut, RefreshCw, Activity, ArrowUpRight
} from 'lucide-react';
import { OperatorContext, OperatorReport } from '../types/operator';
import { api } from '../services/api';
import ReportProblemModal from './ReportProblemModal';
import MyReportsDrawer from './MyReportsDrawer';

interface Props {
  sessionToken: string;
  onLogout: () => void;
}

export default function OperatorDashboard({ sessionToken, onLogout }: Props) {
  const [context, setContext] = useState<OperatorContext | null>(null);
  const [reports, setReports] = useState<OperatorReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [reportsLoading, setReportsLoading] = useState(true);
  const [isReportModalOpen, setIsReportModalOpen] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState<string>('');

  const fetchAllData = async () => {
    try {
      const [ctxData, reportsData] = await Promise.all([
        api.getContext(sessionToken),
        api.getMyReports(sessionToken)
      ]);
      setContext(ctxData);
      setReports(reportsData);
      setLastRefreshed(new Date().toLocaleTimeString());
    } catch (err: any) {
      console.error('Context fetch error:', err);
    } finally {
      setLoading(false);
      setReportsLoading(false);
    }
  };

  useEffect(() => {
    fetchAllData();
    const interval = setInterval(fetchAllData, 2500);
    return () => clearInterval(interval);
  }, [sessionToken]);

  // Real-time WebSocket updates
  useEffect(() => {
    const cleanup = api.connectWebSocket((event) => {
      if ([
        'INCIDENT_CREATED', 'INCIDENT_CONFIRMED', 'INCIDENT_DISMISSED',
        'INCIDENT_RESOLVED', 'MACHINE_FAILED', 'MACHINE_RECOVERED',
        'EXECUTION_STATE_UPDATE', 'WORK_ORDER_STARTED', 'WORK_ORDER_COMPLETED'
      ].includes(event.type)) {
        fetchAllData();
      }
    });

    return cleanup;
  }, [sessionToken]);

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 17) return 'Good afternoon';
    return 'Good evening';
  };

  const assignment = context?.assignment;
  const operator = context?.operator;

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'IN_PROGRESS':
      case 'OCCUPIED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-md text-xs font-semibold font-mono">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            IN PROGRESS
          </span>
        );
      case 'WAITING_FOR_RESOURCE':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 bg-amber-50 border border-amber-200 text-amber-900 rounded-md text-xs font-semibold font-mono">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-ping" />
            WAITING RESOURCE
          </span>
        );
      case 'INTERRUPTED':
      case 'DOWN':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 bg-rose-50 border border-rose-200 text-rose-800 rounded-md text-xs font-semibold font-mono">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
            INTERRUPTED
          </span>
        );
      case 'READY':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 bg-blue-50 border border-blue-200 text-blue-800 rounded-md text-xs font-semibold font-mono">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
            READY
          </span>
        );
      case 'PAUSED':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 bg-purple-50 border border-purple-200 text-purple-800 rounded-md text-xs font-semibold font-mono">
            PAUSED
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 bg-zinc-100 border border-zinc-200 text-zinc-700 rounded-md text-xs font-mono font-medium">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="min-h-screen bg-zinc-50 flex flex-col justify-between p-4 md:p-6 select-none max-w-3xl mx-auto space-y-4">
      
      {/* Top Header */}
      <header className="bg-white rounded-xl p-4 shadow-xs border border-zinc-200 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-zinc-900 flex items-center justify-center text-white shadow-xs">
            <HardHat className="w-4 h-4 text-zinc-100" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-semibold text-zinc-900 tracking-tight">
                {getGreeting()}, {operator?.name || 'Operator'}
              </h1>
              <span className="px-2 py-0.5 rounded text-[11px] font-mono font-semibold bg-zinc-100 text-zinc-800 border border-zinc-200">
                {operator?.operatorId || 'OP-001'}
              </span>
            </div>
            <p className="text-xs text-zinc-500 font-normal">
              {operator?.department || 'Production'} • Operator Terminal
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={fetchAllData}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 transition-colors"
            title="Refresh Telemetry"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={onLogout}
            className="inline-flex items-center gap-1 px-2.5 py-1.5 bg-zinc-100 hover:bg-rose-50 text-zinc-600 hover:text-rose-600 rounded-lg text-xs font-medium transition-colors cursor-pointer"
            title="Lock Terminal"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span>Lock</span>
          </button>
        </div>
      </header>

      {/* Main Panel */}
      <main className="space-y-4">
        
        {/* Workstation Assignment Card */}
        <section className="bg-white rounded-xl border border-zinc-200 p-5 shadow-xs space-y-3.5">
          <div className="flex items-center justify-between border-b border-zinc-100 pb-2.5">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-zinc-500" />
              <h2 className="text-xs font-semibold text-zinc-900 uppercase tracking-wider">
                Workstation Assignment
              </h2>
            </div>
            {assignment ? (
              getStatusBadge(assignment.status)
            ) : (
              <span className="px-2.5 py-0.5 bg-zinc-100 border border-zinc-200 text-zinc-500 rounded-md text-xs font-medium font-mono">
                STANDBY
              </span>
            )}
          </div>

          {loading ? (
            <div className="py-8 text-center text-zinc-400 text-xs font-mono">
              Loading workstation telemetry...
            </div>
          ) : assignment ? (
            <div className="space-y-3">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {/* Machine Box */}
                <div className="p-3.5 bg-zinc-50 rounded-lg border border-zinc-200 space-y-1.5">
                  <span className="text-[11px] font-medium text-zinc-500 uppercase tracking-wider block">
                    Assigned Machine
                  </span>
                  <div className="flex items-baseline gap-2">
                    <span className="text-xl font-bold font-mono text-zinc-900">
                      {assignment.machineCode}
                    </span>
                    <span className="text-xs font-semibold text-zinc-700">
                      {assignment.machineName}
                    </span>
                  </div>
                  <div className="pt-0.5">
                    <span className="px-2 py-0.5 bg-white border border-zinc-200 rounded text-[10px] font-mono font-medium text-zinc-600 uppercase">
                      Type: {assignment.machineType}
                    </span>
                  </div>
                </div>

                {/* Operation & Work Order Box */}
                <div className="p-3.5 bg-zinc-50 rounded-lg border border-zinc-200 space-y-1.5">
                  <span className="text-[11px] font-medium text-zinc-500 uppercase tracking-wider block">
                    Active Operation & Work Order
                  </span>
                  <div className="flex items-baseline gap-2">
                    <span className="text-lg font-bold font-mono text-zinc-900">
                      {assignment.operationId}
                    </span>
                    <span className="text-xs font-semibold text-zinc-700">
                      {assignment.operationName}
                    </span>
                  </div>
                  <div className="flex items-center justify-between pt-0.5 text-xs">
                    <span className="font-mono text-zinc-600 text-[11px]">
                      WO: <strong className="text-zinc-900">{assignment.workOrderCode}</strong>
                    </span>
                    {assignment.remainingSeconds !== undefined && assignment.remainingSeconds > 0 && (
                      <span className="font-mono text-indigo-700 font-medium flex items-center gap-1 text-[11px]">
                        <Clock className="w-3 h-3" />
                        ~{assignment.remainingSeconds}s
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Waiting Notice */}
              {assignment.waitingReason && (
                <div className="p-2.5 bg-amber-50 border border-amber-200 rounded-lg flex items-start gap-2 text-xs text-amber-900">
                  <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <strong className="font-medium block">Notice:</strong>
                    <span>{assignment.waitingReason}</span>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="py-8 text-center space-y-1.5 bg-zinc-50 rounded-lg border border-dashed border-zinc-200">
              <Cpu className="w-6 h-6 text-zinc-400 mx-auto" />
              <p className="text-xs font-semibold text-zinc-800">Station Idle / Unassigned</p>
              <p className="text-[11px] text-zinc-500 max-w-sm mx-auto">
                No active operation is allocated. Work order routing will assign your terminal upon dispatch.
              </p>
            </div>
          )}
        </section>

        {/* PRIMARY ACTION: REPORT A PROBLEM */}
        <section className="bg-white border border-zinc-200 rounded-xl p-4 shadow-xs flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="space-y-0.5 text-center sm:text-left">
            <h3 className="text-xs font-semibold text-zinc-900 flex items-center gap-1.5 justify-center sm:justify-start">
              <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
              Machine Issue or Quality Concern?
            </h3>
            <p className="text-[11px] text-zinc-500">
              Notify the shift supervisor immediately. Creates a high-priority incident for review.
            </p>
          </div>

          <button
            onClick={() => setIsReportModalOpen(true)}
            className="w-full sm:w-auto px-4 py-2 bg-rose-600 hover:bg-rose-700 active:scale-98 text-white font-medium text-xs rounded-lg shadow-xs flex items-center justify-center gap-1.5 transition-all cursor-pointer flex-shrink-0"
          >
            <span>Report Problem</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </button>
        </section>

        {/* My Reports Live Status Stream */}
        <MyReportsDrawer reports={reports} loading={reportsLoading} />

      </main>

      {/* Footer */}
      <footer className="flex items-center justify-between text-[11px] text-zinc-400 font-mono pt-1">
        <span>Adaptive MES • Operator Terminal</span>
        <span>Last Synced: {lastRefreshed || 'Connecting...'}</span>
      </footer>

      {/* Report Modal */}
      <ReportProblemModal
        isOpen={isReportModalOpen}
        onClose={() => setIsReportModalOpen(false)}
        sessionToken={sessionToken}
        currentMachineCode={assignment?.machineCode || 'M-03'}
        currentMachineId={assignment?.machineId}
        onReportSubmitted={fetchAllData}
      />

    </div>
  );
}
