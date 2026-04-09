import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { jsPDF } from 'jspdf';

const API_BASE_URL = 'http://localhost:8000/api/v1';

const fmt = (n) =>
  (n || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// All columns — key ties header/filter/cell together; width is the grid track size
const ALL_COLS = [
  { key: 'side',        label: 'Side',           width: '80px',  defaultHidden: false },
  { key: 'symbol',      label: 'Symbol',         width: '1fr',   defaultHidden: false },
  { key: 'qty',         label: 'Ord Qty',        width: '60px',  defaultHidden: false },
  { key: 'price',       label: 'Ord Price',      width: '90px',  defaultHidden: false },
  { key: 'value',       label: 'Ord Value',      width: '90px',  defaultHidden: false },
  { key: 'filledQty',   label: 'Trd Qty',        width: '60px',  defaultHidden: false },
  { key: 'avgFill',     label: 'Trd Fil Rate',   width: '90px',  defaultHidden: false },
{ key: 'status',      label: 'Status',         width: '80px',  defaultHidden: false },
  { key: 'date',        label: 'Date / Time',    width: '100px', defaultHidden: false },
  { key: 'actions',     label: 'Actions',        width: '120px', defaultHidden: false },
  { key: 'appTradeId',  label: 'App Trade ID',   width: '130px', defaultHidden: true  },
  { key: 'alpacaId',    label: 'Alpaca Trade ID',width: '130px', defaultHidden: true  },
];

const DEFAULT_HIDDEN = new Set(ALL_COLS.filter((c) => c.defaultHidden).map((c) => c.key));

const EMPTY_FILTERS = {
  side: '', symbol: '', qty: '', filledQty: '', avgFill: '', price: '',
  value: '', status: '', date: '', appTradeId: '', alpacaId: '',
};

// CSV/PDF export always includes all columns regardless of visibility
const EXPORT_COLUMNS = ['Side', 'Symbol', 'Ord Qty', 'Ord Price', 'Ord Value', 'Trd Qty', 'Trd Fil Rate', 'Status', 'Date', 'Time', 'App Trade ID', 'Alpaca Trade ID'];

function rowData(t, symbolMeta) {
  const ts = new Date(t.created_at);
  const exchange = symbolMeta[t.symbol]?.exchangeDisplay || '';
  const symbol = exchange ? `${t.symbol} (${exchange})` : t.symbol;
  const ordPrice = t.execution_price ?? t.limit_price ?? t.market_price ?? null;
  return [
    t.side, symbol, t.qty,
    ordPrice != null ? ordPrice.toFixed(2) : '',
    ordPrice != null ? (ordPrice * t.qty).toFixed(2) : '',
    t.filled_qty != null ? t.filled_qty : '',
    t.execution_price != null ? t.execution_price.toFixed(2) : '',
    t.status,
    ts.toLocaleDateString('en-AU', { day: '2-digit', month: 'short', year: 'numeric' }),
    ts.toLocaleTimeString('en-AU', { hour: '2-digit', minute: '2-digit' }),
    t.id,
    t.order_id || 'paper',
  ];
}

function downloadCSV(rows, symbolMeta) {
  const escape = (v) => `"${String(v).replace(/"/g, '""')}"`;
  const lines = [EXPORT_COLUMNS.map(escape).join(',')];
  rows.forEach((t) => lines.push(rowData(t, symbolMeta).map(escape).join(',')));
  const blob = new Blob([lines.join('\r\n')], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `trade_blotter_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

function downloadPDF(rows, symbolMeta) {
  const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
  const margin = 12;
  const pageW = doc.internal.pageSize.getWidth();

  doc.setFontSize(14);
  doc.setTextColor(30, 41, 59);
  doc.text('Trade Blotter', margin, margin + 4);
  doc.setFontSize(8);
  doc.setTextColor(100, 116, 139);
  doc.text(`Exported ${new Date().toLocaleString('en-AU')}  ·  ${rows.length} trade${rows.length !== 1 ? 's' : ''}`, margin, margin + 10);

  const colW = [18, 38, 14, 22, 22, 22, 28, 18, 50];
  const rowH = 7;
  let y = margin + 16;

  doc.setFillColor(15, 23, 42);
  doc.rect(margin, y, pageW - 2 * margin, rowH, 'F');
  doc.setFontSize(7);
  doc.setTextColor(148, 163, 184);
  let x = margin + 2;
  EXPORT_COLUMNS.forEach((col, i) => { doc.text(col, x, y + 4.5); x += colW[i]; });
  y += rowH;

  rows.forEach((t, idx) => {
    if (y + rowH > doc.internal.pageSize.getHeight() - margin) { doc.addPage(); y = margin; }
    if (idx % 2 === 0) { doc.setFillColor(30, 41, 59); doc.rect(margin, y, pageW - 2 * margin, rowH, 'F'); }
    doc.setFontSize(7);
    doc.setTextColor(t.side === 'buy' ? 52 : 248, t.side === 'buy' ? 211 : 113, t.side === 'buy' ? 153 : 113);
    const cells = rowData(t, symbolMeta);
    x = margin + 2;
    cells.forEach((cell, i) => {
      if (i > 0) doc.setTextColor(203, 213, 225);
      doc.text(String(cell), x, y + 4.5, { maxWidth: colW[i] - 2 });
      x += colW[i];
    });
    y += rowH;
  });

  doc.save(`trade_blotter_${new Date().toISOString().slice(0, 10)}.pdf`);
}

function FilterInput({ name, value, onChange, align = 'left', placeholder = '…' }) {
  return (
    <input
      type="text"
      name={name}
      autoComplete="off"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className={`w-full bg-slate-800/60 border border-slate-600/40 rounded px-1.5 py-1 text-[10px] text-slate-300 placeholder-slate-600 focus:outline-none focus:border-sky-500/60 text-${align}`}
    />
  );
}

export default function TradeBlotter({
  trades = [],
  syncStatus = null,
  loading = false,
  symbolMeta = {},
  onRefresh = () => {},
  onOpenTradePanel = () => {},
}) {
  const [syncing, setSyncing] = useState(false);
  const [actionLoading, setActionLoading] = useState({});
  const [tickerMeta, setTickerMeta] = useState({});

  // Fetch ticker metadata for symbols in trades (once per unique symbol)
  useEffect(() => {
    const symbols = [...new Set(trades.map((t) => t.symbol))];
    symbols.forEach(async (sym) => {
      if (tickerMeta[sym]) return;
      try {
        const resp = await axios.get(`${API_BASE_URL}/tickers/${sym}`);
        setTickerMeta((prev) => ({ ...prev, [sym]: resp.data }));
      } catch { /* leave blank */ }
    });
  }, [trades]);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [hiddenCols, setHiddenCols] = useState(DEFAULT_HIDDEN);
  const [downloadOpen, setDownloadOpen] = useState(false);
  const [colsOpen, setColsOpen] = useState(false);
  const downloadRef = useRef(null);
  const colsRef = useRef(null);

  const visibleCols = ALL_COLS.filter((c) => !hiddenCols.has(c.key));
  const gridStyle = { gridTemplateColumns: visibleCols.map((c) => c.width).join(' ') };

  const toggleCol = (key) =>
    setHiddenCols((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });

  const setFilter = (key, val) => setFilters((f) => ({ ...f, [key]: val }));
  const clearFilters = () => setFilters(EMPTY_FILTERS);
  const hasFilters = Object.values(filters).some((v) => v !== '');

  const withActionLoading = async (tradeId, fn) => {
    setActionLoading((prev) => ({ ...prev, [tradeId]: true }));
    try { await fn(); } finally {
      setActionLoading((prev) => ({ ...prev, [tradeId]: false }));
    }
  };

  const handleCancel = (trade) => withActionLoading(trade.id, async () => {
    await axios.post(`${API_BASE_URL}/portfolio/trades/${trade.id}/cancel`);
    onRefresh();
  });

  const handleQuickTrade = (trade, side) => {
    const meta = tickerMeta[trade.symbol] || {};
    onOpenTradePanel({
      symbol: trade.symbol,
      side: side.toUpperCase(),
      qty: trade.qty,
      name: meta.long_name || meta.name || trade.symbol,
      exchangeDisplay: meta.exchange_display || null,
      typeDisplay: meta.type_display || null,
    });
  };

  const syncTrades = async () => {
    setSyncing(true);
    try { await axios.post(`${API_BASE_URL}/portfolio/sync-trades`); onRefresh(); }
    catch { /* leave unchanged */ }
    setSyncing(false);
  };

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handler = (e) => {
      if (downloadRef.current && !downloadRef.current.contains(e.target)) setDownloadOpen(false);
      if (colsRef.current && !colsRef.current.contains(e.target)) setColsOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const HIDDEN_STATUSES = new Set(['expired', 'withdrawn', 'canceled']);

  const filtered = trades
    .filter((t) => !HIDDEN_STATUSES.has(t.status))
    .filter((t) => {
      const value = (t.execution_price ?? t.limit_price ?? t.market_price ?? 0) * t.qty;
      const ts = new Date(t.created_at);
      const dateStr = ts.toLocaleDateString('en-AU', { day: '2-digit', month: 'short' });
      const timeStr = ts.toLocaleTimeString('en-AU', { hour: '2-digit', minute: '2-digit' });
      const contains = (field, term) => String(field).toLowerCase().includes(term.toLowerCase().trim());
      return (
        (!filters.side      || contains(t.side, filters.side)) &&
        (!filters.symbol    || contains(t.symbol, filters.symbol)) &&
        (!filters.qty       || contains(t.qty, filters.qty)) &&
        (!filters.filledQty || contains(String(t.filled_qty ?? ''), filters.filledQty)) &&
        (!filters.avgFill   || contains(fmt(t.execution_price || 0), filters.avgFill)) &&
        (!filters.price     || contains(fmt(t.execution_price ?? t.limit_price ?? t.market_price ?? 0), filters.price)) &&
        (!filters.value     || contains(fmt(value), filters.value)) &&
        (!filters.status    || contains(t.status, filters.status)) &&
        (!filters.date      || contains(`${dateStr} ${timeStr}`, filters.date)) &&
        (!filters.appTradeId || contains(t.id, filters.appTradeId)) &&
        (!filters.alpacaId   || contains(t.order_id || '', filters.alpacaId))
      );
    })
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

  const _executedStatuses = new Set(['accepted', 'filled']);
  const totalValue = filtered
    .filter((t) => _executedStatuses.has(t.status))
    .reduce(
      (sum, t) => sum + (t.execution_price ?? t.limit_price ?? t.market_price ?? 0) * t.qty * (t.side === 'buy' ? -1 : 1),
      0
    );

  // Helper: render a cell only if its column is visible
  const col = (key, node) => hiddenCols.has(key) ? null : node;

  return (
    <div className="space-y-4">
      {/* Title row */}
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.35em] text-sky-400">Portfolio</p>
          <h2 className="mt-0.5 text-lg font-semibold">Trade Blotter</h2>
        </div>
        <div className="flex items-center gap-2">
          {hasFilters && (
            <button onClick={clearFilters}
              className="rounded-lg border border-slate-600 bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-700 transition">
              Clear Filters
            </button>
          )}

          {/* Column visibility toggle */}
          <div className="relative" ref={colsRef}>
            <button onClick={() => setColsOpen((o) => !o)}
              className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-700 transition flex items-center gap-1.5">
              Columns
              <span className="text-slate-500 text-[10px]">▾</span>
            </button>
            {colsOpen && (
              <div className="absolute right-0 mt-1 w-44 rounded-xl border border-slate-700 bg-slate-800 shadow-xl z-20 overflow-hidden py-1">
                {ALL_COLS.map((c) => (
                  <label key={c.key}
                    className="flex items-center gap-2.5 px-3 py-1.5 text-xs text-slate-300 hover:bg-slate-700 cursor-pointer transition">
                    <input
                      type="checkbox"
                      checked={!hiddenCols.has(c.key)}
                      onChange={() => toggleCol(c.key)}
                      className="accent-sky-500"
                    />
                    {c.label}
                  </label>
                ))}
              </div>
            )}
          </div>

          {/* Download dropdown */}
          <div className="relative" ref={downloadRef}>
            <button onClick={() => setDownloadOpen((o) => !o)} disabled={filtered.length === 0}
              className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-700 transition disabled:opacity-40 flex items-center gap-1.5">
              ↓ Download
              <span className="text-slate-500 text-[10px]">▾</span>
            </button>
            {downloadOpen && (
              <div className="absolute right-0 mt-1 w-36 rounded-xl border border-slate-700 bg-slate-800 shadow-xl z-20 overflow-hidden">
                <button onClick={() => { downloadCSV(filtered, symbolMeta); setDownloadOpen(false); }}
                  className="w-full px-4 py-2.5 text-left text-xs text-slate-300 hover:bg-slate-700 transition">
                  CSV (.csv)
                </button>
                <button onClick={() => { downloadPDF(filtered, symbolMeta); setDownloadOpen(false); }}
                  className="w-full px-4 py-2.5 text-left text-xs text-slate-300 hover:bg-slate-700 transition border-t border-slate-700/60">
                  PDF (.pdf)
                </button>
              </div>
            )}
          </div>

          <button onClick={onRefresh} disabled={loading}
            className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-medium text-sky-400 hover:bg-slate-700 transition disabled:opacity-50">
            {loading ? 'Refreshing…' : 'Refresh'}
          </button>
        </div>
      </div>

      {/* Sync warning */}
      {syncStatus?.alpaca_connected && !syncStatus?.in_sync && (
        <div className="rounded-xl border border-yellow-600/40 bg-yellow-900/20 p-3 flex items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold text-yellow-400">Out of sync with Alpaca</p>
            <p className="text-[10px] text-yellow-300/70 mt-0.5">
              {syncStatus.missing_count} order{syncStatus.missing_count !== 1 ? 's' : ''} in Alpaca not recorded locally
            </p>
          </div>
          <button onClick={syncTrades} disabled={syncing}
            className="shrink-0 rounded-lg bg-yellow-600/30 hover:bg-yellow-600/50 border border-yellow-600/40 px-3 py-1.5 text-xs font-semibold text-yellow-300 transition disabled:opacity-50">
            {syncing ? 'Syncing…' : 'Sync Now'}
          </button>
        </div>
      )}
      {syncStatus?.alpaca_connected && syncStatus?.in_sync && (
        <p className="text-[10px] text-emerald-500/70 text-right">✓ In sync with Alpaca</p>
      )}

      {/* Stats row */}
      {trades.length > 0 && (
        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-xl border border-slate-700/50 bg-slate-900/50 p-3 text-center">
            <p className="text-xs text-slate-400">Total Trades</p>
            <p className="mt-1 text-lg font-semibold">
              {filtered.length}
              {hasFilters && <span className="text-xs text-slate-500 ml-1">/ {trades.length}</span>}
            </p>
          </div>
          <div className="rounded-xl border border-slate-700/50 bg-slate-900/50 p-3 text-center">
            <p className="text-xs text-slate-400">Buys</p>
            <p className="mt-1 text-lg font-semibold text-emerald-400">
              {filtered.filter((t) => t.side === 'buy').length}
            </p>
          </div>
          <div className="rounded-xl border border-slate-700/50 bg-slate-900/50 p-3 text-center">
            <p className="text-xs text-slate-400">Sells</p>
            <p className="mt-1 text-lg font-semibold text-rose-400">
              {filtered.filter((t) => t.side === 'sell').length}
            </p>
          </div>
        </div>
      )}

      {/* Table */}
      {trades.length === 0 ? (
        <div className="rounded-xl border border-slate-700/50 bg-slate-900/50 p-8 text-center text-sm text-slate-500">
          {loading ? 'Loading trades…' : 'No trades yet'}
        </div>
      ) : (
        <div className="rounded-xl border border-slate-700/50 bg-slate-900/50 overflow-hidden overflow-x-auto">

          {/* Column headers + filter inputs */}
          <div className="border-b border-slate-700/50 min-w-max">
            <div className="grid gap-x-3 px-4 pt-2.5 pb-1 text-[10px] uppercase tracking-wider text-slate-500" style={gridStyle}>
              {visibleCols.map((c) => (
                <span key={c.key} className={
                  c.key === 'status' ? 'text-center' :
                  c.key === 'actions' || c.key === 'appTradeId' || c.key === 'alpacaId' ? 'text-left' :
                  ['side', 'symbol'].includes(c.key) ? '' : 'text-right'
                }>
                  {c.label}
                </span>
              ))}
            </div>
            <div className="grid gap-x-3 px-4 pb-2" style={gridStyle}>
              {visibleCols.map((c) => {
                const alignMap = { side: 'left', symbol: 'left', status: 'center', actions: 'left', appTradeId: 'left', alpacaId: 'left' };
                const align = alignMap[c.key] || 'right';
                if (c.key === 'actions') return <div key={c.key} />;
                return (
                  <FilterInput key={c.key} name={`filter_${c.key}`} value={filters[c.key] ?? ''} onChange={(v) => setFilter(c.key, v)}
                    align={align} placeholder="…" />
                );
              })}
            </div>
          </div>

          {/* Rows */}
          <div className="divide-y divide-slate-700/30">
            {filtered.length === 0 ? (
              <div className="px-4 py-6 text-center text-xs text-slate-500">
                No trades match the current filters
              </div>
            ) : (
              filtered.map((t) => {
                const ordPrice = t.execution_price ?? t.limit_price ?? t.market_price ?? null;
                const value = (ordPrice ?? 0) * t.qty;
                const ts = new Date(t.created_at);
                return (
                  <div key={t.id}
                    className="grid gap-x-3 items-center px-4 py-2.5 text-xs hover:bg-slate-800/40 transition-colors min-w-max" style={gridStyle}>

                    {col('side', (
                      <div className="flex items-center gap-1.5">
                        <span className={`font-bold uppercase px-1.5 py-0.5 rounded text-[10px] ${
                          t.side === 'buy' ? 'bg-emerald-900/40 text-emerald-400' : 'bg-rose-900/40 text-rose-400'
                        }`}>{t.side}</span>
                        {!t.order_id && <span className="text-[9px] px-1 py-0.5 rounded bg-slate-700/60 text-slate-400">paper</span>}
                      </div>
                    ))}

                    {col('symbol', (
                      <div className="flex items-center gap-1.5 min-w-0">
                        <span className="font-semibold truncate">{t.symbol}</span>
                        {symbolMeta[t.symbol]?.exchangeDisplay && (
                          <span className="text-[9px] text-sky-400 shrink-0">{symbolMeta[t.symbol].exchangeDisplay}</span>
                        )}
                      </div>
                    ))}

                    {col('qty',       <span className="text-right text-slate-300">{t.qty}</span>)}

                    {col('price', (
                      <span className="text-right text-slate-300">
                        {t.execution_price != null
                          ? `$${fmt(t.execution_price)}`
                          : t.limit_price != null
                            ? <span className="text-sky-400">${fmt(t.limit_price)} <span className="text-[9px] text-slate-500">lmt</span></span>
                            : t.market_price != null
                              ? <span className="text-slate-400">${fmt(t.market_price)} <span className="text-[9px] text-slate-500">mkt</span></span>
                              : '—'}
                      </span>
                    ))}

                    {col('value',    <span className="text-right font-medium text-slate-200">{ordPrice != null ? `$${fmt(value)}` : '—'}</span>)}

                    {col('filledQty', <span className="text-right text-slate-300">{t.filled_qty != null ? t.filled_qty : '—'}</span>)}
                    {col('avgFill',   <span className="text-right text-slate-300">{t.execution_price != null ? `$${fmt(t.execution_price)}` : '—'}</span>)}

                    {col('status', (
                      <span className={`text-center font-medium ${
                        t.status === 'accepted'  ? 'text-emerald-400' :
                        t.status === 'filled'    ? 'text-emerald-400' :
                        t.status === 'reached'   ? 'text-sky-400' :
                        t.status === 'not_sent'  ? 'text-yellow-400' :
                        t.status === 'withdrawn' ? 'text-slate-500' :
                        t.status === 'canceled'  ? 'text-rose-400' :
                        t.status === 'expired'   ? 'text-orange-400' :
                        t.status === 'rejected'  ? 'text-rose-400' :
                                                   'text-slate-400'
                      }`}>
                        {t.status === 'not_sent' ? 'not sent' : t.status}
                      </span>
                    ))}

                    {col('date', (
                      <div className="text-right text-slate-400">
                        <div>{ts.toLocaleDateString('en-AU', { day: '2-digit', month: 'short' })}</div>
                        <div>{ts.toLocaleTimeString('en-AU', { hour: '2-digit', minute: '2-digit' })}</div>
                      </div>
                    ))}

                    {col('actions', (
                      <div className="flex items-center justify-center gap-1">
                        {!['accepted', 'filled', 'canceled', 'withdrawn', 'expired', 'rejected'].includes(t.status) && (
                          <button onClick={() => handleCancel(t)} disabled={actionLoading[t.id]}
                            className="px-2 py-1 rounded text-[10px] font-semibold bg-rose-900/30 text-rose-400 border border-rose-700/40 hover:bg-rose-900/60 disabled:opacity-40 transition">
                            {actionLoading[t.id] ? '…' : 'Cancel'}
                          </button>
                        )}
                        {(t.status === 'accepted' || t.status === 'filled') && !t.order_id && (
                          <button onClick={() => handleCancel(t)} disabled={actionLoading[t.id]}
                            className="px-2 py-1 rounded text-[10px] font-semibold bg-slate-700/50 text-slate-400 border border-slate-600/40 hover:bg-slate-700 disabled:opacity-40 transition">
                            {actionLoading[t.id] ? '…' : 'Withdraw'}
                          </button>
                        )}
                        {(t.status === 'accepted' || t.status === 'filled') && t.side === 'buy' && t.order_id && (
                          <button onClick={() => handleQuickTrade(t, 'sell')} disabled={actionLoading[t.id]}
                            className="px-2 py-1 rounded text-[10px] font-semibold bg-rose-900/30 text-rose-400 border border-rose-700/40 hover:bg-rose-900/60 disabled:opacity-40 transition">
                            {actionLoading[t.id] ? '…' : 'Sell'}
                          </button>
                        )}
                        {(t.status === 'accepted' || t.status === 'filled') && t.side === 'sell' && t.order_id && (
                          <button onClick={() => handleQuickTrade(t, 'buy')} disabled={actionLoading[t.id]}
                            className="px-2 py-1 rounded text-[10px] font-semibold bg-emerald-900/30 text-emerald-400 border border-emerald-700/40 hover:bg-emerald-900/60 disabled:opacity-40 transition">
                            {actionLoading[t.id] ? '…' : 'Buy'}
                          </button>
                        )}
                      </div>
                    ))}

                    {col('appTradeId', (
                      <span className="text-left text-[10px] text-slate-500 font-mono truncate" title={t.id}>{t.id}</span>
                    ))}
                    {col('alpacaId', (
                      <span className="text-left text-[10px] text-slate-500 font-mono truncate" title={t.order_id || ''}>
                        {t.order_id || <span className="text-slate-600">paper</span>}
                      </span>
                    ))}

                  </div>
                );
              })
            )}
          </div>

          {/* Footer */}
          <div className="flex justify-between items-center border-t border-slate-700/50 px-4 py-2 text-xs text-slate-400">
            <span>
              {filtered.length} trade{filtered.length !== 1 ? 's' : ''}
              {hasFilters && ` (filtered from ${trades.length})`}
            </span>
            <span>
              Net traded value:{' '}
              <span className={totalValue >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                ${fmt(Math.abs(totalValue))}
              </span>
            </span>
          </div>
        </div>
      )}
    </div>
  );
}