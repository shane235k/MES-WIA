import React, { useState } from 'react';
import { X, AlertTriangle, Send, CheckCircle2, ShieldAlert, Cpu } from 'lucide-react';
import { api } from '../services/api';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  sessionToken: string;
  currentMachineCode?: string;
  currentMachineId?: string;
  onReportSubmitted: () => void;
}

export default function ReportProblemModal({
  isOpen,
  onClose,
  sessionToken,
  currentMachineCode,
  currentMachineId,
  onReportSubmitted
}: Props) {
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSuccess, setIsSuccess] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim()) return;

    setError(null);
    setLoading(true);

    try {
      await api.reportProblem(sessionToken, message, currentMachineId || currentMachineCode);
      setIsSuccess(true);
      onReportSubmitted();
    } catch (err: any) {
      setError(err.message || 'Failed to submit problem report');
    } finally {
      setLoading(false);
    }
  };

  const handleResetAndClose = () => {
    setMessage('');
    setIsSuccess(false);
    setError(null);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4 select-none animate-fade-in">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md overflow-hidden border border-zinc-200">
        
        {/* Modal Header */}
        <div className="px-5 py-4 border-b border-zinc-100 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-rose-50 border border-rose-200 text-rose-700 flex items-center justify-center">
              <AlertTriangle className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-zinc-900">Report Problem</h2>
              <p className="text-[11px] text-zinc-500 font-normal">Transmit incident alert to supervisor</p>
            </div>
          </div>
          <button
            onClick={handleResetAndClose}
            className="p-1 rounded-md text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {isSuccess ? (
          <div className="p-6 text-center space-y-4">
            <div className="mx-auto w-12 h-12 rounded-lg bg-emerald-50 border border-emerald-200 flex items-center justify-center">
              <CheckCircle2 className="w-6 h-6 text-emerald-600" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-zinc-900">Report Submitted</h3>
              <p className="text-xs text-zinc-500 mt-1 max-w-xs mx-auto leading-relaxed">
                Waiting for administrator review. The station status remains active until reviewed.
              </p>
            </div>
            <div className="p-3 bg-zinc-50 rounded-lg border border-zinc-200 text-left text-xs font-mono space-y-1">
              <div className="flex justify-between">
                <span className="text-zinc-500">Target Machine:</span>
                <span className="font-semibold text-zinc-900">{currentMachineCode || 'General Station'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">Status:</span>
                <span className="font-semibold text-amber-700">PENDING_REVIEW</span>
              </div>
            </div>
            <button
              type="button"
              onClick={handleResetAndClose}
              className="w-full h-9 bg-zinc-900 hover:bg-zinc-800 text-white text-xs font-medium rounded-lg transition-colors cursor-pointer"
            >
              Return to Terminal
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="p-5 space-y-4">
            {error && (
              <div className="p-2.5 bg-rose-50 border border-rose-200 rounded-lg text-xs text-rose-800 flex items-center gap-2">
                <ShieldAlert className="w-4 h-4 text-rose-600 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            {/* Target Machine Selection */}
            <div>
              <label className="block text-xs font-medium text-zinc-700 mb-1">
                Target Workstation Machine
              </label>
              <div className="p-2.5 bg-zinc-50 border border-zinc-200 rounded-lg flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <Cpu className="w-4 h-4 text-zinc-500" />
                  <span className="font-mono font-semibold text-zinc-900">
                    {currentMachineCode || 'General Workstation'}
                  </span>
                </div>
                <span className="text-[10px] font-mono font-medium px-2 py-0.5 bg-white border border-zinc-200 rounded text-zinc-500 uppercase">
                  Assigned
                </span>
              </div>
            </div>

            {/* Free-form text input */}
            <div>
              <label className="block text-xs font-medium text-zinc-700 mb-1">
                Observation / Problem Description <span className="text-rose-500">*</span>
              </label>
              <textarea
                required
                rows={3}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Describe issue (e.g. machine overheating, feed jam, hydraulic pressure drop)..."
                className="w-full p-2.5 bg-zinc-50 border border-zinc-200 focus:border-zinc-900 focus:bg-white rounded-lg text-xs text-zinc-900 outline-none transition-all placeholder:text-zinc-400 resize-none leading-relaxed"
              />
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-2.5 pt-1">
              <button
                type="button"
                onClick={handleResetAndClose}
                className="w-1/3 h-9 border border-zinc-200 hover:bg-zinc-50 text-zinc-700 text-xs font-medium rounded-lg transition-colors cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading || !message.trim()}
                className="w-2/3 h-9 bg-rose-600 hover:bg-rose-700 disabled:bg-zinc-200 disabled:text-zinc-400 text-white text-xs font-medium rounded-lg flex items-center justify-center gap-1.5 transition-all cursor-pointer shadow-xs"
              >
                {loading ? (
                  <span>Submitting...</span>
                ) : (
                  <>
                    <Send className="w-3.5 h-3.5" />
                    <span>Submit Report</span>
                  </>
                )}
              </button>
            </div>
          </form>
        )}

      </div>
    </div>
  );
}
