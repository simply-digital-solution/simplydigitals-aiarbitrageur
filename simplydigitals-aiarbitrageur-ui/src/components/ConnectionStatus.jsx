import { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api/v1';
const POLL_INTERVAL = 30000; // 30 s

function Dot({ ok, checking }) {
  if (checking) return <span className="h-2 w-2 rounded-full bg-slate-500 animate-pulse" />;
  return (
    <span
      className={`h-2 w-2 rounded-full ${ok ? 'bg-emerald-400' : 'bg-rose-500'}`}
    />
  );
}

export default function ConnectionStatus() {
  const [status, setStatus] = useState(null);
  const [checking, setChecking] = useState(true);
  const [expanded, setExpanded] = useState(false);

  const fetchStatus = async () => {
    setChecking(true);
    try {
      const resp = await axios.get(`${API_BASE_URL}/status`);
      setStatus(resp.data);
    } catch {
      setStatus({ yfinance: { ok: false, detail: 'API unreachable' }, alpaca: { ok: false, detail: 'API unreachable' } });
    }
    setChecking(false);
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, []);

  const allOk = status?.yfinance?.ok && status?.alpaca?.ok;
  const anyOk = status?.yfinance?.ok || status?.alpaca?.ok;
  const overallColor = checking ? 'text-slate-400' : allOk ? 'text-emerald-400' : anyOk ? 'text-yellow-400' : 'text-rose-400';

  return (
    <div className="relative">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-1.5 text-xs hover:bg-slate-700/60 transition"
        title="Service connectivity"
      >
        <span className="flex items-center gap-1.5">
          <Dot ok={status?.yfinance?.ok} checking={checking} />
          <Dot ok={status?.alpaca?.ok} checking={checking} />
        </span>
        <span className={`font-medium ${overallColor}`}>
          {checking ? 'Checking...' : allOk ? 'Connected' : anyOk ? 'Partial' : 'Disconnected'}
        </span>
      </button>

      {expanded && (
        <div className="absolute right-0 top-full mt-2 z-50 w-64 rounded-xl border border-slate-700 bg-slate-900 shadow-xl shadow-slate-950/40 p-3 space-y-2.5">
          <p className="text-xs uppercase tracking-[0.2em] text-slate-500 pb-1 border-b border-slate-700/50">
            Service Status
          </p>

          {[
            { key: 'yfinance', label: 'yFinance', subtitle: 'Market data' },
            { key: 'alpaca', label: 'Alpaca Broker', subtitle: 'Order execution' },
          ].map(({ key, label, subtitle }) => {
            const svc = status?.[key];
            return (
              <div key={key} className="flex items-start gap-2.5">
                <span className="mt-0.5 shrink-0">
                  <Dot ok={svc?.ok} checking={checking} />
                </span>
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-xs font-semibold text-slate-200">{label}</span>
                    <span className={`text-[10px] font-medium ${svc?.ok ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {checking ? '—' : svc?.ok ? 'OK' : 'Error'}
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-500">{subtitle}</p>
                  {svc?.detail && !checking && (
                    <p className="text-[10px] text-slate-400 truncate mt-0.5" title={svc.detail}>
                      {svc.detail}
                    </p>
                  )}
                </div>
              </div>
            );
          })}

          <div className="pt-1 border-t border-slate-700/50 flex items-center justify-between">
            <span className="text-[10px] text-slate-500">Refreshes every 30s</span>
            <button
              onClick={(e) => { e.stopPropagation(); fetchStatus(); }}
              className="text-[10px] text-sky-400 hover:text-sky-300"
            >
              Check now
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
