import { AlertTriangle, CheckCircle2, XCircle, Clock, ShieldCheck } from 'lucide-react';
import { OperatorReport } from '../types/operator';

interface Props {
  reports: OperatorReport[];
  loading: boolean;
}

export default function MyReportsDrawer({ reports, loading }: Props) {
  const getStatusBadge = (report: OperatorReport) => {
    switch (report.status) {
      case 'PENDING_REVIEW':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-amber-50 border border-amber-200 text-amber-900 rounded-md text-[10px] font-medium">
            <Clock className="w-3 h-3 text-amber-600 animate-pulse" />
            Pending Review
          </span>
        );
      case 'ACTION_REQUIRED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-rose-50 border border-rose-200 text-rose-800 rounded-md text-[10px] font-medium">
            <AlertTriangle className="w-3 h-3 text-rose-600" />
            Confirmed (DOWN)
          </span>
        );
      case 'DISMISSED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-zinc-100 border border-zinc-200 text-zinc-600 rounded-md text-[10px] font-medium">
            <XCircle className="w-3 h-3 text-zinc-500" />
            Dismissed
          </span>
        );
      case 'RESOLVED':
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-md text-[10px] font-medium">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            Resolved
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 bg-zinc-100 text-zinc-700 rounded text-[10px] font-mono">
            {report.status}
          </span>
        );
    }
  };

  return (
    <div className="bg-white rounded-xl border border-zinc-200 p-5 space-y-3 shadow-xs">
      <div className="flex items-center justify-between border-b border-zinc-100 pb-2.5">
        <div className="flex items-center gap-2">
          <ShieldCheck className="w-4 h-4 text-zinc-500" />
          <h3 className="text-xs font-semibold text-zinc-900 uppercase tracking-wider">
            Shift Reports ({reports.length})
          </h3>
        </div>
        <span className="text-[11px] font-medium text-zinc-400">Live Status Feed</span>
      </div>

      {loading ? (
        <div className="py-6 text-center text-zinc-400 text-xs">
          Loading report history...
        </div>
      ) : reports.length === 0 ? (
        <div className="py-6 text-center text-zinc-400 text-xs italic">
          No incident reports submitted for this shift.
        </div>
      ) : (
        <div className="space-y-2.5 max-h-60 overflow-y-auto pr-1">
          {reports.map((r) => (
            <div
              key={r.id}
              className="p-3 bg-zinc-50 rounded-lg border border-zinc-200 space-y-1.5"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="px-1.5 py-0.5 bg-white border border-zinc-200 rounded font-mono font-semibold text-[11px] text-zinc-900">
                    {r.incidentCode}
                  </span>
                  {r.machineCode && (
                    <span className="text-[11px] font-mono text-zinc-600">
                      Station: <strong className="text-zinc-900">{r.machineCode}</strong>
                    </span>
                  )}
                </div>
                {getStatusBadge(r)}
              </div>

              <p className="text-xs text-zinc-700 font-normal leading-relaxed">
                {r.description || r.title}
              </p>

              {r.status === 'DISMISSED' && r.dismissalReason && (
                <div className="p-2 bg-zinc-100 border border-zinc-200 rounded-md text-[11px] text-zinc-600">
                  <strong className="text-zinc-800">Admin Note:</strong> {r.dismissalReason}
                </div>
              )}

              {r.status === 'RESOLVED' && r.resolution && (
                <div className="p-2 bg-emerald-50 border border-emerald-200 rounded-md text-[11px] text-emerald-800">
                  <strong className="text-emerald-900">Resolution:</strong> {r.resolution}
                </div>
              )}

              <div className="text-[10px] font-mono text-zinc-400 text-right pt-0.5">
                {new Date(r.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
