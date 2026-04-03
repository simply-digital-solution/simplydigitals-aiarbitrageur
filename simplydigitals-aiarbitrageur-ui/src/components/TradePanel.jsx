import { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api/v1';

// Trade limit defaults from backend config
const TRADE_LIMITS = {
  MAX_POSITION_EXPOSURE_PCT: 10.0,
  MAX_DAILY_LOSS_PCT: 5.0,
  MAX_ORDER_SIZE_PCT: 2.0,
};

export default function TradePanel({ selectedSymbols }) {
  const [formData, setFormData] = useState({
    symbol: selectedSymbols[0] || 'AAPL',
    side: 'BUY',
    qty: 10,
    limitPrice: null,
    marketOrder: true,
  });

  const [prices, setPrices] = useState({});
  const [portfolio, setPortfolio] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showLimitPriceInput, setShowLimitPriceInput] = useState(false);

  // Fetch current prices
  useEffect(() => {
    const fetchPrices = async () => {
      try {
        const symbolsToFetch = selectedSymbols.length > 0 ? selectedSymbols : ['AAPL'];
        const priceData = {};

        for (const symbol of symbolsToFetch) {
          try {
            const resp = await axios.get(`${API_BASE_URL}/prices/${symbol}/intraday-1min?limit=1`);
            if (resp.data && resp.data.length > 0) {
              priceData[symbol] = resp.data[0].close;
            }
          } catch {
            // keep existing price if available, don't overwrite with random
          }
        }
        setPrices((prev) => ({ ...prev, ...priceData }));
      } catch (err) {
        console.error('Error fetching prices:', err);
      }
    };

    fetchPrices();
    const interval = setInterval(fetchPrices, 10000); // Update every 10s
    return () => clearInterval(interval);
  }, [selectedSymbols]);

  // Fetch portfolio info (silently in background — never blocks the UI)
  useEffect(() => {
    const fetchPortfolio = async () => {
      try {
        const resp = await axios.get(`${API_BASE_URL}/portfolio/account`);
        setPortfolio(resp.data);
      } catch {
        // leave existing state unchanged
      }
    };

    fetchPortfolio();
    const interval = setInterval(fetchPortfolio, 30000);
    return () => clearInterval(interval);
  }, []);

  // Update symbol to first selected symbol
  useEffect(() => {
    if (selectedSymbols.length > 0 && selectedSymbols[0] !== formData.symbol) {
      setFormData((prev) => ({ ...prev, symbol: selectedSymbols[0] }));
    }
  }, [selectedSymbols]);

  // Calculate order metrics — only for the chosen symbol
  const currentPrice = prices[formData.symbol] ?? null;
  const effectivePrice = formData.marketOrder
    ? currentPrice
    : formData.limitPrice || currentPrice;
  const orderValue = effectivePrice != null ? formData.qty * effectivePrice : null;
  const cash = portfolio?.cash ?? 100000;
  const portfolioValue = portfolio?.portfolio_value || cash;
  const exposurePercent =
    orderValue != null ? ((orderValue / portfolioValue) * 100).toFixed(2) : null;

  // Validation — only block on things the user can fix right now
  const errors = [];
  if (orderValue != null && orderValue > cash) {
    errors.push(
      `Order value ($${orderValue.toFixed(2)}) exceeds available cash ($${cash.toFixed(2)})`
    );
  }

  // Handle form submission
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (errors.length > 0) {
      setError(errors[0]);
      return;
    }

    setSubmitting(true);
    try {
      const tradeRequest = {
        symbol: formData.symbol,
        side: formData.side.toLowerCase(),
        qty: formData.qty,
        limit_price: formData.marketOrder ? null : formData.limitPrice,
      };

      const resp = await axios.post(`${API_BASE_URL}/portfolio/trade-with-limits`, tradeRequest);

      if (resp.data.order_id) {
        setSuccess(
          `Order ${resp.data.order_id} submitted: ${formData.side} ${formData.qty} ${formData.symbol}`
        );
        // Reset form
        setFormData((prev) => ({
          ...prev,
          qty: 10,
          limitPrice: null,
          marketOrder: true,
        }));
        setShowLimitPriceInput(false);

        // Refresh portfolio after 2 seconds
        setTimeout(async () => {
          try {
            const portfolioResp = await axios.get(`${API_BASE_URL}/portfolio`);
            setPortfolio(portfolioResp.data);
          } catch (err) {
            console.error('Error refreshing portfolio:', err);
          }
        }, 2000);
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
        <div className="rounded-lg bg-emerald-900/20 border border-emerald-600 px-4 py-3 text-sm text-emerald-200">
          ✓ {success}
        </div>
      )}

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          {/* Symbol */}
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Symbol</label>
            <select
              value={formData.symbol}
              onChange={(e) => setFormData((prev) => ({ ...prev, symbol: e.target.value }))}
              className="w-full rounded-lg border border-slate-700 bg-slate-950/90 px-3 py-2 text-sm outline-none focus:border-sky-500"
            >
              {selectedSymbols.map((sym) => (
                <option key={sym} value={sym}>
                  {sym}
                </option>
              ))}
            </select>
            <p className="text-xs text-slate-500 mt-1">
              {currentPrice != null ? `Current: $${currentPrice.toFixed(2)}` : 'Price loading...'}
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
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  qty: parseInt(e.target.value),
                }))
              }
              className="w-full rounded-lg border border-slate-700 bg-slate-950/90 px-3 py-2 text-sm outline-none focus:border-sky-500"
            />
          </div>

          {/* Order Type */}
          <div>
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
            <label className="block text-xs font-medium text-slate-300 mb-1">Limit Price</label>
            <input
              type="number"
              step="0.01"
              min="0.01"
              value={formData.limitPrice || ''}
              onChange={(e) =>
                setFormData((prev) => ({
                  ...prev,
                  limitPrice: parseFloat(e.target.value),
                }))
              }
              placeholder="Enter limit price"
              className="w-full rounded-lg border border-slate-700 bg-slate-950/90 px-3 py-2 text-sm outline-none focus:border-sky-500"
            />
          </div>
        )}

        {/* Order Summary */}
        <div className="rounded-lg border border-slate-700 bg-slate-950/50 p-3 space-y-2 text-xs">
          <p className="text-xs uppercase tracking-[0.2em] text-slate-500 pb-1 border-b border-slate-700/50">Order Summary</p>
          <div className="flex justify-between items-center">
            <span className="text-slate-400 w-36 shrink-0">
              {formData.marketOrder ? 'Market Price' : 'Limit Price'}
            </span>
            <span className="text-white font-medium tabular-nums">
              {effectivePrice != null ? `$${effectivePrice.toFixed(2)}` : 'Loading...'}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-slate-400 w-36 shrink-0">Order Value</span>
            <span className="text-white font-medium tabular-nums">
              {orderValue != null ? `$${orderValue.toFixed(2)}` : effectivePrice == null ? 'Awaiting price' : '—'}
            </span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-slate-400 w-36 shrink-0">Position Exposure</span>
            <span
              className={`font-medium tabular-nums ${
                exposurePercent != null && parseFloat(exposurePercent) > TRADE_LIMITS.MAX_POSITION_EXPOSURE_PCT
                  ? 'text-rose-400'
                  : 'text-sky-400'
              }`}
            >
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

        {/* Limit Info */}
        {errors.length === 0 && (
          <div className="rounded-lg bg-sky-900/10 border border-sky-700 p-3 text-xs text-sky-200">
            <p className="font-medium mb-1">Trade Limits</p>
            <p>
              Max exposure: {TRADE_LIMITS.MAX_POSITION_EXPOSURE_PCT}% • Max order size:{' '}
              {TRADE_LIMITS.MAX_ORDER_SIZE_PCT}%
            </p>
          </div>
        )}

        {/* Submit Button */}
        <button
          type="submit"
          disabled={submitting || errors.length > 0 || selectedSymbols.length === 0}
          className={`w-full py-3 rounded-lg font-semibold transition ${
            errors.length > 0 || selectedSymbols.length === 0
              ? 'bg-slate-700 text-slate-400 cursor-not-allowed'
              : submitting
                ? 'bg-sky-500/50 text-white cursor-wait'
                : 'bg-sky-500 text-slate-950 hover:bg-sky-400'
          }`}
        >
          {submitting
            ? 'Submitting...'
            : `${formData.side === 'BUY' ? 'Buy' : 'Sell'} ${formData.qty} ${formData.symbol}`}
        </button>
      </form>

      {selectedSymbols.length === 0 && (
        <div className="rounded-lg border border-dashed border-slate-700 p-4 text-center text-sm text-slate-400">
          Select a ticker from the watchlist to trade
        </div>
      )}
    </div>
  );
}
