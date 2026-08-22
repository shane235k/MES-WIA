export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-neutral-900">Settings</h2>
        <p className="text-xs text-neutral-500 mt-0.5">Configure system-wide parameters and MES constants.</p>
      </div>
      
      <div className="border border-neutral-200 rounded-lg p-6 bg-white max-w-md space-y-4">
        <h3 className="text-sm font-semibold text-neutral-900">Local Environment Profile</h3>
        <p className="text-xs text-neutral-500">The Adaptive MES is running in local development mode without external microservices or Docker orchestrations.</p>
        
        <div className="pt-4 border-t border-neutral-100 font-mono text-[10px] space-y-2 text-neutral-600">
          <div>
            <span className="text-neutral-400">API Gateway:</span>
            <div className="text-neutral-950 font-bold">http://localhost:8000</div>
          </div>
          <div>
            <span className="text-neutral-400">Database Connection:</span>
            <div className="text-neutral-950">mongodb://127.0.0.1:27017/mes_db</div>
          </div>
          <div>
            <span className="text-neutral-400">Redis Cache Address:</span>
            <div className="text-neutral-950">redis://127.0.0.1:6379/0</div>
          </div>
          <div>
            <span className="text-neutral-400">Build Version:</span>
            <div className="text-neutral-950">Phase 2 Core</div>
          </div>
        </div>
      </div>
    </div>
  );
}
