import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';

const API_BASE_URL = 'http://localhost:8000/api/v1';
const CHART_COLORS = ['#0ea5e9', '#10b981', '#f59e0b', '#e879f9', '#f87171', '#34d399'];

function mergeChartsData(chartsData, symbols) {
  if (symbols.length === 0) return [];
  const tsSet = new Set();
  for (const sym of symbols) {
    (chartsData[sym] || []).forEach((bar) => tsSet.add(bar.time));
  }
  const times = Array.from(tsSet).sort();
  const lookup = {};
  const openPrice = {};
  for (const sym of symbols) {
    const bars = chartsData[sym] || [];
    lookup[sym] = {};
    bars.forEach((bar) => { lookup[sym][bar.time] = bar.close; });
    openPrice[sym] = bars.length > 0 ? bars[0].open : null;
  }
  return times.map((time) => {
    const point = { time };
    for (const sym of symbols) {
      const close = lookup[sym][time];
      const base = openPrice[sym];
      if (close != null && base != null && base !== 0) {
        point[sym] = parseFloat((((close - base) / base) * 100).toFixed(3));
      }
    }
    return point;
  });
}

function generateMockData() {
  const now = new Date();
  let basePrice = Math.random() * 300 + 50;
  const open = basePrice;
  return Array.from({ length: 60 }, (_, i) => {
    const time = new Date(now.getTime() - (60 - i) * 60000);
    basePrice += (Math.random() - 0.5) * 2;
    return {
      time: time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
      ts: time.toISOString(),
      open,
      close: basePrice,
    };
  });
}

const TOOLTIP_STYLE = {
  contentStyle: {
    backgroundColor: 'rgba(15, 23, 42, 0.95)',
    border: '1px solid rgba(71, 85, 105, 1)',
    borderRadius: '8px',
  },
  labelStyle: { color: 'rgba(226, 232, 240, 1)', marginBottom: 4 },
};

const AXIS_PROPS = {
  tick: { fontSize: 11, fill: 'rgba(148, 163, 184, 1)' },
  stroke: 'rgba(71, 85, 105, 1)',
};

