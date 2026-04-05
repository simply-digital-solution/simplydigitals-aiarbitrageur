import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { jsPDF } from 'jspdf';

const API_BASE_URL = 'http://localhost:8000/api/v1';

const fmt = (n) =>
  (n || 0).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const EMPTY_FILTERS = { side: '', symbol: '', qty: '', price: '', value: '', status: '', date: '' };

const COLUMNS = ['Side', 'Symbol', 'Qty', 'Price', 'Value', 'Status', 'Date', 'Time', 'Order ID'];

function rowData(t, symbolMeta) {
  const ts = new Date(t.created_at);
  const exchange = symbolMeta[t.symbol]?.exchangeDisplay || '';
  const symbol = exchange ? `${t.symbol} (${exchange})` : t.symbol;
  return [
    t.side,
    symbol,
    t.qty,
    t.execution_price != null ? (t.execution_price).toFixed(2) : '',
    ((t.execution_price || 0) * t.qty).toFixed(2),
    t.status,
    ts.toLocaleDateString('en-AU', { day: '2-digit', month: 'short', year: 'numeric' }),
    ts.toLocaleTimeString('en-AU', { hour: '2-digit', minute: '2-digit' }),
    t.order_id || 'paper',
  ];
}

function downloadCSV(rows, symbolMeta) {
  const escape = (v) => `"${String(v).replace(/"/g, '""')}"`;
  const lines = [COLUMNS.map(escape).join(',')];
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

  // Title
  doc.setFontSize(14);
  doc.setTextColor(30, 41, 59);
  doc.text('Trade Blotter', margin, margin + 4);
  doc.setFontSize(8);
  doc.setTextColor(100, 116, 139);
  doc.text(`Exported ${new Date().toLocaleString('en-AU')}  ·  ${rows.length} trade${rows.length !== 1 ? 's' : ''}`, margin, margin + 10);

  // Column widths (mm) — must sum to pageW - 2*margin
  const colW = [18, 38, 14, 22, 22, 22, 28, 18, 50];
  const rowH = 7;
  let y = margin + 16;

  // Header row
  doc.setFillColor(15, 23, 42);
  doc.rect(margin, y, pageW - 2 * margin, rowH, 'F');
  doc.setFontSize(7);
  doc.setTextColor(148, 163, 184);
  let x = margin + 2;
  COLUMNS.forEach((col, i) => { doc.text(col, x, y + 4.5); x += colW[i]; });
  y += rowH;

  // Data rows
  rows.forEach((t, idx) => {
    if (y + rowH > doc.internal.pageSize.getHeight() - margin) {
      doc.addPage();
      y = margin;
    }
    if (idx % 2 === 0) {
      doc.setFillColor(30, 41, 59);
      doc.rect(margin, y, pageW - 2 * margin, rowH, 'F');
    }
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

function FilterInput({ value, onChange, align = 'left', placeholder = '…' }) {
  return (
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className={`w-full bg-slate-800/60 border border-slate-600/40 rounded px-1.5 py-1 text-[10px] text-slate-300 placeholder-slate-600 focus:outline-none focus:border-sky-500/60 text-${align}`}
    />
  );
}

export default function TradeBlotter({ symbolMeta = {} }) {
  const [trades, setTrades] = useState([]);
  const [syncStatus, setSyncStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [downloadOpen, setDownloadOpen] = useState(false);
  const downloadRef = useRef(null);

  const setFilter = (key, val) => setFilters((f) => ({ ...f, [key]: val }));
  const clearFilters = () => setFilters(EMPTY_FILTERS);
  const hasFilters = Object.values(filters).some((v) => v !== '');

  const fetchTrades = async () => {
    setLoading(true);
    try {
      const resp = await axios.get(`${API_BASE_URL}/portfolio/trades`);
      setTrades(resp.data || []);
    } catch {
      // leave existing state unchanged
    }
    setLoading(false);
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
      // leave existing state unchanged
    }
    setSyncing(false);
  };

  useEffect(() => {
    fetchTrades();
    checkSyncStatus();
  }, []);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handler = (e) => { if (downloadRef.current && !downloadRef.current.contains(e.target)) setDownloadOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // Apply filters — all are partial, case-insensitive string matches
  const filtered = trades.filter((t) => {
    const value = (t.execution_price || 0) * t.qty;
    const ts = new Date(t.created_at);
    const dateStr = ts.toLocaleDateString('en-AU', { day: '2-digit', month: 'short' });
    const timeStr = ts.toLocaleTimeString('en-AU', { hour: '2-digit', minute: '2-digit' });
    const contains = (field, term) =>
      String(field).toLowerCase().includes(term.toLowerCase().trim());
    return (
      (!filters.side   || contains(t.side, filters.side)) &&
      (!filters.symbol || contains(t.symbol, filters.symbol)) &&
      (!filters.qty    || contains(t.qty, filters.qty)) &&
      (!filters.price  || contains(fmt(t.execution_price || 0), filters.price)) &&
      (!filters.value  || contains(fmt(value), filters.value)) &&
      (!filters.status || contains(t.status, filters.status)) &&
      (!filters.date   || contains(`${dateStr} ${timeStr}`, filters.date))
    );
  });

  const totalValue = filtered.reduce(
    (sum, t) => sum + (t.execution_price || 0) * t.qty * (t.side === 'buy' ? 1 : -1),
    0
  );

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
            <button
              onClick={clearFilters}
              className="rounded-lg border border-slate-600 bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-700 transition"
            >
              Clear Filters
            </button>
          )}

          {/* Download dropdown */}
          <div className="relative" ref={downloadRef}>
            <button
              onClick={() => setDownloadOpen((o) => !o)}
              disabled={filtered.length === 0}
              className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-300 hover:bg-slate-700 transition disabled:opacity-40 flex items-center gap-1.5"
            >
              ↓ Download
              <span className="text-slate-500 text-[10px]">▾</span>
            </button>
            {downloadOpen && (
              <div className="absolute right-0 mt-1 w-36 rounded-xl border border-slate-700 bg-slate-800 shadow-xl z-20 overflow-hidden">
                <button
                  onClick={() => { downloadCSV(filtered, symbolMeta); setDownloadOpen(false); }}
                  className="w-full px-4 py-2.5 text-left text-xs text-slate-300 hover:bg-slate-700 transition"
                >
                  CSV (.csv)
                </button>
                <button
                  onClick={() => { downloadPDF(filtered, symbolMeta); setDownloadOpen(false); }}
                  className="w-full px-4 py-2.5 text-left text-xs text-slate-300 hover:bg-slate-700 transition border-t border-slate-700/60"
                >
                  PDF (.pdf)
                </button>
              </div>
            )}
          </div>

          <button
            onClick={() => { fetchTrades(); checkSyncStatus(); }}
            disabled={loading}
            className="rounded-lg border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-medium text-sky-400 hover:bg-slate-700 transition disabled:opacity-50"
          >
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
          <button
            onClick={syncTrades}
            disabled={syncing}
            className="shrink-0 rounded-lg bg-yellow-600/30 hover:bg-yellow-600/50 border border-yellow-600/40 px-3 py-1.5 text-xs font-semibold text-yellow-300 transition disabled:opacity-50"
          >
            {syncing ? 'Syncing…' : 'Sync Now'}
          </button>
        </div>
      )}
      {syncStatus?.alpaca_connected && syncStatus?.in_sync && (
        <p className="text-[10px] text-emerald-500/70 text-right">✓ In sync with Alpaca</p>
      )}

      {/* Stats row — always reflects full dataset */}
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
        <div className="rounded-xl border border-slate-700/50 bg-slate-900/50 overflow-hidden">

          {/* Column headers + filter inputs */}
          <div className="border-b border-slate-700/50">
            {/* Labels */}
            <div className="grid grid-cols-[80px_1fr_60px_80px_90px_80px_100px] gap-x-3 px-4 pt-2.5 pb-1 text-[10px] uppercase tracking-wider text-slate-500">
              <span>Side</span>
              <span>Symbol</span>
              <span className="text-right">Qty</span>
              <span className="text-right">Price</span>
              <span className="text-right">Value</span>
              <span className="text-center">Status</span>
              <span className="text-right">Date / Time</span>
            </div>
            {/* Filter inputs */}
            <div className="grid grid-cols-[80px_1fr_60px_80px_90px_80px_100px] gap-x-3 px-4 pb-2">
              <FilterInput value={filters.side}   onChange={(v) => setFilter('side', v)}   placeholder="buy / sell" />
              <FilterInput value={filters.symbol} onChange={(v) => setFilter('symbol', v)} placeholder="AAPL…" />
              <FilterInput value={filters.qty}    onChange={(v) => setFilter('qty', v)}    placeholder="5…"    align="right" />
              <FilterInput value={filters.price}  onChange={(v) => setFilter('price', v)}  placeholder="255…"  align="right" />
              <FilterInput value={filters.value}  onChange={(v) => setFilter('value', v)}  placeholder="1,2…"  align="right" />
              <FilterInput value={filters.status} onChange={(v) => setFilter('status', v)} placeholder="fill…" align="center" />
              <FilterInput value={filters.date}   onChange={(v) => setFilter('date', v)}   placeholder="Apr…"  align="right" />
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
                const value = (t.execution_price || 0) * t.qty;
                const ts = new Date(t.created_at);
                return (
                  <div
                    key={t.id}
                    className="grid grid-cols-[80px_1fr_60px_80px_90px_80px_100px] gap-x-3 items-center px-4 py-2.5 text-xs hover:bg-slate-800/40 transition-colors"
                  >
                    {/* Side */}
                    <div className="flex items-center gap-1.5">
                      <span
                        className={`font-bold uppercase px-1.5 py-0.5 rounded text-[10px] ${
                          t.side === 'buy'
                            ? 'bg-emerald-900/40 text-emerald-400'
                            : 'bg-rose-900/40 text-rose-400'
                        }`}
                      >
                        {t.side}
                      </span>
                      {!t.order_id && (
                        <span className="text-[9px] px-1 py-0.5 rounded bg-slate-700/60 text-slate-400">paper</span>
                      )}
                    </div>

                    {/* Symbol */}
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span className="font-semibold truncate">{t.symbol}</span>
                      {symbolMeta[t.symbol]?.exchangeDisplay && (
                        <span className="text-[9px] text-sky-400 shrink-0">{symbolMeta[t.symbol].exchangeDisplay}</span>
                      )}
                    </div>

                    {/* Qty */}
                    <span className="text-right text-slate-300">{t.qty}</span>

                    {/* Price */}
                    <span className="text-right text-slate-300">
                      {t.execution_price != null ? `$${fmt(t.execution_price)}` : '—'}
                    </span>

                    {/* Value */}
                    <span className="text-right font-medium text-slate-200">${fmt(value)}</span>

                    {/* Status */}
                    <span
                      className={`text-center ${
                        t.status === 'filled'   ? 'text-emerald-400' :
                        t.status === 'accepted' ? 'text-sky-400' :
                        t.status === 'pending'  ? 'text-yellow-400' :
                                                  'text-slate-400'
                      }`}
                    >
                      {t.status}
                    </span>

                    {/* Date / Time */}
                    <div className="text-right text-slate-400">
                      <div>{ts.toLocaleDateString('en-AU', { day: '2-digit', month: 'short' })}</div>
                      <div>{ts.toLocaleTimeString('en-AU', { hour: '2-digit', minute: '2-digit' })}</div>
                    </div>
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
