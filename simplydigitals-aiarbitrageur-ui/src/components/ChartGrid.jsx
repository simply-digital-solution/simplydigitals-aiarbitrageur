import { useState, useEffect } from 'react';
import axios from 'axios';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

const API_BASE_URL = 'http://localhost:8000/api/v1';

export default function ChartGrid({ selectedSymbols }) {
  const [chartsData, setChartsData] = useState({});
  const [loading, setLoading] = useState(false);
  const [gridSize, setGridSize] = useState(2); // 1, 2, or 4

  // Initial fetch: get full 60 bars
  const fetchChartDataInitial = async () => {
    if (selectedSymbols.length === 0) return;

    setLoading(true);
    try {
      const data = {};
      for (const symbol of selectedSymbols) {
        try {
          const resp = await axios.get(`${API_BASE_URL}/prices/${symbol}/intraday-1min?limit=60`);
          // Format data for Recharts
          data[symbol] = (resp.data || [])
            .map((bar) => ({
              time: new Date(bar.ts).toLocaleTimeString('en-US', {
                hour: '2-digit',
                minute: '2-digit',
              }),
              ts: bar.ts,
              open: bar.open,
              high: bar.high,
              low: bar.low,
              close: bar.close,
              volume: bar.volume,
            }))
            .sort((a, b) => new Date(a.ts) - new Date(b.ts));
        } catch (err) {
          console.error(`Error fetching data for ${symbol}:`, err);
          // Generate mock data for demo
          data[symbol] = generateMockData(symbol);
        }
      }
      setChartsData(data);
    } catch (err) {
      console.error('Error fetching chart data:', err);
    }
    setLoading(false);
  };

  // Append new data: only fetch latest bars and append
  const appendChartData = async () => {
    if (selectedSymbols.length === 0) return;

    try {
      for (const symbol of selectedSymbols) {
        try {
          const resp = await axios.get(`${API_BASE_URL}/prices/${symbol}/intraday-1min?limit=5`);
          const newBars = (resp.data || [])
            .map((bar) => ({
              time: new Date(bar.ts).toLocaleTimeString('en-US', {
                hour: '2-digit',
                minute: '2-digit',
              }),
              ts: bar.ts,
              open: bar.open,
              high: bar.high,
              low: bar.low,
              close: bar.close,
              volume: bar.volume,
            }))
            .sort((a, b) => new Date(a.ts) - new Date(b.ts));

          setChartsData((current) => {
            const existing = current[symbol] || [];
            const lastTs = existing.length > 0 ? existing[existing.length - 1].ts : null;

            // Only append bars newer than what we have
            const barsToAdd = newBars.filter(
              (bar) => !lastTs || new Date(bar.ts) > new Date(lastTs)
            );

            if (barsToAdd.length === 0) return current; // No new data

            // Combine and keep max 60 bars
            const combined = [...existing, ...barsToAdd];
            const trimmed = combined.slice(-60);

            return {
              ...current,
              [symbol]: trimmed,
            };
          });
        } catch (err) {
          console.error(`Error appending data for ${symbol}:`, err);
        }
      }
    } catch (err) {
      console.error('Error appending chart data:', err);
    }
  };

  // Generate mock data for demo purposes
  const generateMockData = (_symbol) => {
    const now = new Date();
    const data = [];
    let basePrice = Math.random() * 300 + 50;

    for (let i = 60; i > 0; i--) {
      const time = new Date(now.getTime() - i * 60000);
      const variation = (Math.random() - 0.5) * 2;
      basePrice += variation;

      data.push({
        time: time.toLocaleTimeString('en-US', {
          hour: '2-digit',
          minute: '2-digit',
        }),
        ts: time.toISOString(),
        open: basePrice - Math.random(),
        high: basePrice + Math.random(),
        low: basePrice - Math.random() * 2,
        close: basePrice,
        volume: Math.random() * 1000000,
      });
    }
    return data;
  };

  // Initial load and when selected symbols change
  useEffect(() => {
    fetchChartDataInitial();
  }, [selectedSymbols]);

  // Poll for updates every 60 seconds (append mode)
  useEffect(() => {
    const interval = setInterval(appendChartData, 60000);
    return () => clearInterval(interval);
  }, [selectedSymbols]);

  // Determine grid layout
  const getGridClass = () => {
    if (selectedSymbols.length === 0) return '';
    if (gridSize === 1) return 'grid-cols-1';
    if (gridSize === 2) return 'grid-cols-1 md:grid-cols-2';
    return 'grid-cols-1 md:grid-cols-2 xl:grid-cols-4';
  };

  // Chart colors (cycling through palette)
  const chartColors = ['#0ea5e9', '#06b6d4', '#10b981', '#f59e0b'];

  return (
    <div className="space-y-6">
      {/* Header and Controls */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.35em] text-sky-400">Price Charts</p>
          <h2 className="mt-1 text-lg font-semibold">1-Minute Candles</h2>
        </div>

        {/* Grid Toggle Buttons */}
        <div className="flex gap-2">
          {[1, 2, 4].map((size) => (
            <button
              key={size}
              onClick={() => setGridSize(size)}
              className={`rounded-lg px-3 py-2 text-sm font-medium transition ${
                gridSize === size
                  ? 'bg-sky-600 text-white'
                  : 'border border-slate-700 bg-slate-950/50 text-slate-300 hover:bg-slate-900'
              }`}
            >
              {size === 1 && '1×1'}
              {size === 2 && '2×1'}
              {size === 4 && '2×2'}
            </button>
          ))}
        </div>
      </div>

      {/* Charts Grid */}
      {selectedSymbols.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-700 p-12 text-center">
          <p className="text-slate-400">Select tickers from the watchlist to view charts</p>
        </div>
      ) : loading ? (
        <div className="rounded-2xl border border-slate-700 bg-slate-950/50 p-8 text-center">
          <p className="text-slate-400">Loading charts...</p>
        </div>
      ) : (
        <div className={`grid gap-4 ${getGridClass()}`}>
          {selectedSymbols.map((symbol, idx) => {
            const data = chartsData[symbol] || [];
            const color = chartColors[idx % chartColors.length];
            const _minPrice = data.length > 0 ? Math.min(...data.map((d) => d.low)) : 0;
            const _maxPrice = data.length > 0 ? Math.max(...data.map((d) => d.high)) : 0;
            const latestClose = data.length > 0 ? data[data.length - 1].close : 0;
            const change =
              data.length > 1
                ? (((latestClose - data[0].open) / data[0].open) * 100).toFixed(2)
                : 0;

            return (
              <div key={symbol} className="rounded-2xl border border-slate-700 bg-slate-950/60 p-4">
                {/* Chart Header */}
                <div className="mb-3 flex items-baseline justify-between">
                  <div>
                    <h3 className="font-semibold text-white">{symbol}</h3>
                    <p className="text-sm text-slate-400">${latestClose.toFixed(2)}</p>
                  </div>
                  <p
                    className={`text-sm font-medium ${
                      change >= 0 ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    {change >= 0 ? '+' : ''}
                    {change}%
                  </p>
                </div>

                {/* Chart */}
                {data.length > 0 ? (
                  <ResponsiveContainer width="100%" height={250}>
                    <AreaChart data={data}>
                      <defs>
                        <linearGradient id={`gradient-${symbol}`} x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={color} stopOpacity={0.3} />
                          <stop offset="95%" stopColor={color} stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(71, 85, 105, 0.3)" />
                      <XAxis
                        dataKey="time"
                        tick={{ fontSize: 12, fill: 'rgba(148, 163, 184, 1)' }}
                        stroke="rgba(71, 85, 105, 1)"
                      />
                      <YAxis
                        domain={['dataMin - 1', 'dataMax + 1']}
                        tick={{ fontSize: 12, fill: 'rgba(148, 163, 184, 1)' }}
                        stroke="rgba(71, 85, 105, 1)"
                      />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: 'rgba(15, 23, 42, 0.9)',
                          border: '1px solid rgba(71, 85, 105, 1)',
                          borderRadius: '8px',
                        }}
                        labelStyle={{ color: 'rgba(226, 232, 240, 1)' }}
                        formatter={(value) => [`$${value.toFixed(2)}`, 'Price']}
                        labelFormatter={(label) => `Time: ${label}`}
                      />
                      <Area
                        type="monotone"
                        dataKey="close"
                        stroke={color}
                        strokeWidth={2}
                        fill={`url(#gradient-${symbol})`}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-[250px] flex items-center justify-center text-slate-400">
                    No data available
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Info Bar */}
      {selectedSymbols.length > 0 && (
        <div className="rounded-lg bg-slate-900/50 border border-slate-700 px-4 py-3 text-xs text-slate-400">
          Showing {selectedSymbols.length} chart
          {selectedSymbols.length > 1 ? 's' : ''} • Data updates every 60 seconds
        </div>
      )}
    </div>
  );
}
