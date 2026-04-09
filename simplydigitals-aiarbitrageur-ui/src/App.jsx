import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { LayoutDashboard, ScrollText, TrendingUp, Menu, X, BookMarked } from 'lucide-react';
import WatchlistSidebar from './components/WatchlistSidebar';
import ChartGrid from './components/ChartGrid';
import TradePanel from './components/TradePanel';
import PortfolioSummary from './components/PortfolioSummary';
import TradeBlotter from './components/TradeBlotter';
import ConnectionStatus from './components/ConnectionStatus';

const API_BASE_URL = 'http://localhost:8000/api/v1';

const NAV_ITEMS = [
  { id: 'home', label: 'Home', Icon: LayoutDashboard },
  { id: 'watchlist', label: 'Watchlist', Icon: BookMarked, mobileOnly: true },
  { id: 'trading', label: 'Trading', Icon: TrendingUp },
  { id: 'dashboard', label: 'Trade Blotter', Icon: ScrollText },
];

export default function App() {
  const [selectedSymbols, setSelectedSymbols] = useState(['AAPL', 'MSFT']);
  const [latestPrices, setLatestPrices] = useState({});
  const [symbolMeta, setSymbolMeta] = useState({});
  const [activeNav, setActiveNav] = useState('home');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [tradePrefill, setTradePrefill] = useState(null);

  // Shared portfolio data — fetched once here, passed to both PortfolioSummary and TradeBlotter
  const [positions, setPositions] = useState([]);
  const [account, setAccount] = useState({ cash: null, buying_power: null });
  const [trades, setTrades] = useState([]);
  const [syncStatus, setSyncStatus] = useState(null);
  const [portfolioLoading, setPortfolioLoading] = useState(false);

  const refreshPortfolio = useCallback(async () => {
    setPortfolioLoading(true);
    try {
      const [posResp, accResp, tradesResp, syncResp] = await Promise.all([
        axios.get(`${API_BASE_URL}/portfolio`),
        axios.get(`${API_BASE_URL}/portfolio/account`),
        axios.get(`${API_BASE_URL}/portfolio/trades`),
        axios.get(`${API_BASE_URL}/portfolio/trade-sync-status`).catch(() => ({ data: null })),
      ]);
      setPositions(posResp.data || []);
      setAccount(accResp.data || {});
      setTrades(tradesResp.data || []);
      setSyncStatus(syncResp.data);
    } catch {
      // leave existing state unchanged
    }
    setPortfolioLoading(false);
  }, []);

  // Single interval drives all portfolio data — 30s consistent refresh
  useEffect(() => {
    refreshPortfolio();
    const interval = setInterval(refreshPortfolio, 30000);
    return () => clearInterval(interval);
  }, [refreshPortfolio]);

  const handleNavSelect = (id) => {
    setActiveNav(id);
    setMobileMenuOpen(false);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      {/* Header */}
      <div className="border-b border-slate-700 bg-slate-900/70 px-4 py-4 shadow-lg shadow-slate-950/20 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-[1600px]">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.35em] text-sky-400">AI Arbitrageur</p>
              <h1 className="text-2xl font-semibold sm:text-3xl">Trading Dashboard</h1>
            </div>
            <div className="flex items-center gap-3">
              <ConnectionStatus />
              {/* Hamburger — mobile only */}
              <button
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="rounded-lg border border-slate-700 bg-slate-800 p-2 lg:hidden"
                aria-label="Toggle menu"
              >
                {mobileMenuOpen ? <X size={18} /> : <Menu size={18} />}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Mobile dropdown nav */}
      {mobileMenuOpen && (
        <div className="border-b border-slate-700 bg-slate-900 lg:hidden">
          <div className="mx-auto max-w-[1600px] px-4 py-2 flex flex-col">
            {NAV_ITEMS.map(({ id, label, Icon }) => (
              <button
                key={id}
                onClick={() => handleNavSelect(id)}
                className={`flex items-center gap-3 px-3 py-3 text-sm font-medium rounded-lg transition-colors ${
                  activeNav === id
                    ? 'bg-sky-900/40 text-white'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                }`}
              >
                <Icon size={16} />
                {label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Desktop Nav Bar — excludes mobileOnly items */}
      <div className="border-b border-slate-700 bg-slate-900/50 px-4 sm:px-6 lg:px-8 hidden lg:block">
        <div className="mx-auto max-w-[1600px] flex gap-1">
          {NAV_ITEMS.filter((item) => !item.mobileOnly).map(({ id, label, Icon }) => (
            <button
              key={id}
              onClick={() => setActiveNav(id)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                activeNav === id
                  ? 'border-sky-500 text-white'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Icon size={15} />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Page Content */}
      <div className="mx-auto max-w-[1600px] flex-1 px-4 py-6 sm:px-6 lg:px-8">

        {/* Home */}
        {activeNav === 'home' && (
          <div className="flex flex-col gap-6 lg:flex-row">
            <aside className="hidden lg:block w-full rounded-3xl border border-slate-700 bg-slate-900/70 shadow-xl shadow-slate-950/20 lg:w-48 lg:flex-shrink-0">
              <WatchlistSidebar
                selectedSymbols={selectedSymbols}
                onSelectSymbols={setSelectedSymbols}
                onSymbolMetaChange={setSymbolMeta}
              />
            </aside>
            <main className="flex-1 space-y-6 min-w-0">
              <section className="rounded-3xl border border-slate-700 bg-slate-900/70 p-4 shadow-xl shadow-slate-950/20 sm:p-6">
                <ChartGrid
                  selectedSymbols={selectedSymbols}
                  onPricesUpdated={setLatestPrices}
                  symbolMeta={symbolMeta}
                />
              </section>
            </main>
            <aside className="w-full rounded-3xl border border-slate-700 bg-slate-900/70 shadow-xl shadow-slate-950/20 lg:w-56 lg:flex-shrink-0">
              <PortfolioSummary
                positions={positions}
                account={account}
                latestPrices={latestPrices}
                symbolMeta={symbolMeta}
                loading={portfolioLoading}
                onRefresh={refreshPortfolio}
              />
            </aside>
          </div>
        )}

        {/* Watchlist — mobile nav page */}
        {activeNav === 'watchlist' && (
          <section className="rounded-3xl border border-slate-700 bg-slate-900/70 shadow-xl shadow-slate-950/20">
            <WatchlistSidebar
              selectedSymbols={selectedSymbols}
              onSelectSymbols={setSelectedSymbols}
              onSymbolMetaChange={setSymbolMeta}
            />
          </section>
        )}

        {/* Trading */}
        {activeNav === 'trading' && (
          <section className="rounded-3xl border border-slate-700 bg-slate-900/70 p-4 shadow-xl shadow-slate-950/20 sm:p-6">
            <TradePanel
              selectedSymbols={selectedSymbols}
              onTradeCompleted={refreshPortfolio}
              prefill={tradePrefill}
              onPrefillConsumed={() => setTradePrefill(null)}
            />
          </section>
        )}

        {/* Trade Blotter */}
        {activeNav === 'dashboard' && (
          <section className="rounded-3xl border border-slate-700 bg-slate-900/70 p-4 shadow-xl shadow-slate-950/20 sm:p-6">
            <TradeBlotter
              trades={trades}
              syncStatus={syncStatus}
              loading={portfolioLoading}
              symbolMeta={symbolMeta}
              onRefresh={refreshPortfolio}
              onOpenTradePanel={(prefill) => { setTradePrefill(prefill); setActiveNav('trading'); }}
            />
          </section>
        )}

      </div>
    </div>
  );
}
