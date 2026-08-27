// Shared OHLC data/cache controller used by both chart providers.
// It intentionally loads historical data only; refreshing newer bars is a
// separate concern and can be added later without changing chart providers.
(function () {
  const INTERVAL_MS = {
    '30m': 30 * 60 * 1000,
    '1h': 60 * 60 * 1000,
    '4h': 4 * 60 * 60 * 1000,
    '1d': 24 * 60 * 60 * 1000,
    '1wk': 7 * 24 * 60 * 60 * 1000,
  };
  const MAX_HISTORICAL_REQUEST_BARS = 300;

  class ChartDataController {
    constructor({ symbol, initialOhlc, initialInterval = '1d', onDataChange, onLoadingChange }) {
      this.symbol = symbol;
      this.interval = initialInterval;
      this.onDataChange = onDataChange || (() => {});
      this.onLoadingChange = onLoadingChange || (() => {});
      this.cache = new Map();
      this.fetchInFlight = false;
      this.pendingViewport = null;
      this.intervalRequestId = 0;
      this.rangeRequestId = 0;
      this.loadingRequestCount = 0;
      this.setCache(initialOhlc || []);
    }

    getIntervalMs() {
      return INTERVAL_MS[this.interval] || INTERVAL_MS['1d'];
    }

    getData() {
      return Array.from(this.cache.entries())
        .sort((a, b) => a[0] - b[0])
        .map(([, point]) => point);
    }

    setCache(rawOhlc) {
      this.cache.clear();
      this.addToCache(rawOhlc);
    }

    addToCache(rawOhlc) {
      rawOhlc.forEach((point) => {
        const timestamp = Date.parse(point.x);
        if (!Number.isNaN(timestamp)) this.cache.set(timestamp, point);
      });
    }

    getCacheBounds() {
      if (!this.cache.size) return null;
      const timestamps = Array.from(this.cache.keys()).sort((a, b) => a - b);
      return { min: timestamps[0], max: timestamps[timestamps.length - 1] };
    }

    showLoading() {
      this.loadingRequestCount += 1;
      const container = document.querySelector('.chart-container');
      if (container) {
        let overlay = container.querySelector('.chart-loading-overlay');
        if (!overlay) {
          overlay = document.createElement('div');
          overlay.className = 'chart-loading-overlay';
          overlay.innerHTML = '<div class="chart-loading-spinner"></div>';
          container.appendChild(overlay);
        }
        overlay.style.display = 'flex';
      }
      this.onLoadingChange(true);
    }

    hideLoading() {
      this.loadingRequestCount = Math.max(0, this.loadingRequestCount - 1);
      if (this.loadingRequestCount > 0) return;
      const overlay = document.querySelector('.chart-loading-overlay');
      if (overlay) overlay.style.display = 'none';
      this.onLoadingChange(false);
    }

    notify(reason, details = {}) {
      this.onDataChange(this.getData(), { reason, interval: this.interval, ...details });
    }

    async changeInterval(interval) {
      const requestId = ++this.intervalRequestId;
      // Invalidate an older-history request started for the previous interval.
      ++this.rangeRequestId;
      this.interval = interval;
      this.pendingViewport = null;
      this.showLoading();
      try {
        const response = await fetch(`/get_ohlc?symbol=${encodeURIComponent(this.symbol)}&interval=${encodeURIComponent(interval)}`);
        const data = await response.json();
        // A later interval click supersedes this result.
        if (requestId !== this.intervalRequestId) return false;
        if (data.error || !Array.isArray(data.ohlc)) {
          console.error('Error fetching interval data:', data.error || 'Invalid response');
          return false;
        }
        this.setCache(data.ohlc);
        this.notify('interval');
        return true;
      } catch (error) {
        if (requestId === this.intervalRequestId) console.error('Interval fetch error:', error);
        return false;
      } finally {
        // Every call to showLoading() must release its own reference, including
        // responses superseded by a later interval selection.
        this.hideLoading();
      }
    }

    needsHistoricalFetch(startDate) {
      const bounds = this.getCacheBounds();
      return !bounds || startDate < bounds.min - this.getIntervalMs() / 2;
    }

    loadPreviousWindow(viewportWidth) {
      const bounds = this.getCacheBounds();
      if (!bounds) return false;
      const intervalMs = this.getIntervalMs();
      // Lightweight Charts clamps at the first data point, so its visible range
      // cannot extend before cache.min. Request just beyond that edge instead.
      return this.loadHistorical(
        bounds.min - intervalMs,
        bounds.min + Math.max(viewportWidth, intervalMs),
      );
    }

    async loadHistorical(startDate, endDate) {
      if (!this.needsHistoricalFetch(startDate)) return false;
      if (this.fetchInFlight) {
        this.pendingViewport = { startDate, endDate };
        return false;
      }

      this.fetchInFlight = true;
      const requestId = ++this.rangeRequestId;
      const intervalMs = this.getIntervalMs();
      const maxRequestSpan = intervalMs * MAX_HISTORICAL_REQUEST_BARS;
      const viewportWidth = Math.min(
        Math.max(endDate - startDate, intervalMs),
        maxRequestSpan / 2,
      );
      const bounds = this.getCacheBounds();
      // Fetch directly before the cached history rather than trusting an
      // arbitrary chart scale end. This prevents a malformed/extreme viewport
      // from creating a multi-year server request.
      const fetchEnd = bounds ? bounds.min - intervalMs : endDate;
      const fetchStart = fetchEnd - Math.min(viewportWidth * 2, maxRequestSpan);
      this.showLoading();
      try {
        const start = encodeURIComponent(new Date(fetchStart).toISOString());
        const end = encodeURIComponent(new Date(fetchEnd).toISOString());
        const response = await fetch(`/get_ohlc_range?symbol=${encodeURIComponent(this.symbol)}&interval=${encodeURIComponent(this.interval)}&start=${start}&end=${end}`);
        const data = await response.json();
        // Ignore a range result that belongs to an interval replaced in-flight.
        if (requestId !== this.rangeRequestId || data.error || !Array.isArray(data.ohlc)) {
          if (data.error) console.error('Error fetching historical range:', data.error);
          return false;
        }
        if (data.ohlc.length) {
          this.addToCache(data.ohlc);
          this.notify('historical', { viewport: { startDate, endDate } });
          return true;
        }
        return false;
      } catch (error) {
        console.error('Historical range fetch error:', error);
        return false;
      } finally {
        this.fetchInFlight = false;
        this.hideLoading();
        const pending = this.pendingViewport;
        this.pendingViewport = null;
        if (pending && this.needsHistoricalFetch(pending.startDate)) {
          this.loadHistorical(pending.startDate, pending.endDate);
        }
      }
    }
  }

  window.ChartDataController = ChartDataController;
}());