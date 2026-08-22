import { useEffect, useState } from 'react';
import { Clock, ShieldAlert, RotateCcw, User, RefreshCw } from 'lucide-react';
import { api } from '../services/api';

interface Props {
  sessionToken: string;
  operatorEmployeeId: string;
  operatorName: string;
  onApproved: () => void;
  onReset: () => void;
}

export default function PendingApprovalScreen({
  sessionToken,
  operatorEmployeeId,
  operatorName,
  onApproved,
  onReset
}: Props) {
  const [status, setStatus] = useState('PENDING');
  const [lastChecked, setLastChecked] = useState('');

  const checkStatus = async () => {
    try {
      const res = await api.checkStatus(sessionToken);
      setStatus(res.status);
      setLastChecked(new Date().toLocaleTimeString());
      if (res.status === 'APPROVED') {
        onApproved();
      }
    } catch (err) {
      console.warn('Status check warning:', err);
    }
  };

  useEffect(() => {
    checkStatus();
    const interval = setInterval(checkStatus, 2000);
    return () => clearInterval(interval);
  }, [sessionToken]);

  // Real-time WebSocket trigger
  useEffect(() => {
    const cleanup = api.connectWebSocket((event) => {
      if (event.type === 'ACTIVATION_APPROVED') {
        if (event.data?.sessionToken === sessionToken || event.data?.operatorEmployeeId === operatorEmployeeId) {
          onApproved();
        }
      } else if (event.type === 'ACTIVATION_REJECTED' || event.type === 'ACTIVATION_REVOKED') {
        checkStatus();
      }
    });

    return cleanup;
  }, [sessionToken, operatorEmployeeId]);

  return (
    <div className="min-h-screen bg-zinc-50 flex items-center justify-center p-4 select-none">
      <div className="w-full max-w-sm bg-white rounded-xl shadow-xs border border-zinc-200 p-6 space-y-4 text-center">
        
        {/* Status Icon */}
        <div className="mx-auto w-12 h-12 rounded-lg bg-amber-50 border border-amber-200 flex items-center justify-center">
          <Clock className="w-6 h-6 text-amber-600 animate-pulse" />
        </div>

        <div>
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 bg-amber-50 border border-amber-200 text-amber-900 rounded-md text-[11px] font-mono font-medium uppercase tracking-wider mb-1.5">
            Status: {status}
          </span>
          <h1 className="text-sm font-semibold text-zinc-900">
            Awaiting Approval
          </h1>
          <p className="text-xs text-zinc-500 mt-1 max-w-xs mx-auto leading-relaxed">
            Your activation request is pending administrator confirmation.
          </p>
        </div>

        {/* Operator Info */}
        <div className="p-3 bg-zinc-50 rounded-lg border border-zinc-200 text-left space-y-1.5 text-xs">
          <div className="flex items-center justify-between">
            <span className="text-zinc-500">Operator:</span>
            <span className="font-medium text-zinc-900 flex items-center gap-1">
              <User className="w-3 h-3 text-zinc-500" />
              {operatorName}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-zinc-500">Employee ID:</span>
            <span className="font-mono font-semibold text-zinc-900">{operatorEmployeeId}</span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-zinc-500">Last Synced:</span>
            <span className="font-mono text-zinc-400 text-[11px]">{lastChecked || 'Just now'}</span>
          </div>
        </div>

        {status === 'REJECTED' && (
          <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-800 flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-rose-600 flex-shrink-0" />
            <span>Administrator rejected this activation request.</span>
          </div>
        )}

        <div className="pt-1 flex flex-col gap-2">
          <button
            onClick={checkStatus}
            className="w-full h-9 bg-zinc-900 hover:bg-zinc-800 text-white font-medium text-xs rounded-lg flex items-center justify-center gap-1.5 transition-colors cursor-pointer shadow-xs"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Check Status</span>
          </button>
          <button
            onClick={onReset}
            className="w-full h-8 text-zinc-500 hover:text-zinc-900 text-xs font-medium rounded-lg flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Use Different Code</span>
          </button>
        </div>

      </div>
    </div>
  );
}
