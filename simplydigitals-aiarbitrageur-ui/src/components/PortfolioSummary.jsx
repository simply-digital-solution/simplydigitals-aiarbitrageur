import { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api/v1';

const fmt = (n) =>
  (n || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const sign = (n) => (n >= 0 ? '+' : '');
const plClass = (n) => (n >= 0 ? 'text-emerald-400' : 'text-rose-400');


export default function PortfolioSummary({ latestPrices = {}, symbolMeta = {} }) {
  const [positions, setPositions] = useState([]);
  const [account, setAccount] = useState({ cash: null, buying_power: null });
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('summary');
  const [syncStatus, setSyncStatus] = useState(null);
  const [syncing, setSyncing] = useState(false);

  const fetchPortfolio = async () => {
    setLoading(true);
    try {
      const [posResp, accResp] = await Promise.all([
        axios.get(`${API_BASE_URL}/portfolio`),
        axios.get(`${API_BASE_URL}/portfolio/account`),
      ]);
      setPositions(posResp.data || []);
      setAccount(accResp.data || {});
    } catch {
      // API unavailable — leave existing state unchanged
    }
    setLoading(false);
  };

  const fetchTrades = async () => {
    try {
      const resp = await axios.get(`${API_BASE_URL}/portfolio/trades`);
      setTrades(resp.data || []);
    } catch {
      // API unavailable — leave existing state unchanged
    }
  };

  const checkSyncStatus = async () => {
    try {
      const resp = await axios.get(`${API_BASE_URL}/portfolio/trade-sync-status`);
      setSyncStatus(resp.data);
    } catch {
      setSyncStatus(null);
    }
  };

  const syncTrades = async () => {
    setSyncing(true);
    try {
      await axios.post(`${API_BASE_URL}/portfolio/sync-trades`);
      await Promise.all([fetchTrades(), checkSyncStatus()]);
    } catch {
      // Leave state unchanged on error
    }
    setSyncing(false);
  };

  useEffect(() => {
    fetchPortfolio();
    fetchTrades();
    const interval = setInterval(() => { fetchPortfolio(); fetchTrades(); }, 30000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (activeTab === 'history') checkSyncStatus();
  }, [activeTab]);

  // Enrich positions with live prices from ChartGrid when available
  const enriched = positions.map((pos) => {
    const live = latestPrices[pos.symbol];
    if (!live) return pos;
    const currentPrice = live.current;
    const currentValue = currentPrice * pos.qty;
    const costBasis = pos.avg_cost * pos.qty;
    const totalPnl = currentValue - costBasis;
    const totalPnlPct = costBasis ? (totalPnl / costBasis) * 100 : 0;
    const dayPnl = (live.current - live.dayOpen) * pos.qty;
    const yesterdayValue = live.prevClose != null ? live.prevClose * pos.qty : null;
    return { ...pos, current_price: currentPrice, current_value: currentValue, pnl: totalPnl, pnl_pct: totalPnlPct, day_pnl: dayPnl, yesterday_value: yesterdayValue };
  });

  // Fallback for positions without live prices: use backend pnl
  const totalPnl = enriched.reduce((sum, p) => sum + (p.pnl || 0), 0);
  const dayPnl = enriched.reduce((sum, p) => sum + (p.day_pnl ?? (p.pnl || 0)), 0);
  const totalValue = enriched.reduce((sum, p) => sum + (p.current_value || 0), 0);

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* Header */}
      <div>
        <p className="text-xs uppercase tracking-[0.35em] text-sky-400">Portfolio</p>
        <h2 className="mt-1 text-lg font-semibold">Account Summary</h2>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-700 text-sm">
        {['summary', 'positions', 'history'].map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-3 py-2 font-medium capitalize border-b-2 transition-colors ${
              activeTab === tab
                ? 'border-sky-500 text-white'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Summary Tab */}
      {activeTab === 'summary' && (
        <div className="space-y-3">
          <div className="rounded-2xl border border-slate-700 bg-slate-950/60 p-4 space-y-3">
            <div>
              <p className="text-xs text-slate-400">Portfolio Value</p>
              <p className="mt-1 text-2xl font-semibold text-white">${fmt(totalValue)}</p>
            </div>
            <div className="grid grid-cols-2 gap-3 pt-2 border-t border-slate-700">
              <div>
                <p className="text-xs text-slate-400">Day P&L</p>
                <p className={`mt-1 text-base font-semibold ${plClass(dayPnl)}`}>
                  {sign(dayPnl)}${fmt(Math.abs(dayPnl))}
                </p>
              </div>
              <div>
                <p className="text-xs text-slate-400">Total P&L</p>
                <p className={`mt-1 text-base font-semibold ${plClass(totalPnl)}`}>
                  {sign(totalPnl)}${fmt(Math.abs(totalPnl))}
                </p>
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-700 bg-slate-950/60 p-4 space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-400">Cash Available</span>
              <span className="text-emerald-400 font-medium">
                {account.cash != null ? `$${fmt(account.cash)}` : '—'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Buying Power</span>
              <span className="text-sky-400 font-medium">
                {account.buying_power != null ? `$${fmt(account.buying_power)}` : '—'}
              </span>
            </div>
          </div>

          {Object.keys(latestPrices).length > 0 && (
            <div className="rounded-2xl border border-slate-700 bg-slate-950/60 p-4 text-xs text-slate-400">
              {`Live prices from ${Object.keys(latestPrices).join(', ')}`}
            </div>
          )}
        </div>
      )}

      {/* Positions Tab */}
      {activeTab === 'positions' && (
        <div className="space-y-2">
          {loading && positions.length === 0 ? (
            <p className="text-xs text-slate-400 py-2">Loading...</p>
          ) : enriched.length === 0 ? (
            <p className="text-xs text-slate-500 py-2">No open positions</p>
          ) : (
            enriched.map((pos) => (
              <div key={pos.symbol} className="rounded-xl border border-slate-700/50 bg-slate-900/50 p-3 space-y-1.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="font-semibold text-sm">{pos.symbol}</span>
                    {symbolMeta[pos.symbol]?.exchangeDisplay && (
                      <span className="text-[10px] text-sky-400 leading-none">{symbolMeta[pos.symbol].exchangeDisplay}</span>
                    )}
                  </div>
                  <span className="text-xs text-slate-400">{pos.qty} shares</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400">Avg ${fmt(pos.avg_cost)}</span>
                  <span className="text-slate-300">${fmt(pos.current_price)}</span>
                </div>
                <div className="flex justify-between text-xs border-t border-slate-700/50 pt-1.5">
                  <span className="text-slate-400">Purchase Value</span>
                  <span className="text-slate-300">${fmt(pos.avg_cost * pos.qty)}</span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400">Yesterday Value</span>
                  <span className="text-slate-300">
                    {pos.yesterday_value != null ? `$${fmt(pos.yesterday_value)}` : '—'}
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400">Market Value</span>
                  <span className="text-slate-300">
                    {pos.current_value != null ? `$${fmt(pos.current_value)}` : '—'}
                  </span>
                </div>
                <div className="flex justify-between text-xs border-t border-slate-700/50 pt-1.5">
                  <span className="text-slate-400">Day P&L</span>
                  <span className={plClass(pos.day_pnl ?? pos.pnl)}>
                    {sign(pos.day_pnl ?? pos.pnl)}${fmt(Math.abs((pos.day_pnl ?? pos.pnl) || 0))}
                  </span>
                </div>
                <div className="flex justify-between text-xs">
                  <span className="text-slate-400">Total P&L</span>
                  <span className={plClass(pos.pnl)}>
                    {sign(pos.pnl)}${fmt(Math.abs(pos.pnl || 0))}
                    {pos.pnl_pct != null && (
                      <span className="ml-1 opacity-70">({sign(pos.pnl_pct)}{(pos.pnl_pct || 0).toFixed(2)}%)</span>
                    )}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Trade History Tab */}
      {activeTab === 'history' && (
        <div className="space-y-2">
          {/* Sync mismatch warning */}
          {syncStatus?.alpaca_connected && !syncStatus?.in_sync && (
            <div className="rounded-xl border border-yellow-600/40 bg-yellow-900/20 p-3 flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-xs font-semibold text-yellow-400">Trade history out of sync</p>
                <p className="text-[10px] text-yellow-300/70 mt-0.5">
                  {syncStatus.missing_count} Alpaca order{syncStatus.missing_count !== 1 ? 's' : ''} not in local history
                </p>
              </div>
              <button
                onClick={syncTrades}
                disabled={syncing}
                className="shrink-0 rounded-lg bg-yellow-600/30 hover:bg-yellow-600/50 border border-yellow-600/40 px-2.5 py-1 text-[10px] font-semibold text-yellow-300 transition disabled:opacity-50"
              >
                {syncing ? 'Syncing…' : 'Sync Now'}
              </button>
            </div>
          )}
          {syncStatus?.alpaca_connected && syncStatus?.in_sync && (
            <p className="text-[10px] text-emerald-500/70 text-right">✓ In sync with Alpaca</p>
          )}

          <div className="max-h-96 overflow-y-auto space-y-2">
            {trades.length === 0 ? (
              <p className="text-xs text-slate-500 py-2">No trade history</p>
            ) : (
              trades.map((t) => (
                <div key={t.id} className="rounded-xl border border-slate-700/50 bg-slate-900/50 p-3">
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-xs font-bold uppercase px-1.5 py-0.5 rounded ${
                          t.side === 'buy'
                            ? 'bg-emerald-900/40 text-emerald-400'
                            : 'bg-rose-900/40 text-rose-400'
                        }`}
                      >
                        {t.side}
                      </span>
                      <span className="font-semibold text-sm">{t.symbol}</span>
                      {symbolMeta[t.symbol]?.exchangeDisplay && (
                        <span className="text-[10px] text-sky-400 leading-none">{symbolMeta[t.symbol].exchangeDisplay}</span>
                      )}
                    </div>
                    <span
                      className={`text-xs ${
                        t.status === 'filled' ? 'text-emerald-400' : t.status === 'pending' ? 'text-yellow-400' : 'text-slate-400'
                      }`}
                    >
                      {t.status}
                    </span>
                  </div>
                  <div className="flex justify-between text-xs text-slate-400">
                    <span>{t.qty} @ {t.execution_price != null ? `$${fmt(t.execution_price)}` : '—'}</span>
                    <span>{new Date(t.created_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Refresh */}
      <button
        onClick={() => { fetchPortfolio(); fetchTrades(); }}
        disabled={loading}
        className="w-full rounded-lg border border-slate-700 bg-slate-950/50 px-3 py-2 text-xs font-medium text-sky-400 hover:bg-slate-900 transition disabled:opacity-50"
      >
        {loading ? 'Refreshing...' : 'Refresh'}
      </button>
    </div>
  );
}
