import { useState, useEffect } from "react";
import axios from "axios";

const API_BASE_URL = "http://localhost:8000/api/v1";

// Trade limit defaults from backend config
const TRADE_LIMITS = {
  MAX_POSITION_EXPOSURE_PCT: 10.0,
  MAX_DAILY_LOSS_PCT: 5.0,
  MAX_ORDER_SIZE_PCT: 2.0,
};

export default function TradePanel({ selectedSymbols }) {
  const [formData, setFormData] = useState({
    symbol: selectedSymbols[0] || "AAPL",
    side: "BUY",
    qty: 10,
    limitPrice: null,
    marketOrder: true,
  });

  const [prices, setPrices] = useState({});
  const [portfolio, setPortfolio] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [showLimitPriceInput, setShowLimitPriceInput] = useState(false);

  // Fetch current prices
  useEffect(() => {
    const fetchPrices = async () => {
      try {
        const symbolsToFetch =
          selectedSymbols.length > 0 ? selectedSymbols : ["AAPL"];
        const priceData = {};

        for (const symbol of symbolsToFetch) {
          try {
            const resp = await axios.get(
              `${API_BASE_URL}/prices/${symbol}/intraday-1min?limit=1`,
            );
            if (resp.data && resp.data.length > 0) {
              priceData[symbol] = resp.data[0].close;
            }
          } catch (err) {
            // Mock data for demo
            priceData[symbol] = Math.random() * 500;
          }
        }
        setPrices(priceData);
      } catch (err) {
        console.error("Error fetching prices:", err);
      }
    };

    fetchPrices();
    const interval = setInterval(fetchPrices, 10000); // Update every 10s
    return () => clearInterval(interval);
  }, [selectedSymbols]);

  // Fetch portfolio info
  useEffect(() => {
    const fetchPortfolio = async () => {
      try {
        const resp = await axios.get(`${API_BASE_URL}/portfolio`);
        setPortfolio(resp.data);
      } catch (err) {
        console.error("Error fetching portfolio:", err);
        // Mock portfolio for demo
        setPortfolio({
          cash: 50000,
          portfolio_value: 100000,
          positions: [],
        });
      }
    };

    fetchPortfolio();
    const interval = setInterval(fetchPortfolio, 30000); // Update every 30s
    return () => clearInterval(interval);
  }, []);

  // Update symbol to first selected symbol
  useEffect(() => {
    if (selectedSymbols.length > 0 && selectedSymbols[0] !== formData.symbol) {
      setFormData((prev) => ({ ...prev, symbol: selectedSymbols[0] }));
    }
  }, [selectedSymbols]);

  // Calculate order metrics
  const currentPrice = prices[formData.symbol] || 100;
  const orderValue =
    formData.qty *
    (formData.marketOrder ? currentPrice : formData.limitPrice || currentPrice);
  const portfolioValue = portfolio?.portfolio_value || 100000;
  const cash = portfolio?.cash || 50000;
  const exposurePercent = ((orderValue / portfolioValue) * 100).toFixed(2);
  const orderSizePercent = ((orderValue / portfolioValue) * 100).toFixed(2);

  // Validation
  const errors = [];
  if (orderValue > cash) {
    errors.push(
      `Order value ($${orderValue.toFixed(2)}) exceeds available cash ($${cash.toFixed(2)})`,
    );
  }
  if (exposurePercent > TRADE_LIMITS.MAX_POSITION_EXPOSURE_PCT) {
    errors.push(
      `Position exposure (${exposurePercent}%) exceeds limit (${TRADE_LIMITS.MAX_POSITION_EXPOSURE_PCT}%)`,
    );
  }
  if (orderSizePercent > TRADE_LIMITS.MAX_ORDER_SIZE_PCT) {
    errors.push(
      `Order size (${orderSizePercent}%) exceeds limit (${TRADE_LIMITS.MAX_ORDER_SIZE_PCT}%)`,
    );
  }

  // Handle form submission
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (errors.length > 0) {
      setError(errors[0]);
      return;
    }

    setLoading(true);
    try {
      const tradeRequest = {
        symbol: formData.symbol,
        side: formData.side,
        qty: formData.qty,
        limit_price: formData.marketOrder ? null : formData.limitPrice,
      };

      const resp = await axios.post(
        `${API_BASE_URL}/portfolio/trade-with-limits`,
        tradeRequest,
      );

      if (resp.data.order_id) {
        setSuccess(
          `Order ${resp.data.order_id} submitted: ${formData.side} ${formData.qty} ${formData.symbol}`,
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
            console.error("Error refreshing portfolio:", err);
          }
        }, 2000);
      }
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Failed to submit order. Please try again.",
      );
    }
    setLoading(false);
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div>
        <p className="text-xs uppercase tracking-[0.35em] text-sky-400">
          Trade Execution
        </p>
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
            <label className="block text-xs font-medium text-slate-300 mb-1">
              Symbol
            </label>
            <select
              value={formData.symbol}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, symbol: e.target.value }))
              }
              className="w-full rounded-lg border border-slate-700 bg-slate-950/90 px-3 py-2 text-sm outline-none focus:border-sky-500"
            >
              {selectedSymbols.map((sym) => (
                <option key={sym} value={sym}>
                  {sym}
                </option>
              ))}
            </select>
            <p className="text-xs text-slate-500 mt-1">
              Current: ${currentPrice.toFixed(2)}
            </p>
          </div>

          {/* Side */}
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">
              Side
            </label>
            <select
              value={formData.side}
              onChange={(e) =>
                setFormData((prev) => ({ ...prev, side: e.target.value }))
              }
              className="w-full rounded-lg border border-slate-700 bg-slate-950/90 px-3 py-2 text-sm outline-none focus:border-sky-500"
            >
              <option value="BUY">Buy</option>
              <option value="SELL">Sell</option>
            </select>
          </div>

          {/* Quantity */}
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">
              Quantity
            </label>
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
            <label className="block text-xs font-medium text-slate-300 mb-1">
              Order Type
            </label>
            <select
              value={formData.marketOrder ? "market" : "limit"}
              onChange={(e) => {
                const isMarket = e.target.value === "market";
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
            <label className="block text-xs font-medium text-slate-300 mb-1">
              Limit Price
            </label>
            <input
              type="number"
              step="0.01"
              min="0.01"
              value={formData.limitPrice || ""}
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
          <div className="flex justify-between">
            <span className="text-slate-400">Order Value:</span>
            <span className="text-white font-medium">
              ${orderValue.toFixed(2)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Position Exposure:</span>
            <span
              className={
                exposurePercent > TRADE_LIMITS.MAX_POSITION_EXPOSURE_PCT
                  ? "text-rose-400"
                  : "text-sky-400"
              }
            >
              {exposurePercent}%
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-400">Available Cash:</span>
            <span
              className={
                orderValue > cash ? "text-rose-400" : "text-emerald-400"
              }
            >
              ${cash.toFixed(2)}
            </span>
          </div>
        </div>

        {/* Limit Info */}
        {errors.length === 0 && (
          <div className="rounded-lg bg-sky-900/10 border border-sky-700 p-3 text-xs text-sky-200">
            <p className="font-medium mb-1">Trade Limits</p>
            <p>
              Max exposure: {TRADE_LIMITS.MAX_POSITION_EXPOSURE_PCT}% • Max
              order size: {TRADE_LIMITS.MAX_ORDER_SIZE_PCT}%
            </p>
          </div>
        )}

        {/* Submit Button */}
        <button
          type="submit"
          disabled={
            loading || errors.length > 0 || selectedSymbols.length === 0
          }
          className={`w-full py-3 rounded-lg font-semibold transition ${
            errors.length > 0 || selectedSymbols.length === 0
              ? "bg-slate-700 text-slate-400 cursor-not-allowed"
              : loading
                ? "bg-sky-500/50 text-white cursor-wait"
                : "bg-sky-500 text-slate-950 hover:bg-sky-400"
          }`}
        >
          {loading
            ? "Submitting..."
            : `${formData.side === "BUY" ? "Buy" : "Sell"} ${formData.qty} ${formData.symbol}`}
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
