import { useState, useEffect } from 'react';
import ActivationScreen from './components/ActivationScreen';
import PendingApprovalScreen from './components/PendingApprovalScreen';
import OperatorDashboard from './components/OperatorDashboard';
import { api } from './services/api';

export default function App() {
  const [sessionToken, setSessionToken] = useState<string | null>(() => localStorage.getItem('mes_operator_session'));
  const [operatorEmployeeId, setOperatorEmployeeId] = useState<string>(() => localStorage.getItem('mes_operator_emp_id') || '');
  const [operatorName, setOperatorName] = useState<string>(() => localStorage.getItem('mes_operator_name') || '');
  const [approvalStatus, setApprovalStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const verifySession = async () => {
      if (!sessionToken) {
        setLoading(false);
        return;
      }

      try {
        const res = await api.checkStatus(sessionToken);
        setApprovalStatus(res.status);
        if (res.operatorEmployeeId) setOperatorEmployeeId(res.operatorEmployeeId);
        if (res.operatorName) setOperatorName(res.operatorName);
      } catch (err: any) {
        // If backend is restarting or offline, do not clear local storage
        if (err?.message === 'Failed to fetch') {
          console.warn("Could not reach backend to verify session. Retaining offline session.");
          setApprovalStatus('PENDING');
        } else {
          localStorage.removeItem('mes_operator_session');
          setSessionToken(null);
          setApprovalStatus(null);
        }
      } finally {
        setLoading(false);
      }
    };

    verifySession();
  }, [sessionToken]);

  const handleActivationRequested = (token: string, empId: string, name: string) => {
    localStorage.setItem('mes_operator_session', token);
    localStorage.setItem('mes_operator_emp_id', empId);
    localStorage.setItem('mes_operator_name', name);
    setSessionToken(token);
    setOperatorEmployeeId(empId);
    setOperatorName(name);
    setApprovalStatus('PENDING');
  };

  const handleApproved = () => {
    setApprovalStatus('APPROVED');
  };

  const handleResetSession = () => {
    localStorage.removeItem('mes_operator_session');
    localStorage.removeItem('mes_operator_emp_id');
    localStorage.removeItem('mes_operator_name');
    setSessionToken(null);
    setOperatorEmployeeId('');
    setOperatorName('');
    setApprovalStatus(null);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-100 flex items-center justify-center">
        <div className="flex items-center gap-3 text-zinc-500 font-mono text-xs">
          <span className="w-4 h-4 border-2 border-zinc-400 border-t-zinc-900 rounded-full animate-spin" />
          <span>Connecting to factory MES backend...</span>
        </div>
      </div>
    );
  }

  // 1. Not activated -> Show Activation Code Entry
  if (!sessionToken || !approvalStatus || approvalStatus === 'NOT_ACTIVATED') {
    return <ActivationScreen onActivationRequested={handleActivationRequested} />;
  }

  // 2. Pending Admin Approval -> Show Pending Screen
  if (approvalStatus === 'PENDING' || approvalStatus === 'REJECTED') {
    return (
      <PendingApprovalScreen
        sessionToken={sessionToken}
        operatorEmployeeId={operatorEmployeeId}
        operatorName={operatorName}
        onApproved={handleApproved}
        onReset={handleResetSession}
      />
    );
  }

  // 3. Approved -> Show Operator Dashboard
  return (
    <OperatorDashboard
      sessionToken={sessionToken}
      onLogout={handleResetSession}
    />
  );
}
