import { useState, useEffect } from 'react';
import { 
  Plus, Edit2, Trash2, X, UserCheck, Shield, HardHat, 
  KeyRound, Check, Ban, Copy, CheckCircle2, AlertCircle, RefreshCw, ExternalLink
} from 'lucide-react';

interface User {
  id?: string;
  _id?: string;
  employeeId: string;
  name: string;
  email: string;
  role: string;
  department: string;
  status: string;
  availabilityStatus?: string;
  currentWorkOrderId?: string | null;
  currentWorkOrderCode?: string | null;
  currentWorkOrderName?: string | null;
  currentOperationId?: string | null;
}

interface UsersPageProps {
  onNavigateToExecution?: (workOrderId: string) => void;
}

interface OperatorActivation {
  id: string;
  _id?: string;
  activationCode?: string;
  operatorId: string;
  operatorEmployeeId: string;
  operatorName: string;
  status: 'NOT_ACTIVATED' | 'PENDING' | 'APPROVED' | 'REJECTED' | 'REVOKED';
  sessionToken?: string;
  createdAt: string;
  requestedAt?: string;
  approvedAt?: string;
}

export default function UsersPage({ onNavigateToExecution }: UsersPageProps = {}) {
  const [users, setUsers] = useState<User[]>([]);
  const [activations, setActivations] = useState<OperatorActivation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [activeTab, setActiveTab] = useState<'ALL' | 'OPERATORS' | 'SUPERVISORS' | 'AVAILABLE'>('ALL');

  // Generated code modal
  const [generatedCode, setGeneratedCode] = useState<string | null>(null);
  const [generatedForUser, setGeneratedForUser] = useState<User | null>(null);
  const [isCodeModalOpen, setIsCodeModalOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  // Form states
  const [employeeId, setEmployeeId] = useState('');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('OPERATOR');
  const [department, setDepartment] = useState('');
  const [status, setStatus] = useState('ACTIVE');
  const [availabilityStatus, setAvailabilityStatus] = useState('AVAILABLE');

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const fetchData = async () => {
    try {
      const [usersRes, actRes] = await Promise.all([
        fetch(`${API_URL}/api/users`),
        fetch(`${API_URL}/api/operator-activations`)
      ]);

      if (!usersRes.ok) throw new Error('Failed to fetch users');
      const usersData = await usersRes.json();
      const actsData = actRes.ok ? await actRes.json() : [];

      setUsers(usersData);
      setActivations(actsData);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, []);

  // WebSocket Live Subscription
  useEffect(() => {
    const wsUrl = API_URL.replace(/^http/, 'ws') + '/api/ws/execution';
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if ([
          'ACTIVATION_REQUESTED', 'ACTIVATION_APPROVED', 'ACTIVATION_REJECTED',
          'ACTIVATION_REVOKED', 'USER_CREATED', 'USER_UPDATED'
        ].includes(msg.type)) {
          fetchData();
        }
      } catch (err) {
        console.error('WS parse error in UsersPage:', err);
      }
    };

    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      } else if (ws.readyState === WebSocket.CONNECTING) {
        ws.onopen = () => {
          ws.close();
        };
      }
    };
  }, [API_URL]);

  const resetForm = () => {
    setEmployeeId('');
    setName('');
    setEmail('');
    setRole('OPERATOR');
    setDepartment('');
    setStatus('ACTIVE');
    setAvailabilityStatus('AVAILABLE');
    setEditingUser(null);
  };

  const handleOpenCreate = () => {
    resetForm();
    setIsModalOpen(true);
  };

  const handleOpenEdit = (user: User) => {
    setEditingUser(user);
    setEmployeeId(user.employeeId);
    setName(user.name);
    setEmail(user.email);
    setRole(user.role);
    setDepartment(user.department);
    setStatus(user.status);
    setAvailabilityStatus(user.availabilityStatus || 'AVAILABLE');
    setIsModalOpen(true);
  };

  const handleGenerateActivationCode = async (user: User) => {
    setError(null);
    try {
      const uId = (user.id || user._id) as string;
      const res = await fetch(`${API_URL}/api/operator-activations/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ operatorId: uId })
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Failed to generate activation code');
      }

      const actData: OperatorActivation = await res.json();
      setGeneratedCode(actData.activationCode || 'ACT-CODE');
      setGeneratedForUser(user);
      setCopied(false);
      setIsCodeModalOpen(true);
      fetchData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleApproveActivation = async (activationId: string) => {
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/operator-activations/${activationId}/approve`, {
        method: 'POST'
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Failed to approve activation');
      }
      fetchData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleRejectActivation = async (activationId: string) => {
    if (!window.confirm('Reject this operator client activation request?')) return;
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/operator-activations/${activationId}/reject`, {
        method: 'POST'
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Failed to reject activation');
      }
      fetchData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleRevokeActivation = async (activationId: string) => {
    if (!window.confirm('Revoke access for this operator client? The desktop client will be locked.')) return;
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/operator-activations/${activationId}/revoke`, {
        method: 'POST'
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Failed to revoke activation');
      }
      fetchData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleCopyCode = () => {
    if (!generatedCode) return;
    navigator.clipboard.writeText(generatedCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    const payload = editingUser 
      ? { name, email, role, department, status, availabilityStatus }
      : { employeeId, name, email, role, department, status, availabilityStatus };
      
    const method = editingUser ? 'PUT' : 'POST';
    const url = editingUser 
      ? `${API_URL}/api/users/${editingUser.id || editingUser._id}`
      : `${API_URL}/api/users`;

    try {
      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Operation failed');
      }

      await fetchData();
      setIsModalOpen(false);
      resetForm();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Are you sure you want to delete this user?')) return;
    try {
      const response = await fetch(`${API_URL}/api/users/${id}`, {
        method: 'DELETE',
      });
      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.detail || 'Failed to delete user');
      }
      fetchData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const getAvailabilityBadge = (user: User) => {
    if (user.role !== 'OPERATOR') return null;
    const avail = user.availabilityStatus || 'AVAILABLE';
    if (avail === 'ASSIGNED' || user.currentWorkOrderId) {
      return (
        <div className="space-y-1.5 py-0.5">
          <div className="flex items-center gap-1.5">
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200">
              <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
              ASSIGNED
            </span>
            {user.currentOperationId && (
              <span className="text-[10px] font-mono font-bold bg-zinc-100 text-zinc-700 px-1.5 py-0.5 rounded border border-zinc-200">
                {user.currentOperationId}
              </span>
            )}
          </div>
          {(user.currentWorkOrderCode || user.currentWorkOrderId) && (
            <div className="flex flex-col gap-0.5 text-xs">
              <div className="font-mono font-bold text-zinc-900 text-[11px] flex items-center gap-1">
                <span>{user.currentWorkOrderCode || `WO-${user.currentWorkOrderId?.slice(-6)}`}</span>
              </div>
              {user.currentWorkOrderName && (
                <div className="text-[11px] text-zinc-500 truncate max-w-[160px]" title={user.currentWorkOrderName}>
                  {user.currentWorkOrderName}
                </div>
              )}
            </div>
          )}
          {user.currentWorkOrderId && onNavigateToExecution && (
            <button
              onClick={() => onNavigateToExecution(user.currentWorkOrderId!)}
              className="inline-flex items-center gap-1 text-[11px] font-semibold text-indigo-600 hover:text-indigo-800 hover:underline transition-colors cursor-pointer"
            >
              <span>Jump to Execution</span>
              <ExternalLink className="w-3 h-3" />
            </button>
          )}
        </div>
      );
    }
    if (avail === 'AVAILABLE') {
      return (
        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
          AVAILABLE
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200">
        {avail}
      </span>
    );
  };

  const getActivationStatusDisplay = (user: User) => {
    if (user.role !== 'OPERATOR') return <span className="text-xs text-zinc-400">—</span>;
    const uId = (user.id || user._id) as string;
    const act = activations.find(a => a.operatorId === uId || a.operatorEmployeeId === user.employeeId);

    if (!act || act.status === 'NOT_ACTIVATED') {
      return (
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 bg-zinc-100 border border-zinc-200 text-zinc-600 rounded text-[11px] font-mono">
            NOT_ACTIVATED
          </span>
          <button
            onClick={() => handleGenerateActivationCode(user)}
            className="inline-flex items-center gap-1 px-2 py-1 bg-zinc-900 hover:bg-zinc-800 text-white rounded text-[11px] font-semibold transition-colors"
            title="Generate Client Activation Code"
          >
            <KeyRound className="w-3 h-3 text-amber-400" />
            Generate Code
          </button>
        </div>
      );
    }

    if (act.status === 'PENDING') {
      return (
        <div className="flex items-center gap-1.5">
          <span className="px-2 py-0.5 bg-amber-50 border border-amber-200 text-amber-800 rounded text-[11px] font-mono font-bold animate-pulse">
            PENDING APPROVAL
          </span>
          <button
            onClick={() => handleApproveActivation(act.id || (act._id as string))}
            className="inline-flex items-center gap-1 px-2 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-[11px] font-semibold shadow-2xs"
            title="Approve Operator Client"
          >
            <Check className="w-3 h-3" />
            Approve
          </button>
          <button
            onClick={() => handleRejectActivation(act.id || (act._id as string))}
            className="p-1 bg-rose-50 hover:bg-rose-100 text-rose-700 border border-rose-200 rounded text-[11px]"
            title="Reject Request"
          >
            <Ban className="w-3 h-3" />
          </button>
        </div>
      );
    }

    if (act.status === 'APPROVED') {
      return (
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded text-[11px] font-mono font-bold">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            APPROVED
          </span>
          <button
            onClick={() => handleRevokeActivation(act.id || (act._id as string))}
            className="px-2 py-0.5 text-zinc-500 hover:text-rose-600 hover:bg-rose-50 border border-zinc-200 rounded text-[10px] font-medium transition-colors"
            title="Revoke desktop client session"
          >
            Revoke
          </button>
        </div>
      );
    }

    if (act.status === 'REJECTED' || act.status === 'REVOKED') {
      return (
        <div className="flex items-center gap-2">
          <span className="px-2 py-0.5 bg-zinc-100 border border-zinc-200 text-zinc-500 rounded text-[11px] font-mono">
            {act.status}
          </span>
          <button
            onClick={() => handleGenerateActivationCode(user)}
            className="inline-flex items-center gap-1 px-2 py-0.5 text-[11px] font-semibold text-zinc-700 hover:text-zinc-900 bg-zinc-100 hover:bg-zinc-200 border rounded"
          >
            <RefreshCw className="w-2.5 h-2.5" />
            New Code
          </button>
        </div>
      );
    }

    return <span className="text-xs text-zinc-400">—</span>;
  };

  const filteredUsers = users.filter(u => {
    if (activeTab === 'OPERATORS') return u.role === 'OPERATOR';
    if (activeTab === 'SUPERVISORS') return u.role === 'SUPERVISOR' || u.role === 'ADMIN';
    if (activeTab === 'AVAILABLE') return u.role === 'OPERATOR' && (u.availabilityStatus === 'AVAILABLE' || !u.availabilityStatus);
    return true;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-zinc-900">Personnel & Operators</h1>
          <p className="text-sm text-zinc-500">
            Manage certified operators, plant supervisors, and desktop client activation approvals.
          </p>
        </div>
        <button
          onClick={handleOpenCreate}
          className="inline-flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium text-white bg-zinc-900 rounded-lg hover:bg-zinc-800 transition-colors shadow-sm"
        >
          <Plus className="w-4 h-4" />
          Add Personnel
        </button>
      </div>

      {error && (
        <div className="p-4 bg-rose-50 border border-rose-200 rounded-lg text-sm text-rose-700 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600" />
            <span>{error}</span>
          </div>
          <button onClick={() => setError(null)} className="text-rose-500 hover:text-rose-700">✕</button>
        </div>
      )}

      {/* Filter Tabs */}
      <div className="flex gap-2 border-b border-zinc-200 pb-2">
        <button
          onClick={() => setActiveTab('ALL')}
          className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
            activeTab === 'ALL' ? 'bg-zinc-900 text-white' : 'text-zinc-600 hover:bg-zinc-100'
          }`}
        >
          All Users ({users.length})
        </button>
        <button
          onClick={() => setActiveTab('OPERATORS')}
          className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
            activeTab === 'OPERATORS' ? 'bg-zinc-900 text-white' : 'text-zinc-600 hover:bg-zinc-100'
          }`}
        >
          Operators ({users.filter(u => u.role === 'OPERATOR').length})
        </button>
        <button
          onClick={() => setActiveTab('SUPERVISORS')}
          className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
            activeTab === 'SUPERVISORS' ? 'bg-zinc-900 text-white' : 'text-zinc-600 hover:bg-zinc-100'
          }`}
        >
          Supervisors ({users.filter(u => u.role === 'SUPERVISOR' || u.role === 'ADMIN').length})
        </button>
        <button
          onClick={() => setActiveTab('AVAILABLE')}
          className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
            activeTab === 'AVAILABLE' ? 'bg-emerald-600 text-white' : 'text-emerald-700 hover:bg-emerald-50'
          }`}
        >
          Available Now ({users.filter(u => u.role === 'OPERATOR' && (u.availabilityStatus === 'AVAILABLE' || !u.availabilityStatus)).length})
        </button>
      </div>

      {/* Table */}
      <div className="bg-white border border-zinc-200 rounded-xl overflow-hidden shadow-xs">
        <table className="w-full text-left text-sm text-zinc-600">
          <thead className="bg-zinc-50 border-b border-zinc-200 text-xs font-semibold text-zinc-900 uppercase">
            <tr>
              <th className="px-6 py-3.5">Employee</th>
              <th className="px-6 py-3.5">Role</th>
              <th className="px-6 py-3.5">Department</th>
              <th className="px-6 py-3.5">Live Availability</th>
              <th className="px-6 py-3.5">Tauri Client Status</th>
              <th className="px-6 py-3.5 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-200">
            {loading ? (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-zinc-500">
                  Loading personnel records...
                </td>
              </tr>
            ) : filteredUsers.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-6 py-8 text-center text-zinc-500">
                  No personnel matching this filter.
                </td>
              </tr>
            ) : (
              filteredUsers.map((user) => {
                const userId = (user.id || user._id) as string;
                return (
                  <tr key={userId} className="hover:bg-zinc-50/50 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-zinc-100 border border-zinc-200 flex items-center justify-center font-bold text-zinc-700 text-xs">
                          {user.name.split(' ').map(n => n[0]).join('')}
                        </div>
                        <div>
                          <div className="font-semibold text-zinc-900">{user.name}</div>
                          <div className="text-xs text-zinc-400 font-mono">{user.employeeId} • {user.email}</div>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold bg-zinc-100 text-zinc-800 border border-zinc-200/60">
                        {user.role === 'OPERATOR' && <HardHat className="w-3 h-3 text-amber-600" />}
                        {user.role === 'SUPERVISOR' && <Shield className="w-3 h-3 text-indigo-600" />}
                        {user.role === 'ADMIN' && <UserCheck className="w-3 h-3 text-emerald-600" />}
                        {user.role}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-zinc-600">{user.department}</td>
                    <td className="px-6 py-4">
                      {getAvailabilityBadge(user) || <span className="text-xs text-zinc-400">—</span>}
                    </td>
                    <td className="px-6 py-4">
                      {getActivationStatusDisplay(user)}
                    </td>
                    <td className="px-6 py-4 text-right space-x-2">
                      <button
                        onClick={() => handleOpenEdit(user)}
                        className="p-1 text-zinc-400 hover:text-zinc-700 transition-colors"
                        title="Edit User"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(userId)}
                        className="p-1 text-rose-400 hover:text-rose-600 transition-colors"
                        title="Delete User"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* Modal: Display Generated Activation Code */}
      {isCodeModalOpen && generatedForUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden border border-zinc-200">
            <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200 bg-zinc-50/50">
              <div className="flex items-center gap-2">
                <div className="p-1.5 bg-amber-500/10 text-amber-600 rounded-lg">
                  <KeyRound className="w-4 h-4" />
                </div>
                <h2 className="text-base font-bold text-zinc-900">Operator Activation Code</h2>
              </div>
              <button
                onClick={() => setIsCodeModalOpen(false)}
                className="p-1 rounded-md text-zinc-400 hover:text-zinc-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <p className="text-xs text-zinc-600">
                A single-use activation code has been generated for <strong>{generatedForUser.name} ({generatedForUser.employeeId})</strong>. Provide this code to the operator to enter into the desktop Operator Client.
              </p>

              <div className="p-4 bg-zinc-900 rounded-xl flex items-center justify-between text-white font-mono tracking-widest text-lg font-bold">
                <span>{generatedCode}</span>
                <button
                  onClick={handleCopyCode}
                  className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-xs font-sans rounded-lg flex items-center gap-1.5 transition-colors border border-zinc-700"
                >
                  {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                  {copied ? 'Copied' : 'Copy'}
                </button>
              </div>

              <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-[11px] text-amber-800 space-y-1">
                <strong>Next Steps:</strong>
                <ol className="list-decimal list-inside space-y-0.5 text-amber-700">
                  <li>Operator launches the Operator Client app.</li>
                  <li>Operator types this activation code and submits.</li>
                  <li>Approve the request here on the Admin dashboard.</li>
                </ol>
              </div>

              <div className="flex justify-end pt-2">
                <button
                  type="button"
                  onClick={() => setIsCodeModalOpen(false)}
                  className="px-4 py-2 bg-zinc-900 text-white text-xs font-semibold rounded-lg hover:bg-zinc-800"
                >
                  Done
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Create/Edit User */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xs p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md overflow-hidden border border-zinc-200">
            <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-200 bg-zinc-50/50">
              <h2 className="text-base font-semibold text-zinc-900">
                {editingUser ? 'Edit Personnel' : 'Add New Personnel'}
              </h2>
              <button
                onClick={() => setIsModalOpen(false)}
                className="p-1 rounded-md text-zinc-400 hover:text-zinc-600 hover:bg-zinc-100 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Employee ID <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  disabled={!!editingUser}
                  value={employeeId}
                  onChange={(e) => setEmployeeId(e.target.value.toUpperCase())}
                  placeholder="OP-001"
                  className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-sm uppercase font-mono disabled:bg-zinc-100"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Full Name <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Alex Rivera"
                  className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-zinc-700 mb-1">
                  Email Address <span className="text-rose-500">*</span>
                </label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="alex.rivera@factory.com"
                  className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-sm"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">Role</label>
                  <select
                    value={role}
                    onChange={(e) => setRole(e.target.value)}
                    className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-sm bg-white"
                  >
                    <option value="OPERATOR">OPERATOR</option>
                    <option value="SUPERVISOR">SUPERVISOR</option>
                    <option value="ADMIN">ADMIN</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">Department</label>
                  <input
                    type="text"
                    required
                    value={department}
                    onChange={(e) => setDepartment(e.target.value)}
                    placeholder="Assembly Line"
                    className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-sm"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-zinc-700 mb-1">Account Status</label>
                  <select
                    value={status}
                    onChange={(e) => setStatus(e.target.value)}
                    className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-sm bg-white"
                  >
                    <option value="ACTIVE">ACTIVE</option>
                    <option value="INACTIVE">INACTIVE</option>
                  </select>
                </div>

                {role === 'OPERATOR' && (
                  <div>
                    <label className="block text-xs font-semibold text-zinc-700 mb-1">Availability</label>
                    <select
                      value={availabilityStatus}
                      onChange={(e) => setAvailabilityStatus(e.target.value)}
                      className="w-full px-3 py-2 border border-zinc-300 rounded-lg text-sm bg-white font-semibold"
                    >
                      <option value="AVAILABLE">AVAILABLE</option>
                      <option value="ASSIGNED">ASSIGNED</option>
                      <option value="UNAVAILABLE">UNAVAILABLE</option>
                    </select>
                  </div>
                )}
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-zinc-100">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 border border-zinc-200 text-sm font-medium rounded-lg text-zinc-700 hover:bg-zinc-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-zinc-900 text-sm font-medium rounded-lg text-white hover:bg-zinc-800 shadow-sm"
                >
                  {editingUser ? 'Save Changes' : 'Create User'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