export default function ChartGrid({ selectedSymbols, onPricesUpdated, symbolMeta = {} }) {
  const [chartsData, setChartsData] = useState({});
  const [prevCloses, setPrevCloses] = useState({});
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('pct');
  const [chartScale, setChartScale] = useState(1);
  const [containerWidth, setContainerWidth] = useState(0);
  const pctScrollRef = useRef(null);
  const tickerScrollRef = useRef(null);
  const containerRef = useRef(null);
  const pinchStartDistRef = useRef(null);
  const pinchStartScaleRef = useRef(1);

  // At scale 1 the chart fills the container exactly (undefined = no min-width override)
  const chartMinWidth = chartScale > 1 ? containerWidth * chartScale : undefined;

  // Observe container width so scale multiplier is based on real pixels
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(([entry]) => setContainerWidth(entry.contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const activeScrollRef = activeTab === 'pct' ? pctScrollRef : tickerScrollRef;

  const scrollToRight = () => {
    const el = activeScrollRef.current;
    if (el) el.scrollLeft = el.scrollWidth;
  };

  // Attach pinch handlers to whichever scroll container is active
  useEffect(() => {
    const el = activeScrollRef.current;
    if (!el) return;

    const onTouchStart = (e) => {
      if (e.touches.length !== 2) return;
      const dx = e.touches[0].clientX - e.touches[1].clientX;
      const dy = e.touches[0].clientY - e.touches[1].clientY;
      pinchStartDistRef.current = Math.hypot(dx, dy);
      pinchStartScaleRef.current = chartScale;
    };

    const onTouchMove = (e) => {
      if (e.touches.length !== 2 || pinchStartDistRef.current === null) return;
      e.preventDefault();
      const dx = e.touches[0].clientX - e.touches[1].clientX;
      const dy = e.touches[0].clientY - e.touches[1].clientY;
      const dist = Math.hypot(dx, dy);
      const ratio = dist / pinchStartDistRef.current;
      const next = Math.min(Math.max(pinchStartScaleRef.current * ratio, 1), 5);
      setChartScale(next);
    };

    const onTouchEnd = () => { pinchStartDistRef.current = null; };

    el.addEventListener('touchstart', onTouchStart, { passive: true });
    el.addEventListener('touchmove', onTouchMove, { passive: false });
    el.addEventListener('touchend', onTouchEnd, { passive: true });
    return () => {
      el.removeEventListener('touchstart', onTouchStart);
      el.removeEventListener('touchmove', onTouchMove);
      el.removeEventListener('touchend', onTouchEnd);
    };
  }, [activeTab, chartScale]);

  // Reset scale + tab when symbols change
  useEffect(() => { setActiveTab('pct'); setChartScale(1); }, [selectedSymbols]);

  // Scroll to right whenever data, tab, or scale changes
  useEffect(() => { scrollToRight(); }, [activeTab, chartsData, chartScale]);

  const fetchChartDataInitial = async () => {
    if (selectedSymbols.length === 0) return;
    setLoading(true);
    try {
      const data = {};
      const closes = {};
      for (const symbol of selectedSymbols) {
        try {
          const [intradayResp, histResp] = await Promise.all([
            axios.get(`${API_BASE_URL}/prices/${symbol}/intraday-1min?limit=60`),
            axios.get(`${API_BASE_URL}/prices/${symbol}/history?range=5D`),
          ]);
          data[symbol] = (intradayResp.data || [])
            .map((bar) => ({
              time: new Date(bar.ts).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
              ts: bar.ts,
              open: bar.open,
              close: bar.close,
            }))
            .sort((a, b) => new Date(a.ts) - new Date(b.ts));
          const histBars = (histResp.data || []).sort((a, b) => new Date(a.date) - new Date(b.date));
          if (histBars.length > 0) {
            closes[symbol] = histBars[histBars.length - 1].close;
          }
        } catch {
          data[symbol] = generateMockData();
        }
      }
      setChartsData(data);
      setPrevCloses(closes);
      const priceMap = {};
      for (const sym of selectedSymbols) {
        const bars = data[sym] || [];
        if (bars.length > 0) {
          priceMap[sym] = {
            current: bars[bars.length - 1].close,
            dayOpen: bars[0].open,
            prevClose: closes[sym] ?? null,
          };
        }
      }
      onPricesUpdated?.(priceMap);
    } catch (err) {
      console.error('Error fetching chart data:', err);
    }
    setLoading(false);
  };

  const appendChartData = async () => {
    if (selectedSymbols.length === 0) return;
    let didUpdate = false;
    try {
      for (const symbol of selectedSymbols) {
        try {
          const resp = await axios.get(`${API_BASE_URL}/prices/${symbol}/intraday-1min?limit=5`);
          const newBars = (resp.data || [])
            .map((bar) => ({
              time: new Date(bar.ts).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
              ts: bar.ts,
              open: bar.open,
              close: bar.close,
            }))
            .sort((a, b) => new Date(a.ts) - new Date(b.ts));
          setChartsData((current) => {
            const existing = current[symbol] || [];
            const lastTs = existing.length > 0 ? existing[existing.length - 1].ts : null;
            const barsToAdd = newBars.filter((bar) => !lastTs || new Date(bar.ts) > new Date(lastTs));
            if (barsToAdd.length === 0) return current;
            didUpdate = true;
            return { ...current, [symbol]: [...existing, ...barsToAdd].slice(-60) };
          });
        } catch (err) {
          console.error(`Error appending data for ${symbol}:`, err);
        }
      }
    } catch (err) {
      console.error('Error appending chart data:', err);
    }
    if (didUpdate) {
      setChartsData((current) => {
        const priceMap = {};
        for (const sym of selectedSymbols) {
          const bars = current[sym] || [];
          if (bars.length > 0) {
            priceMap[sym] = {
              current: bars[bars.length - 1].close,
              dayOpen: bars[0].open,
              prevClose: prevCloses[sym] ?? null,
            };
          }
        }
        onPricesUpdated?.(priceMap);
        return current;
      });
    }
  };

  useEffect(() => { fetchChartDataInitial(); }, [selectedSymbols]);
  useEffect(() => {
    const interval = setInterval(appendChartData, 60000);
    return () => clearInterval(interval);
  }, [selectedSymbols]);

  const stats = selectedSymbols.map((sym, idx) => {
    const bars = chartsData[sym] || [];
    const latestClose = bars.length > 0 ? bars[bars.length - 1].close : 0;
    const change = bars.length > 1
      ? (((latestClose - bars[0].open) / bars[0].open) * 100).toFixed(2)
      : '0.00';
    return { sym, color: CHART_COLORS[idx % CHART_COLORS.length], latestClose, change };
  });

  const merged = mergeChartsData(chartsData, selectedSymbols);
  const activeStat = stats.find((s) => s.sym === activeTab);
  const activeData = activeTab !== 'pct' ? (chartsData[activeTab] || []) : [];

  const tabs = [
    { id: 'pct', label: '% Change' },
    ...stats.map(({ sym, color, latestClose, change }) => ({ id: sym, label: sym, color, latestClose, change })),
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <p className="text-xs uppercase tracking-[0.35em] text-sky-400">Price Charts</p>
        <h2 className="mt-1 text-lg font-semibold">1-Minute Candles</h2>
      </div>

      {selectedSymbols.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-700 p-12 text-center">
          <p className="text-slate-400">Select tickers from the watchlist to view charts</p>
        </div>
      ) : loading ? (
        <div className="rounded-2xl border border-slate-700 bg-slate-950/50 p-8 text-center">
          <p className="text-slate-400">Loading chart...</p>
        </div>
      ) : (
        <div className="rounded-2xl border border-slate-700 bg-slate-950/60">
          {/* Mobile: ticker dropdown */}
          <div className="block sm:hidden border-b border-slate-700 p-3">
            <select
              value={activeTab}
              onChange={(e) => setActiveTab(e.target.value)}
              className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-white outline-none focus:border-sky-500"
            >
              {tabs.map(({ id, label, change }) => (
                <option key={id} value={id}>
                  {id === 'pct' ? '% Change (All)' : `${label}${change !== undefined ? ` (${change >= 0 ? '+' : ''}${change}%)` : ''}`}
                </option>
              ))}
            </select>
          </div>

          {/* Desktop: tab bar */}
          <div className="hidden sm:flex overflow-x-auto border-b border-slate-700">
            {tabs.map(({ id, label, color, latestClose, change }) => {
              const isActive = activeTab === id;
              return (
                <button
                  key={id}
                  onClick={() => setActiveTab(id)}
                  className={`flex shrink-0 items-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2 ${
                    isActive
                      ? 'border-sky-500 text-white'
                      : 'border-transparent text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {id === 'pct' ? (
                    <span>% Change</span>
                  ) : (
                    <>
                      <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: color }} />
                      <span>{label}</span>
                      {symbolMeta[id]?.exchangeDisplay && (
                        <span className="text-[10px] text-sky-400 leading-none">{symbolMeta[id].exchangeDisplay}</span>
                      )}
                      {latestClose > 0 && (
                        <span className={`text-xs ${change >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                          {change >= 0 ? '+' : ''}{change}%
                        </span>
                      )}
                    </>
                  )}
                </button>
              );
            })}
          </div>

          <div ref={containerRef} className="p-4">
            {/* % Change tab — overlaid multi-ticker chart */}
            {activeTab === 'pct' && (
              <>
                <div className="mb-4 flex flex-wrap gap-3">
                  {stats.map(({ sym, color, latestClose, change }) => (
                    <div key={sym} className="flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5">
                      <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
                      <span className="font-semibold text-white">{sym}</span>
                      {symbolMeta[sym]?.exchangeDisplay && (
                        <span className="text-[10px] text-sky-400 leading-none">{symbolMeta[sym].exchangeDisplay}</span>
                      )}
                      <span className="text-sm text-slate-400">${latestClose.toFixed(2)}</span>
                      <span className={`text-sm font-medium ${change >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {change >= 0 ? '+' : ''}{change}%
                      </span>
                    </div>
                  ))}
                </div>
                <div ref={pctScrollRef} className="overflow-x-auto -mx-1 px-1">
                  <div style={{ minWidth: chartMinWidth }}>
                    <ResponsiveContainer width="100%" height={320}>
                      <AreaChart data={merged}>
                        <defs>
                          {stats.map(({ sym, color }) => (
                            <linearGradient key={sym} id={`gradient-pct-${sym}`} x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor={color} stopOpacity={0.25} />
                              <stop offset="95%" stopColor={color} stopOpacity={0} />
                            </linearGradient>
                          ))}
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(71, 85, 105, 0.3)" />
                        <XAxis dataKey="time" {...AXIS_PROPS} />
                        <YAxis tickFormatter={(v) => `${v > 0 ? '+' : ''}${v}%`} {...AXIS_PROPS} />
                        <Tooltip
                          {...TOOLTIP_STYLE}
                          formatter={(value, name) => [`${value >= 0 ? '+' : ''}${value}%`, name]}
                          labelFormatter={(label) => `Time: ${label}`}
                        />
                        <Legend
                          wrapperStyle={{ fontSize: 12, paddingTop: 8 }}
                          formatter={(value) => <span style={{ color: 'rgba(226, 232, 240, 1)' }}>{value}</span>}
                        />
                        {stats.map(({ sym, color }) => (
                          <Area key={sym} type="monotone" dataKey={sym} stroke={color} strokeWidth={2}
                            fill={`url(#gradient-pct-${sym})`} connectNulls dot={false} activeDot={false} />
                        ))}
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </>
            )}

            {/* Per-ticker tab — raw price chart */}
            {activeTab !== 'pct' && activeStat && (
              <>
                <div className="mb-4 flex items-baseline justify-between">
                  <div>
                    <span className="text-lg font-semibold text-white">{activeStat.sym}</span>
                    <span className="ml-3 text-slate-400">${activeStat.latestClose.toFixed(2)}</span>
                  </div>
                  <span className={`text-sm font-medium ${activeStat.change >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {activeStat.change >= 0 ? '+' : ''}{activeStat.change}% from open
                  </span>
                </div>
                {activeData.length > 0 ? (
                  <div ref={tickerScrollRef} className="overflow-x-auto -mx-1 px-1">
                    <div style={{ minWidth: chartMinWidth }}>
                      <ResponsiveContainer width="100%" height={320}>
                        <AreaChart data={activeData}>
                          <defs>
                            <linearGradient id={`gradient-${activeStat.sym}`} x1="0" y1="0" x2="0" y2="1">
                              <stop offset="5%" stopColor={activeStat.color} stopOpacity={0.3} />
                              <stop offset="95%" stopColor={activeStat.color} stopOpacity={0} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid strokeDasharray="3 3" stroke="rgba(71, 85, 105, 0.3)" />
                          <XAxis dataKey="time" {...AXIS_PROPS} />
                          <YAxis domain={['dataMin - 1', 'dataMax + 1']} tickFormatter={(v) => `$${v.toFixed(2)}`} {...AXIS_PROPS} />
                          <Tooltip
                            {...TOOLTIP_STYLE}
                            formatter={(value) => [`$${value.toFixed(2)}`, 'Price']}
                            labelFormatter={(label) => `Time: ${label}`}
                          />
                          <Area type="monotone" dataKey="close" stroke={activeStat.color} strokeWidth={2}
                            fill={`url(#gradient-${activeStat.sym})`} dot={false} activeDot={false} />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                ) : (
                  <div className="flex h-[320px] items-center justify-center text-slate-400">
                    No data available
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {selectedSymbols.length > 0 && (
        <div className="rounded-lg bg-slate-900/50 border border-slate-700 px-4 py-3 text-xs text-slate-400">
          {selectedSymbols.length} ticker{selectedSymbols.length > 1 ? 's' : ''} • Data updates every 60 seconds
        </div>
      )}
    </div>
  );
}
