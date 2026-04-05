import { useState } from 'react';
import WatchlistSidebar from './components/WatchlistSidebar';
import ChartGrid from './components/ChartGrid';
import TradePanel from './components/TradePanel';
import PortfolioSummary from './components/PortfolioSummary';
import TradeBlotter from './components/TradeBlotter';
import ConnectionStatus from './components/ConnectionStatus';

const NAV_ITEMS = [
  { id: 'home', label: 'Home' },
  { id: 'dashboard', label: 'Trade Blotter' },
];

export default function App() {
  const [selectedSymbols, setSelectedSymbols] = useState(['AAPL', 'MSFT']);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [latestPrices, setLatestPrices] = useState({});
  const [symbolMeta, setSymbolMeta] = useState({});
  const [activeNav, setActiveNav] = useState('home');

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
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm lg:hidden"
              >
                {sidebarOpen ? 'Hide' : 'Show'} Watchlist
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Nav Bar */}
      <div className="border-b border-slate-700 bg-slate-900/50 px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-[1600px] flex gap-1">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveNav(item.id)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                activeNav === item.id
                  ? 'border-sky-500 text-white'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {/* Page Content */}
      <div className="mx-auto max-w-[1600px] flex-1 px-4 py-6 sm:px-6 lg:px-8">

        {/* Home */}
        {activeNav === 'home' && (
          <div className="flex flex-col gap-6 lg:flex-row">
            {sidebarOpen && (
              <aside className="w-full rounded-3xl border border-slate-700 bg-slate-900/70 shadow-xl shadow-slate-950/20 lg:w-48 lg:flex-shrink-0">
                <WatchlistSidebar
                  selectedSymbols={selectedSymbols}
                  onSelectSymbols={setSelectedSymbols}
                  onSymbolMetaChange={setSymbolMeta}
                />
              </aside>
            )}
            <main className="flex-1 space-y-6">
              <section className="rounded-3xl border border-slate-700 bg-slate-900/70 p-6 shadow-xl shadow-slate-950/20">
                <ChartGrid selectedSymbols={selectedSymbols} onPricesUpdated={setLatestPrices} symbolMeta={symbolMeta} />
              </section>
              <section className="rounded-3xl border border-slate-700 bg-slate-900/70 p-6 shadow-xl shadow-slate-950/20">
                <TradePanel selectedSymbols={selectedSymbols} />
              </section>
            </main>
            <aside className="w-full rounded-3xl border border-slate-700 bg-slate-900/70 shadow-xl shadow-slate-950/20 lg:w-56 lg:flex-shrink-0">
              <PortfolioSummary latestPrices={latestPrices} symbolMeta={symbolMeta} />
            </aside>
          </div>
        )}

        {/* Trade Blotter */}
        {activeNav === 'dashboard' && (
          <section className="rounded-3xl border border-slate-700 bg-slate-900/70 p-6 shadow-xl shadow-slate-950/20">
            <TradeBlotter symbolMeta={symbolMeta} />
          </section>
        )}

      </div>
    </div>
  );
}
