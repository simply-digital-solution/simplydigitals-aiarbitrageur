import { useState, useEffect, useRef } from 'react';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api/v1';

const TRADE_LIMITS = {
  MAX_POSITION_EXPOSURE_PCT: 10.0,
  MAX_DAILY_LOSS_PCT: 5.0,
  MAX_ORDER_SIZE_PCT: 2.0,
};

const STATUS_LABEL = { not_sent: 'Not Sent', reached: 'Reached Alpaca', accepted: 'Accepted' };
const STATUS_BORDER = {
  not_sent: 'border-yellow-600 bg-yellow-900/20 text-yellow-200',
  reached:  'border-sky-600 bg-sky-900/20 text-sky-200',
  accepted: 'border-emerald-600 bg-emerald-900/20 text-emerald-200',
};

export default function TradePanel({ selectedSymbols }) {
  const [formData, setFormData] = useState({
    symbol: selectedSymbols[0] || '',
    side: 'BUY',
    qty: 10,
    limitPrice: null,
    marketOrder: true,
  });

  // Symbol search
  const [symbolQuery, setSymbolQuery]           = useState(selectedSymbols[0] || '');
  const [symbolResults, setSymbolResults]       = useState([]);
  const [symbolSearching, setSymbolSearching]   = useState(false);
  const [symbolDropdownOpen, setSymbolDropdownOpen] = useState(false);
  const symbolRef = useRef(null);

  // Price / portfolio
  const [prices, setPrices]       = useState({});
  const [portfolio, setPortfolio] = useState(null);

  // Form state
  const [submitting, setSubmitting]           = useState(false);
  const [error, setError]                     = useState('');
  const [success, setSuccess]                 = useState('');
  const [tradeStatus, setTradeStatus]         = useState(null);
  const [showLimitPriceInput, setShowLimitPriceInput] = useState(false);
  const [limitInputMode, setLimitInputMode]   = useState('$'); // '$' | '%'
  const [limitRawValue, setLimitRawValue]     = useState('');

  // ── Symbol search: debounce 300ms ─────────────────────────────────────────
  useEffect(() => {
    if (symbolQuery.trim().length < 1) {
      setSymbolResults([]);
      setSymbolDropdownOpen(false);
      return;
    }
    const timer = setTimeout(async () => {
      setSymbolSearching(true);
      try {
        const resp = await axios.get(`${API_BASE_URL}/tickers/search`, {
          params: { q: symbolQuery.trim() },
        });
        setSymbolResults(resp.data || []);
        setSymbolDropdownOpen(true);
      } catch {
        setSymbolResults([]);
      }
      setSymbolSearching(false);
    }, 300);
    return () => clearTimeout(timer);
  }, [symbolQuery]);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (symbolRef.current && !symbolRef.current.contains(e.target)) {
        setSymbolDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleSymbolSelect = (ticker) => {
    setFormData((prev) => ({ ...prev, symbol: ticker.symbol }));
    setSymbolQuery(ticker.symbol);
    setSymbolDropdownOpen(false);
    setSymbolResults([]);
  };

  // ── Price fetching ─────────────────────────────────────────────────────────
  useEffect(() => {
    const symbols = formData.symbol
      ? [formData.symbol]
      : selectedSymbols.length > 0
        ? selectedSymbols
        : [];
    if (symbols.length === 0) return;

    const fetchPrices = async () => {
      const priceData = {};
      for (const sym of symbols) {
        try {
          const resp = await axios.get(`${API_BASE_URL}/prices/${sym}/intraday-1min?limit=1`);
          if (resp.data?.length > 0) priceData[sym] = resp.data[0].close;
        } catch { /* keep existing */ }
      }
      setPrices((prev) => ({ ...prev, ...priceData }));
    };

    fetchPrices();
    const interval = setInterval(fetchPrices, 10000);
    return () => clearInterval(interval);
  }, [formData.symbol, selectedSymbols]);

  // ── Portfolio ──────────────────────────────────────────────────────────────
  useEffect(() => {
    const fetchPortfolio = async () => {
      try {
        const resp = await axios.get(`${API_BASE_URL}/portfolio/account`);
        setPortfolio(resp.data);
      } catch { /* ignore */ }
    };
    fetchPortfolio();
    const interval = setInterval(fetchPortfolio, 30000);
    return () => clearInterval(interval);
  }, []);

  // Sync symbol field when watchlist selection changes
  useEffect(() => {
    if (selectedSymbols.length > 0 && !formData.symbol) {
      setFormData((prev) => ({ ...prev, symbol: selectedSymbols[0] }));
      setSymbolQuery(selectedSymbols[0]);
    }
  }, [selectedSymbols]);

  // ── Order metrics ──────────────────────────────────────────────────────────
  const currentPrice = prices[formData.symbol] ?? null;

  // Derive absolute limit price from raw input ($ or %)
  const limitPriceAbsolute = (() => {
    const v = parseFloat(limitRawValue);
    if (!v || !currentPrice) return null;
    if (limitInputMode === '%') return parseFloat((currentPrice * (1 + v / 100)).toFixed(4));
    return v;
  })();

  const effectivePrice  = formData.marketOrder ? currentPrice : (limitPriceAbsolute || currentPrice);
  const orderValue      = effectivePrice != null ? formData.qty * effectivePrice : null;
  const cash            = portfolio?.cash ?? 100000;
  const portfolioValue  = portfolio?.portfolio_value || cash;
  const exposurePercent = orderValue != null ? ((orderValue / portfolioValue) * 100).toFixed(2) : null;

  // Expected P&L vs market price for limit orders
  const limitPnl = (() => {
    if (formData.marketOrder || !limitPriceAbsolute || !currentPrice) return null;
    // For BUY: saving = market − limit (positive means you pay less than market)
    // For SELL: saving = limit − market (positive means you receive more than market)
    const saving = formData.side === 'BUY'
      ? (currentPrice - limitPriceAbsolute) * formData.qty
      : (limitPriceAbsolute - currentPrice) * formData.qty;
    const pct = formData.side === 'BUY'
      ? ((currentPrice - limitPriceAbsolute) / currentPrice) * 100
      : ((limitPriceAbsolute - currentPrice) / currentPrice) * 100;
    return { saving, pct };
  })();

  const errors = [];
  if (orderValue != null && orderValue > cash)
    errors.push(`Order value ($${orderValue.toFixed(2)}) exceeds available cash ($${cash.toFixed(2)})`);
  if (!formData.symbol)
    errors.push('Select a symbol to trade');

  // ── Status polling ─────────────────────────────────────────────────────────
  const pollTradeStatus = (tradeId, symbol, side, qty) => {
    let attempts = 0;
    const interval = setInterval(async () => {
      attempts++;
      try {
        const resp = await axios.get(`${API_BASE_URL}/portfolio/trades/${tradeId}/status`);
        const st = resp.data.status;
        setTradeStatus(st);
        setSuccess(`${side} ${qty} ${symbol} — ${STATUS_LABEL[st] || st}`);
        if (st === 'accepted' || attempts >= 20) {
          clearInterval(interval);
          try {
            const acc = await axios.get(`${API_BASE_URL}/portfolio/account`);
            setPortfolio(acc.data);
          } catch { /* ignore */ }
        }
      } catch { clearInterval(interval); }
    }, 2000);
  };

  // ── Submit ─────────────────────────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    if (errors.length > 0) { setError(errors[0]); return; }

    setSubmitting(true);
    try {
      const resp = await axios.post(`${API_BASE_URL}/portfolio/trade-with-limits`, {
        symbol: formData.symbol,
        side: formData.side.toLowerCase(),
        qty: formData.qty,
        limit_price: formData.marketOrder ? null : limitPriceAbsolute,
      });

      const trade = resp.data;
      setTradeStatus(trade.status);
      setSuccess(`${formData.side} ${formData.qty} ${formData.symbol} — ${STATUS_LABEL[trade.status] || trade.status}`);
      setFormData((prev) => ({ ...prev, qty: 10, limitPrice: null, marketOrder: true }));
      setShowLimitPriceInput(false);
      setLimitRawValue('');
      setLimitInputMode('$');

      if (trade.status !== 'accepted') {
        pollTradeStatus(trade.id, formData.symbol, formData.side, formData.qty);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to submit order. Please try again.');
    }
    setSubmitting(false);
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <p className="text-xs uppercase tracking-[0.35em] text-sky-400">Trade Execution</p>
        <h2 className="mt-1 text-lg font-semibold">Place Order</h2>
      </div>

      {/* Messages */}
      {error && (
        <div className="rounded-lg bg-rose-900/20 border border-rose-600 px-4 py-3 text-sm text-rose-200">
          ⚠ {error}
        </div>
      )}
      {success && (
        <div className={`rounded-lg border px-4 py-3 text-sm ${STATUS_BORDER[tradeStatus] || 'border-emerald-600 bg-emerald-900/20 text-emerald-200'}`}>
          ✓ {success}
        </div>
      )}

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-3">

          {/* Symbol search */}
          <div className="col-span-2" ref={symbolRef}>
            <label className="block text-xs font-medium text-slate-300 mb-1">Symbol</label>
            <div className="relative">
              <input
                type="text"
                value={symbolQuery}
                onChange={(e) => {
                  setSymbolQuery(e.target.value);
                  setFormData((prev) => ({ ...prev, symbol: '' }));
                }}
                onFocus={() => symbolResults.length > 0 && setSymbolDropdownOpen(true)}
                placeholder="Search ticker or company name…"
                className="w-full rounded-lg border border-slate-700 bg-slate-950/90 px-3 py-2 text-sm outline-none focus:border-sky-500"
              />
              {symbolSearching && (
                <span className="absolute right-3 top-2.5 text-xs text-slate-500">Searching…</span>
              )}

              {/* Dropdown results */}
              {symbolDropdownOpen && symbolResults.length > 0 && (
                <div className="absolute z-30 left-0 right-0 mt-1 rounded-xl border border-slate-700 bg-slate-900 shadow-xl overflow-hidden">
                  {symbolResults.map((ticker) => (
                    <button
                      key={ticker.symbol}
                      type="button"
                      onMouseDown={() => handleSymbolSelect(ticker)}
                      className="w-full text-left px-3 py-2.5 text-sm hover:bg-sky-900/40 transition border-b border-slate-800 last:border-0"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-white">{ticker.symbol}</span>
                          {ticker.exchange_display && (
                            <span className="text-[10px] text-sky-400">{ticker.exchange_display}</span>
                          )}
                        </div>
                        {ticker.type_display && (
                          <span className="text-[10px] bg-slate-700 text-slate-300 px-1.5 py-0.5 rounded shrink-0">
                            {ticker.type_display}
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-slate-400 truncate mt-0.5">{ticker.name}</div>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <p className="text-xs text-slate-500 mt-1">
              {formData.symbol
                ? currentPrice != null
                  ? `${formData.symbol} · Current: $${currentPrice.toFixed(2)}`
                  : `${formData.symbol} · Price loading…`
                : 'Type to search'}
            </p>
          </div>

          {/* Side */}
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Side</label>
            <select
              value={formData.side}
              onChange={(e) => setFormData((prev) => ({ ...prev, side: e.target.value }))}
              className="w-full rounded-lg border border-slate-700 bg-slate-950/90 px-3 py-2 text-sm outline-none focus:border-sky-500"
            >
              <option value="BUY">Buy</option>
              <option value="SELL">Sell</option>
            </select>
          </div>

          {/* Quantity */}
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Quantity</label>
            <input
              type="number"
              min="1"
              value={formData.qty}
              onChange={(e) => setFormData((prev) => ({ ...prev, qty: parseInt(e.target.value) }))}
              className="w-full rounded-lg border border-slate-700 bg-slate-950/90 px-3 py-2 text-sm outline-none focus:border-sky-500"
            />
          </div>

          {/* Order Type */}
          <div className="col-span-2">
            <label className="block text-xs font-medium text-slate-300 mb-1">Order Type</label>
            <select
              value={formData.marketOrder ? 'market' : 'limit'}
              onChange={(e) => {
                const isMarket = e.target.value === 'market';
                setFormData((prev) => ({ ...prev, marketOrder: isMarket }));
                setShowLimitPriceInput(!isMarket);
              }}
              className="w-full rounded-lg border border-slate-700 bg-slate-950/90 px-3 py-2 text-sm outline-none focus:border-sky-500"
            >
              <option value="market">Market</option>
              <option value="limit">Limit</option>
            </select>
          </div>
        </div>

        {/* Limit Price */}
        {showLimitPriceInput && (
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs font-medium text-slate-300">Limit Price</label>
              {/* $ / % toggle */}
              <div className="flex rounded-lg overflow-hidden border border-slate-700 text-xs">
                {['$', '%'].map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => { setLimitInputMode(mode); setLimitRawValue(''); setFormData((p) => ({ ...p, limitPrice: null })); }}
                    className={`px-3 py-1 font-medium transition ${limitInputMode === mode ? 'bg-sky-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'}`}
                  >
                    {mode}
                  </button>
                ))}
              </div>
            </div>
            <div className="relative">
              <span className="absolute left-3 top-2 text-sm text-slate-400 pointer-events-none">
                {limitInputMode === '$' ? '$' : '%'}
              </span>
              <input
                type="number"
                step={limitInputMode === '$' ? '0.01' : '0.1'}
                value={limitRawValue}
                onChange={(e) => {
                  const raw = e.target.value;
                  setLimitRawValue(raw);
                  const v = parseFloat(raw);
                  if (!v || !currentPrice) { setFormData((p) => ({ ...p, limitPrice: null })); return; }
                  const abs = limitInputMode === '%'
                    ? parseFloat((currentPrice * (1 + v / 100)).toFixed(4))
                    : v;
                  setFormData((p) => ({ ...p, limitPrice: abs }));
                }}
                placeholder={limitInputMode === '$' ? 'e.g. 195.50' : 'e.g. -2.5'}
                className="w-full rounded-lg border border-slate-700 bg-slate-950/90 pl-7 pr-3 py-2 text-sm outline-none focus:border-sky-500"
              />
            </div>
            {limitInputMode === '%' && limitPriceAbsolute != null && (
              <p className="text-xs text-slate-500 mt-1">= ${limitPriceAbsolute.toFixed(2)} per share</p>
            )}
          </div>
        )}

        {/* Order Summary */}
        <div className="rounded-lg border border-slate-700 bg-slate-950/50 p-3 space-y-2 text-xs">
          <p className="text-xs uppercase tracking-[0.2em] text-slate-500 pb-1 border-b border-slate-700/50">Order Summary</p>

          {/* Market price — always shown */}
          <div className="flex justify-between items-center">
            <span className="text-slate-400 w-36 shrink-0">Market Price</span>
            <span className="text-white font-medium tabular-nums">
              {currentPrice != null ? `$${currentPrice.toFixed(2)}` : 'Loading…'}
            </span>
          </div>

          {/* Limit price row — only in limit mode */}
          {!formData.marketOrder && (
            <div className="flex justify-between items-center">
              <span className="text-slate-400 w-36 shrink-0">Limit Price</span>
              <span className="text-sky-300 font-medium tabular-nums">
                {limitPriceAbsolute != null ? `$${limitPriceAbsolute.toFixed(2)}` : '—'}
              </span>
            </div>
          )}

          {/* Market Value — qty × market price, always shown */}
          <div className="flex justify-between items-center">
            <span className="text-slate-400 w-36 shrink-0">Market Value</span>
            <span className="text-slate-300 font-medium tabular-nums">
              {currentPrice != null ? `$${(formData.qty * currentPrice).toFixed(2)}` : 'Loading…'}
            </span>
          </div>

          {/* Order Value — qty × effective price (limit price if set, else market) */}
          <div className="flex justify-between items-center">
            <span className="text-slate-400 w-36 shrink-0">Order Value</span>
            <span className="text-white font-medium tabular-nums">
              {orderValue != null ? `$${orderValue.toFixed(2)}` : currentPrice == null ? 'Awaiting price' : '—'}
            </span>
          </div>

          {/* Expected P&L vs market — limit orders only */}
          {limitPnl != null && (
            <div className="flex justify-between items-center border-t border-slate-700/50 pt-2 mt-1">
              <span className="text-slate-400 w-36 shrink-0">Expected P&L vs Market</span>
              <span className={`font-semibold tabular-nums ${limitPnl.saving >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {limitPnl.saving >= 0 ? '+' : '−'}${Math.abs(limitPnl.saving).toFixed(2)}
                <span className="ml-1 font-normal opacity-70">
                  ({limitPnl.pct >= 0 ? '+' : ''}{limitPnl.pct.toFixed(2)}%)
                </span>
              </span>
            </div>
          )}

          <div className="flex justify-between items-center">
            <span className="text-slate-400 w-36 shrink-0">Position Exposure</span>
            <span className={`font-medium tabular-nums ${exposurePercent != null && parseFloat(exposurePercent) > TRADE_LIMITS.MAX_POSITION_EXPOSURE_PCT ? 'text-rose-400' : 'text-sky-400'}`}>
              {exposurePercent != null ? `${exposurePercent}%` : '—'}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-slate-400 w-36 shrink-0">Available Cash</span>
            <span className={`font-medium tabular-nums ${orderValue != null && orderValue > cash ? 'text-rose-400' : 'text-emerald-400'}`}>
              ${cash.toFixed(2)}
            </span>
          </div>
        </div>

        {/* Trade Limits info */}
        {errors.length === 0 && (
          <div className="rounded-lg bg-sky-900/10 border border-sky-700 p-3 text-xs text-sky-200">
            <p className="font-medium mb-1">Trade Limits</p>
            <p>Max exposure: {TRADE_LIMITS.MAX_POSITION_EXPOSURE_PCT}% · Max order size: {TRADE_LIMITS.MAX_ORDER_SIZE_PCT}%</p>
          </div>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={submitting || errors.length > 0}
          className={`w-full py-3 rounded-lg font-semibold transition ${
            errors.length > 0
              ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
              : submitting
                ? 'bg-sky-500/50 text-white cursor-wait'
                : 'bg-sky-500 text-slate-950 hover:bg-sky-400'
          }`}
        >
          {submitting
            ? 'Submitting…'
            : formData.symbol
              ? `${formData.side === 'BUY' ? 'Buy' : 'Sell'} ${formData.qty} ${formData.symbol}`
              : 'Select a symbol'}
        </button>
      </form>
    </div>
  );
}
