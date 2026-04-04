import { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api/v1';

const EXCHANGE_NAMES = {
  NMS: 'NASDAQ', NGM: 'NASDAQ', NCM: 'NASDAQ',
  NYQ: 'NYSE', PCX: 'NYSE Arca', ASE: 'NYSE American',
  GER: 'XETRA', TOR: 'TSX', MEX: 'BMV', LSE: 'LSE',
};
const exchLabel = (code) => (code ? (EXCHANGE_NAMES[code] || code) : null);

export default function WatchlistSidebar({ selectedSymbols, onSelectSymbols, onSymbolMetaChange }) {
  const [watchlist, setWatchlist] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [prices, setPrices] = useState({});
  const [loading, setLoading] = useState(false);

  // Default watchlist (would come from API in production)
  useEffect(() => {
    const defaultWatchlist = [
      { symbol: 'AAPL', name: 'Apple Inc.', exchange: 'NMS' },
      { symbol: 'MSFT', name: 'Microsoft Corporation', exchange: 'NMS' },
      { symbol: 'TSLA', name: 'Tesla Inc.', exchange: 'NMS' },
      { symbol: 'GOOGL', name: 'Alphabet Inc.', exchange: 'NMS' },
      { symbol: 'AMZN', name: 'Amazon.com Inc.', exchange: 'NMS' },
    ];
    setWatchlist(defaultWatchlist);
    const meta = {};
    defaultWatchlist.forEach((t) => { meta[t.symbol] = { exchange: t.exchange, exchangeDisplay: exchLabel(t.exchange) }; });
    onSymbolMetaChange?.(meta);

    // Fetch initial prices
    fetchPrices(defaultWatchlist.map((t) => t.symbol));
  }, []);

  // Fetch prices for symbols
  const fetchPrices = async (symbols) => {
    try {
      const priceData = {};
      for (const symbol of symbols) {
        try {
          const resp = await axios.get(`${API_BASE_URL}/prices/${symbol}/intraday-1min?limit=1`);
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
      console.error('Error fetching prices:', err);
    }
  };

  // Search tickers (debounced)
  useEffect(() => {
    if (searchQuery.trim().length < 1) {
      setSearchResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const resp = await axios.get(`${API_BASE_URL}/tickers/search`, {
          params: { q: searchQuery.trim() },
        });
        setSearchResults(resp.data || []);
      } catch (err) {
        console.error('Error searching tickers:', err);
        setSearchResults([]);
      }
      setLoading(false);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const handleSearch = (query) => {
    setSearchQuery(query);
  };

  // Add ticker to watchlist
  const handleAddTicker = (ticker) => {
    if (!watchlist.find((t) => t.symbol === ticker.symbol)) {
      const updated = [...watchlist, ticker];
      setWatchlist(updated);
      fetchPrices([ticker.symbol]);
      const meta = {};
      updated.forEach((t) => { meta[t.symbol] = { exchange: t.exchange, exchangeDisplay: t.exchange_display || exchLabel(t.exchange) }; });
      onSymbolMetaChange?.(meta);
    }
    setSearchQuery('');
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
        <p className="text-xs uppercase tracking-[0.35em] text-sky-400">Watchlist</p>
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
                <div className="flex items-center justify-between gap-2">
                  <span className="font-semibold">{ticker.symbol}</span>
                  <div className="flex items-center gap-1 shrink-0">
                    {ticker.type_display && (
                      <span className="text-xs bg-slate-700 text-slate-300 px-1.5 py-0.5 rounded">
                        {ticker.type_display}
                      </span>
                    )}
                    {ticker.exchange_display && (
                      <span className="text-xs text-sky-400">{ticker.exchange_display}</span>
                    )}
                  </div>
                </div>
                <div className="text-xs text-slate-400 truncate mt-0.5">{ticker.name}</div>
              </button>
            ))}
          </div>
        )}

        {loading && <div className="text-xs text-slate-400 p-2">Searching...</div>}
      </div>

      {/* Watchlist Items */}
      <div className="rounded-2xl border border-slate-700 bg-slate-950/80 p-3 flex-1 overflow-y-auto">
        <p className="text-xs uppercase tracking-[0.2em] text-slate-500 mb-3">Your Tickers</p>
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
                      ? 'bg-sky-900/40 border border-sky-600'
                      : 'bg-slate-900 hover:bg-slate-800'
                  }`}
                  onClick={() => handleToggleSymbol(ticker.symbol)}
                  role="button"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5">
                      <span className="font-medium text-sm">{ticker.symbol}</span>
                      {(ticker.exchange_display || exchLabel(ticker.exchange)) && (
                        <span className="text-[10px] text-sky-400 leading-none">
                          {ticker.exchange_display || exchLabel(ticker.exchange)}
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-slate-500 truncate">${price.toFixed(2)}</div>
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
          {selectedSymbols.length} ticker{selectedSymbols.length > 1 ? 's' : ''} selected for
          charting
        </div>
      )}
    </div>
  );
}
