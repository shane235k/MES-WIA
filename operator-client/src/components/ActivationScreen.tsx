import React, { useState } from 'react';
import { KeyRound, ArrowRight, ShieldCheck, HardHat, AlertCircle } from 'lucide-react';
import { api } from '../services/api';

interface Props {
  onActivationRequested: (sessionToken: string, operatorEmployeeId: string, operatorName: string) => void;
}

export default function ActivationScreen({ onActivationRequested }: Props) {
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim()) return;

    setError(null);
    setLoading(true);

    try {
      const res = await api.activate(code);
      onActivationRequested(res.sessionToken, res.operatorEmployeeId, res.operatorName);
    } catch (err: any) {
      if (err?.message === 'Failed to fetch') {
        setError(`Cannot reach MES backend at ${import.meta.env.VITE_API_URL || 'http://localhost:8000'}.`);
      } else {
        setError(err.message || 'Failed to activate with this code');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-50 flex items-center justify-center p-4 select-none">
      <div className="w-full max-w-sm bg-white rounded-xl shadow-xs border border-zinc-200 p-6 space-y-5">
        
        {/* Header */}
        <div className="flex items-center gap-3 pb-3 border-b border-zinc-100">
          <div className="w-9 h-9 rounded-lg bg-zinc-900 flex items-center justify-center text-white shadow-xs">
            <HardHat className="w-4 h-4 text-zinc-100" />
          </div>
          <div>
            <h1 className="text-sm font-semibold text-zinc-900 tracking-tight">Adaptive MES</h1>
            <p className="text-[11px] text-zinc-500 font-medium">Operator Terminal</p>
          </div>
        </div>

        <div>
          <h2 className="text-sm font-medium text-zinc-900">Terminal Activation</h2>
          <p className="text-xs text-zinc-500 mt-0.5 leading-relaxed">
            Enter the activation code provided by your supervisor to connect this station.
          </p>
        </div>

        {error && (
          <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg flex items-start gap-2 text-xs text-rose-800">
            <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-zinc-700 mb-1.5">
              Activation Code
            </label>
            <div className="relative">
              <KeyRound className="w-4 h-4 text-zinc-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                required
                autoFocus
                value={code}
                onChange={(e) => setCode(e.target.value.toUpperCase())}
                placeholder="ACT-OP001-XXXXXX"
                className="w-full pl-9 pr-3 py-2 bg-zinc-50 border border-zinc-200 focus:border-zinc-900 focus:bg-white rounded-lg font-mono text-xs font-semibold tracking-wider uppercase text-zinc-900 outline-none transition-all placeholder:text-zinc-400"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading || !code.trim()}
            className="w-full h-9 px-4 bg-zinc-900 hover:bg-zinc-800 disabled:bg-zinc-200 disabled:text-zinc-400 text-white font-medium text-xs rounded-lg flex items-center justify-center gap-2 transition-all cursor-pointer shadow-xs"
          >
            {loading ? (
              <span className="inline-flex items-center gap-2">
                <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Connecting...
              </span>
            ) : (
              <>
                <span>Activate Terminal</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </>
            )}
          </button>
        </form>

        <div className="pt-2 flex items-center justify-center gap-1.5 text-[11px] text-zinc-400">
          <ShieldCheck className="w-3.5 h-3.5 text-zinc-500" />
          <span>Local Shop-Floor Security Enforced</span>
        </div>

      </div>
    </div>
  );
}
