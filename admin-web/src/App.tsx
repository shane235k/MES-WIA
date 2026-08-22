import { useState, useEffect } from 'react';
import { 
  Layers, 
  Activity, 
  Settings as SettingsIcon, 
  Cpu, 
  Briefcase, 
  ClipboardList,
  User as UserIcon,
  AlertTriangle,
  Menu,
  X
} from 'lucide-react';

import Dashboard from './components/Dashboard';
import UsersPage from './pages/UsersPage';
import CapabilitiesPage from './pages/CapabilitiesPage';
import MachinesPage from './pages/MachinesPage';
import ProductsPage from './pages/ProductsPage';
import MaterialsPage from './pages/MaterialsPage';
import WorkflowsPage from './pages/WorkflowsPage';
import WorkflowDesignerPage from './pages/WorkflowDesignerPage';
import WorkOrdersPage from './pages/WorkOrdersPage';
import IncidentsPage from './pages/IncidentsPage';
import AuditLogsPage from './pages/AuditLogsPage';
import SettingsPage from './pages/SettingsPage';

interface ServiceStatus {
  status: string;
}

interface HealthResponse {
  status: string;
  api: { status: string };
  database: ServiceStatus;
  redis: ServiceStatus;
}

export default function App() {
  const [activeTab, setActiveTab] = useState('Overview');
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [systemStatus, setSystemStatus] = useState<string>('checking');
  const [pendingIncidentCount, setPendingIncidentCount] = useState<number>(0);
  
  // Custom navigation states
  const [activeWorkflowId, setActiveWorkflowId] = useState<string | null>(null);
  const [activeWorkOrderId, setActiveWorkOrderId] = useState<string | null>(null);
  const [productionSubTab, setProductionSubTab] = useState<'products' | 'materials'>('products');
  const [machinesSubTab, setMachinesSubTab] = useState<'machines' | 'capabilities'>('machines');

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const fetchIncidentCount = async () => {
    try {
      const res = await fetch(`${API_URL}/api/incidents?status=PENDING_REVIEW`);
      if (res.ok) {
        const data = await res.json();
        setPendingIncidentCount(data.length);
      }
    } catch {
      // ignore in background
    }
  };

  const handleNavigateToExecution = async (workOrderId: string) => {
    try {
      const res = await fetch(`${API_URL}/api/work-orders/${workOrderId}`);
      if (res.ok) {
        const wo = await res.json();
        if (wo.workflowId) {
          setActiveWorkflowId(wo.workflowId);
          setActiveWorkOrderId(workOrderId);
          setActiveTab('Workflows');
          return;
        }
      }
    } catch (err) {
      console.error('Failed to navigate to execution:', err);
    }
    setActiveTab('Work Orders');
  };

  useEffect(() => {
    const checkSystemStatus = async () => {
      try {
        const response = await fetch(`${API_URL}/api/health`);
        if (response.ok) {
          const data: HealthResponse = await response.json();
          setSystemStatus(data.status);
        } else {
          setSystemStatus('degraded');
        }
      } catch {
        setSystemStatus('offline');
      }
    };
    checkSystemStatus();
    fetchIncidentCount();
    const interval = setInterval(() => {
      checkSystemStatus();
      fetchIncidentCount();
    }, 5000);
    return () => clearInterval(interval);
  }, [API_URL]);

  // Live WebSocket incident notification updates
  useEffect(() => {
    const wsUrl = API_URL.replace(/^http/, 'ws') + '/api/ws/execution';
    const ws = new WebSocket(wsUrl);

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if ([
          'INCIDENT_CREATED', 'INCIDENT_CONFIRMED', 'INCIDENT_DISMISSED',
          'INCIDENT_RESOLVED', 'MACHINE_FAILED', 'MACHINE_RECOVERED'
        ].includes(msg.type)) {
          fetchIncidentCount();
        }
      } catch (err) {
        console.error('WS parse error:', err);
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

  const menuItems = [
    { name: 'Overview', icon: Activity },
    { name: 'Production', icon: Layers },
    { name: 'Workflows', icon: ClipboardList },
    { name: 'Machines', icon: Cpu },
    { name: 'Incidents', icon: AlertTriangle, badge: pendingIncidentCount },
    { name: 'Work Orders', icon: Briefcase },
    { name: 'Users', icon: UserIcon },
    { name: 'Audit Log', icon: ClipboardList },
    { name: 'Settings', icon: SettingsIcon },
  ];

  return (
    <div className="min-h-screen bg-white flex text-neutral-900">
      
      {/* Sidebar - Desktop */}
      <aside className="hidden md:flex flex-col w-64 border-r border-neutral-200 bg-white">
        <div className="h-16 border-b border-neutral-200 flex items-center px-6">
          <span className="font-semibold tracking-tight text-neutral-900 font-mono text-sm flex items-center gap-2">
            <span className="w-2.5 h-2.5 bg-black rounded-sm" />
            ADAPTIVE-MES
          </span>
        </div>
        <nav className="flex-1 px-4 py-6 space-y-1">
          {menuItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.name;
            const badgeCount = item.badge || 0;
            return (
              <button
                key={item.name}
                onClick={() => {
                  setActiveTab(item.name);
                  setActiveWorkflowId(null); // Reset visual designer state
                }}
                className={`w-full flex items-center justify-between px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                  isActive 
                    ? 'bg-neutral-100 text-neutral-900' 
                    : 'text-neutral-500 hover:text-neutral-900 hover:bg-neutral-50'
                }`}
              >
                <div className="flex items-center gap-3">
                  <Icon className={`w-4 h-4 ${isActive ? 'text-neutral-900' : 'text-neutral-400'}`} />
                  <span>{item.name}</span>
                </div>
                {badgeCount > 0 && (
                  <span className="px-1.5 py-0.2 bg-amber-500 text-white rounded-full text-[10px] font-bold font-mono animate-pulse">
                    {badgeCount}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
        <div className="p-4 border-t border-neutral-200">
          <div className="flex items-center gap-3 px-2 py-1.5 rounded-md hover:bg-neutral-50 cursor-pointer">
            <div className="w-8 h-8 rounded-full border border-neutral-200 flex items-center justify-center bg-neutral-50">
              <UserIcon className="w-4 h-4 text-neutral-500" />
            </div>
            <div>
              <p className="text-xs font-semibold text-neutral-900">Aryan Singh</p>
              <p className="text-[10px] text-neutral-400 font-mono">administrator</p>
            </div>
          </div>
        </div>
      </aside>

      {/* Sidebar - Mobile / Tablet Overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 flex md:hidden bg-neutral-900/10 backdrop-blur-xs">
          <div className="relative flex flex-col w-64 bg-white border-r border-neutral-200">
            <div className="h-16 border-b border-neutral-200 flex items-center justify-between px-6">
              <span className="font-semibold tracking-tight text-neutral-900 font-mono text-sm flex items-center gap-2">
                <span className="w-2.5 h-2.5 bg-black rounded-sm" />
                ADAPTIVE-MES
              </span>
              <button onClick={() => setSidebarOpen(false)} className="p-1 hover:bg-neutral-100 rounded">
                <X className="w-5 h-5 text-neutral-500" />
              </button>
            </div>
            <nav className="flex-1 px-4 py-6 space-y-1">
              {menuItems.map((item) => {
                const Icon = item.icon;
                const isActive = activeTab === item.name;
                const badgeCount = item.badge || 0;
                return (
                  <button
                    key={item.name}
                    onClick={() => {
                      setActiveTab(item.name);
                      setActiveWorkflowId(null);
                      setSidebarOpen(false);
                    }}
                    className={`w-full flex items-center justify-between px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                      isActive 
                        ? 'bg-neutral-100 text-neutral-900' 
                        : 'text-neutral-500 hover:text-neutral-900 hover:bg-neutral-50'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <Icon className={`w-4 h-4 ${isActive ? 'text-neutral-900' : 'text-neutral-400'}`} />
                      <span>{item.name}</span>
                    </div>
                    {badgeCount > 0 && (
                      <span className="px-1.5 py-0.2 bg-amber-500 text-white rounded-full text-[10px] font-bold font-mono">
                        {badgeCount}
                      </span>
                    )}
                  </button>
                );
              })}
            </nav>
            <div className="p-4 border-t border-neutral-200">
              <div className="flex items-center gap-3 px-2 py-1.5 rounded-md hover:bg-neutral-50">
                <div className="w-8 h-8 rounded-full border border-neutral-200 flex items-center justify-center bg-neutral-50">
                  <UserIcon className="w-4 h-4 text-neutral-500" />
                </div>
                <div>
                  <p className="text-xs font-semibold text-neutral-900">Aryan Singh</p>
                  <p className="text-[10px] text-neutral-400 font-mono">administrator</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main Container */}
      <div className="flex-1 flex flex-col min-w-0 bg-neutral-50/30">
        
        {/* Header */}
        <header className="h-16 border-b border-neutral-200 bg-white flex items-center justify-between px-6 md:px-8 shrink-0">
          <div className="flex items-center gap-4">
            <button 
              onClick={() => setSidebarOpen(true)} 
              className="p-1 hover:bg-neutral-100 rounded md:hidden text-neutral-500 hover:text-neutral-900"
            >
              <Menu className="w-5 h-5" />
            </button>
            <h1 className="text-base font-semibold text-neutral-900">{activeTab}</h1>
            
            {/* Sub-tab navigations for nested views */}
            {activeTab === 'Production' && (
              <div className="flex items-center gap-1 bg-neutral-100 p-0.5 rounded-md text-[10px] ml-4 font-mono font-medium">
                <button
                  onClick={() => setProductionSubTab('products')}
                  className={`px-2.5 py-1 rounded transition-colors ${
                    productionSubTab === 'products' ? 'bg-white text-neutral-900 shadow-xs' : 'text-neutral-500'
                  }`}
                >
                  Products Catalog
                </button>
                <button
                  onClick={() => setProductionSubTab('materials')}
                  className={`px-2.5 py-1 rounded transition-colors ${
                    productionSubTab === 'materials' ? 'bg-white text-neutral-900 shadow-xs' : 'text-neutral-500'
                  }`}
                >
                  Materials Stock
                </button>
              </div>
            )}

            {activeTab === 'Machines' && (
              <div className="flex items-center gap-1 bg-neutral-100 p-0.5 rounded-md text-[10px] ml-4 font-mono font-medium">
                <button
                  onClick={() => setMachinesSubTab('machines')}
                  className={`px-2.5 py-1 rounded transition-colors ${
                    machinesSubTab === 'machines' ? 'bg-white text-neutral-900 shadow-xs' : 'text-neutral-500'
                  }`}
                >
                  Workstations List
                </button>
                <button
                  onClick={() => setMachinesSubTab('capabilities')}
                  className={`px-2.5 py-1 rounded transition-colors ${
                    machinesSubTab === 'capabilities' ? 'bg-white text-neutral-900 shadow-xs' : 'text-neutral-500'
                  }`}
                >
                  Capabilities Registry
                </button>
              </div>
            )}
          </div>
          
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 border border-neutral-200 rounded-full px-3 py-1 bg-white shadow-xs">
              <span className={`w-2 h-2 rounded-full ${
                systemStatus === 'healthy' ? 'bg-emerald-500' :
                systemStatus === 'degraded' ? 'bg-amber-500' :
                systemStatus === 'offline' ? 'bg-red-500' : 'bg-neutral-300'
              }`} />
              <span className="text-[11px] font-medium text-neutral-600 uppercase tracking-wider font-mono">
                {systemStatus === 'healthy' && 'Systems OK'}
                {systemStatus === 'degraded' && 'Degraded State'}
                {systemStatus === 'offline' && 'Offline'}
                {systemStatus === 'checking' && 'Checking...'}
              </span>
            </div>
          </div>
        </header>

        {/* Content Area */}
        <main className="flex-1 overflow-auto p-6 md:p-8 min-h-0">
          <div className="max-w-6xl mx-auto h-full">
            
            {activeTab === 'Overview' && <Dashboard />}

            {activeTab === 'Production' && (
              productionSubTab === 'products' ? <ProductsPage /> : <MaterialsPage />
            )}

            {activeTab === 'Workflows' && (
              activeWorkflowId ? (
                <WorkflowDesignerPage 
                    workflowId={activeWorkflowId}
                    initialWorkOrderId={activeWorkOrderId || undefined}
                    onBack={() => {
                    setActiveWorkflowId(null);
                    setActiveWorkOrderId(null);
                  }} 
                />
              ) : (
                <WorkflowsPage onSelectWorkflow={(id) => {
                  setActiveWorkflowId(id);
                  setActiveWorkOrderId(null);
                }} />
              )
            )}

            {activeTab === 'Machines' && (
              machinesSubTab === 'machines' ? <MachinesPage /> : <CapabilitiesPage />
            )}

            {activeTab === 'Incidents' && <IncidentsPage />}

            {activeTab === 'Work Orders' && (
              <WorkOrdersPage 
                onOpenDesigner={(wfId, woId) => {
                  setActiveWorkflowId(wfId);
                  setActiveWorkOrderId(woId || null);
                  setActiveTab('Workflows');
                }} 
              />
            )}

            {activeTab === 'Users' && (
              <UsersPage onNavigateToExecution={handleNavigateToExecution} />
            )}

            {activeTab === 'Audit Log' && <AuditLogsPage />}

            {activeTab === 'Settings' && <SettingsPage />}
            
          </div>
        </main>
      </div>

    </div>
  );
}
