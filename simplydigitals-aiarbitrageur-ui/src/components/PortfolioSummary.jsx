import { useState, useEffect } from "react";
import axios from "axios";

const API_BASE_URL = "http://localhost:8000/api/v1";

export default function PortfolioSummary() {
  const [portfolio, setPortfolio] = useState(null);
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Fetch portfolio data
  const fetchPortfolio = async () => {
    setLoading(true);
    try {
      const resp = await axios.get(`${API_BASE_URL}/portfolio`);
      setPortfolio(resp.data);
      setPositions(resp.data.positions || []);
      setError("");
    } catch (err) {
      console.error("Error fetching portfolio:", err);
      // Mock data for demo
      setPortfolio({
        portfolio_value: 100000,
        cash: 50000,
        buying_power: 200000,
        day_pl: 1250,
        day_pl_pct: 1.25,
        positions: [
          {
            symbol: "AAPL",
            qty: 50,
            avg_entry_price: 150,
            market_value: 8250,
            unrealized_pl: 250,
          },
          {
            symbol: "MSFT",
            qty: 30,
            avg_entry_price: 300,
            market_value: 9150,
            unrealized_pl: 150,
          },
        ],
      });
      setPositions(
        resp.data?.positions || [
          {
            symbol: "AAPL",
            qty: 50,
            avg_entry_price: 150,
            market_value: 8250,
            unrealized_pl: 250,
          },
          {
            symbol: "MSFT",
            qty: 30,
            avg_entry_price: 300,
            market_value: 9150,
            unrealized_pl: 150,
          },
        ],
      );
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchPortfolio();
    // Refresh portfolio every 30 seconds
    const interval = setInterval(fetchPortfolio, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !portfolio) {
    return (
      <div className="rounded-3xl border border-slate-700 bg-slate-900/70 p-6 shadow-xl shadow-slate-950/20">
        <p className="text-slate-400">Loading portfolio...</p>
      </div>
    );
  }

  if (!portfolio) {
    return (
      <div className="rounded-3xl border border-slate-700 bg-slate-900/70 p-6 shadow-xl shadow-slate-950/20">
        <p className="text-rose-400">Unable to load portfolio</p>
      </div>
    );
  }

  const isPositive = portfolio.day_pl_pct >= 0;

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* Header */}
      <div>
        <p className="text-xs uppercase tracking-[0.35em] text-sky-400">
          Portfolio
        </p>
        <h2 className="mt-1 text-lg font-semibold">Account Summary</h2>
      </div>

      {/* Portfolio Stats */}
      <div className="rounded-2xl border border-slate-700 bg-slate-950/60 p-4 space-y-3">
        {/* Total Value */}
        <div>
          <p className="text-xs text-slate-400">Portfolio Value</p>
          <p className="mt-1 text-2xl font-semibold text-white">
            $
            {(portfolio.portfolio_value || 0).toLocaleString("en-US", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </p>
        </div>

        {/* Daily P&L */}
        <div className="flex items-end justify-between pt-2 border-t border-slate-700">
          <div className="flex-1">
            <p className="text-xs text-slate-400">Day P&L</p>
            <p
              className={`mt-1 text-lg font-semibold ${
                isPositive ? "text-emerald-400" : "text-rose-400"
              }`}
            >
              {isPositive ? "+" : ""}$
              {(portfolio.day_pl || 0).toLocaleString("en-US", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </p>
          </div>
          <p
            className={`text-sm font-medium ${
              isPositive ? "text-emerald-400" : "text-rose-400"
            }`}
          >
            {isPositive ? "+" : ""}
            {(portfolio.day_pl_pct || 0).toFixed(2)}%
          </p>
        </div>
      </div>

      {/* Account Details */}
      <div className="rounded-2xl border border-slate-700 bg-slate-950/60 p-4 space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-slate-400">Cash Available</span>
          <span className="text-emerald-400 font-medium">
            $
            {(portfolio.cash || 0).toLocaleString("en-US", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-400">Buying Power</span>
          <span className="text-sky-400 font-medium">
            $
            {(portfolio.buying_power || 0).toLocaleString("en-US", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </span>
        </div>
      </div>

      {/* Open Positions */}
      <div className="rounded-2xl border border-slate-700 bg-slate-950/60 p-4">
        <div className="flex items-center justify-between mb-3">
          <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
            Open Positions
          </p>
          <span className="text-sm font-medium text-sky-400">
            {positions.length}
          </span>
        </div>

        {positions.length === 0 ? (
          <p className="text-xs text-slate-500 py-2">No open positions</p>
        ) : (
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {positions.map((pos) => (
              <div
                key={pos.symbol}
                className="bg-slate-900/50 rounded-lg p-2 border border-slate-700/50"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-medium text-sm">{pos.symbol}</span>
                  <span className="text-xs text-slate-400">
                    {pos.qty} shares
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-400">
                    ${(pos.avg_entry_price || 0).toFixed(2)}
                  </span>
                  <span
                    className={
                      pos.unrealized_pl >= 0
                        ? "text-emerald-400"
                        : "text-rose-400"
                    }
                  >
                    {pos.unrealized_pl >= 0 ? "+" : ""}$
                    {(pos.unrealized_pl || 0).toFixed(2)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Refresh Button */}
      <button
        onClick={fetchPortfolio}
        disabled={loading}
        className="w-full rounded-lg border border-slate-700 bg-slate-950/50 px-3 py-2 text-xs font-medium text-sky-400 hover:bg-slate-900 transition disabled:opacity-50"
      >
        {loading ? "Refreshing..." : "Refresh"}
      </button>
    </div>
  );
}
