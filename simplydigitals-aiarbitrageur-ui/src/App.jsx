import { useState } from 'react';
import WatchlistSidebar from './components/WatchlistSidebar';
import ChartGrid from './components/ChartGrid';
import TradePanel from './components/TradePanel';
import PortfolioSummary from './components/PortfolioSummary';

export default function App() {
  const [selectedSymbols, setSelectedSymbols] = useState(['AAPL', 'MSFT']);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      {/* Header */}
      <div className="border-b border-slate-700 bg-slate-900/70 px-4 py-4 shadow-lg shadow-slate-950/20 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-[1600px]">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.35em] text-sky-400">AI Arbitrageur</p>
              <h1 className="text-2xl font-semibold sm:text-3xl">Intraday Trading Dashboard</h1>
            </div>
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm lg:hidden"
            >
              {sidebarOpen ? 'Hide' : 'Show'} Watchlist
            </button>
          </div>
        </div>
      </div>

      {/* Main Layout: Vertical mobile, 3-column horizontal desktop */}
      <div className="mx-auto max-w-[1600px] flex-1 px-4 py-6 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-6 lg:flex-row">
          {/* Left Sidebar: Full-width mobile, Fixed 200px desktop */}
          {sidebarOpen && (
            <aside className="w-full rounded-3xl border border-slate-700 bg-slate-900/70 shadow-xl shadow-slate-950/20 lg:w-48 lg:flex-shrink-0">
              <WatchlistSidebar
                selectedSymbols={selectedSymbols}
                onSelectSymbols={setSelectedSymbols}
              />
            </aside>
          )}

          {/* Main Content: Charts and Trade Panel */}
          <main className="flex-1 space-y-6">
            {/* Charts Grid */}
            <section className="rounded-3xl border border-slate-700 bg-slate-900/70 p-6 shadow-xl shadow-slate-950/20">
              <ChartGrid selectedSymbols={selectedSymbols} />
            </section>

            {/* Trade Panel */}
            <section className="rounded-3xl border border-slate-700 bg-slate-900/70 p-6 shadow-xl shadow-slate-950/20">
              <TradePanel selectedSymbols={selectedSymbols} />
            </section>
          </main>

          {/* Right Sidebar: Full-width mobile, Fixed 200px desktop */}
          <aside className="w-full rounded-3xl border border-slate-700 bg-slate-900/70 shadow-xl shadow-slate-950/20 lg:w-56 lg:flex-shrink-0">
            <PortfolioSummary />
          </aside>
        </div>
      </div>
    </div>
  );
}
