import { useState, useEffect } from "react";
import axios from "axios";

const API_BASE_URL = "http://localhost:8000/api/v1";

export default function WatchlistSidebar({ selectedSymbols, onSelectSymbols }) {
  const [watchlist, setWatchlist] = useState([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [prices, setPrices] = useState({});
  const [loading, setLoading] = useState(false);

  // Default watchlist (would come from API in production)
  useEffect(() => {
    const defaultWatchlist = [
      { symbol: "AAPL", name: "Apple Inc." },
      { symbol: "MSFT", name: "Microsoft Corporation" },
      { symbol: "TSLA", name: "Tesla Inc." },
      { symbol: "GOOGL", name: "Alphabet Inc." },
      { symbol: "AMZN", name: "Amazon.com Inc." },
    ];
    setWatchlist(defaultWatchlist);

    // Fetch initial prices
    fetchPrices(defaultWatchlist.map((t) => t.symbol));
  }, []);

  // Fetch prices for symbols
  const fetchPrices = async (symbols) => {
    try {
      const priceData = {};
      for (const symbol of symbols) {
        try {
          const resp = await axios.get(
            `${API_BASE_URL}/prices/${symbol}/intraday-1min?limit=1`,
          );
          if (resp.data && resp.data.length > 0) {
            const latest = resp.data[0];
            priceData[symbol] = latest.close;
          }
        } catch (err) {
          // Fallback to mock data
          priceData[symbol] = Math.random() * 500;
        }
      }
      setPrices(priceData);
    } catch (err) {
      console.error("Error fetching prices:", err);
    }
  };

  // Search tickers
  const handleSearch = async (query) => {
    setSearchQuery(query);
    if (query.trim().length < 1) {
      setSearchResults([]);
      return;
    }

    setLoading(true);
    try {
      const resp = await axios.get(`${API_BASE_URL}/tickers/search`, {
        params: { q: query, limit: 5 },
      });
      setSearchResults(resp.data.tickers || []);
    } catch (err) {
      console.error("Error searching tickers:", err);
      setSearchResults([]);
    }
    setLoading(false);
  };

  // Add ticker to watchlist
  const handleAddTicker = (ticker) => {
    if (!watchlist.find((t) => t.symbol === ticker.symbol)) {
      setWatchlist([...watchlist, ticker]);
      fetchPrices([ticker.symbol]);
    }
    setSearchQuery("");
    setSearchResults([]);
  };

  // Toggle symbol selection
  const handleToggleSymbol = (symbol) => {
    if (selectedSymbols.includes(symbol)) {
      onSelectSymbols(selectedSymbols.filter((s) => s !== symbol));
    } else {
      onSelectSymbols([...selectedSymbols, symbol]);
    }
  };

  // Remove ticker from watchlist
  const handleRemoveTicker = (symbol) => {
    setWatchlist(watchlist.filter((t) => t.symbol !== symbol));
    if (selectedSymbols.includes(symbol)) {
      handleToggleSymbol(symbol);
    }
  };

  return (
    <div className="flex flex-col gap-4 p-4">
      {/* Header */}
      <div>
        <p className="text-xs uppercase tracking-[0.35em] text-sky-400">
          Watchlist
        </p>
        <h2 className="mt-2 text-lg font-semibold">Search & Select</h2>
      </div>

      {/* Search Box */}
      <div className="space-y-2">
        <input
          type="text"
          placeholder="Search ticker..."
          value={searchQuery}
          onChange={(e) => handleSearch(e.target.value)}
          className="w-full rounded-2xl border border-slate-700 bg-slate-950/90 px-3 py-2 text-sm outline-none focus:border-sky-500"
        />

        {/* Search Results */}
        {searchResults.length > 0 && (
          <div className="rounded-2xl border border-slate-700 bg-slate-950/80 p-2 space-y-1">
            {searchResults.map((ticker) => (
              <button
                key={ticker.symbol}
                onClick={() => handleAddTicker(ticker)}
                className="w-full text-left rounded-lg bg-slate-900 px-2 py-2 text-sm hover:bg-sky-900 transition"
              >
                <span className="font-medium">{ticker.symbol}</span>
                <span className="text-xs text-slate-400 ml-2">
                  {ticker.name}
                </span>
              </button>
            ))}
          </div>
        )}

        {loading && (
          <div className="text-xs text-slate-400 p-2">Searching...</div>
        )}
      </div>

      {/* Watchlist Items */}
      <div className="rounded-2xl border border-slate-700 bg-slate-950/80 p-3 flex-1 overflow-y-auto">
        <p className="text-xs uppercase tracking-[0.2em] text-slate-500 mb-3">
          Your Tickers
        </p>
        {watchlist.length === 0 ? (
          <div className="text-xs text-slate-500 p-2">No tickers added</div>
        ) : (
          <ul className="space-y-2">
            {watchlist.map((ticker) => {
              const isSelected = selectedSymbols.includes(ticker.symbol);
              const price = prices[ticker.symbol] || 0;

              return (
                <li
                  key={ticker.symbol}
                  className={`flex items-center justify-between rounded-lg px-2 py-2 transition cursor-pointer ${
                    isSelected
                      ? "bg-sky-900/40 border border-sky-600"
                      : "bg-slate-900 hover:bg-slate-800"
                  }`}
                  onClick={() => handleToggleSymbol(ticker.symbol)}
                  role="button"
                >
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-sm truncate">
                      {ticker.symbol}
                    </div>
                    <div className="text-xs text-slate-500 truncate">
                      ${price.toFixed(2)}
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRemoveTicker(ticker.symbol);
                    }}
                    className="ml-2 text-rose-400 hover:text-rose-300 text-xs"
                  >
                    ✕
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* Selected Count */}
      {selectedSymbols.length > 0 && (
        <div className="rounded-lg bg-sky-900/20 border border-sky-600 px-3 py-2 text-xs text-sky-200">
          {selectedSymbols.length} ticker{selectedSymbols.length > 1 ? "s" : ""}{" "}
          selected for charting
        </div>
      )}
    </div>
  );
}
