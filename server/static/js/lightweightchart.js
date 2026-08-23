// Lightweight Charts implementation with the same features as chart.js
// Uses TradingView's Lightweight Charts library
// Ensure initialization runs immediately if DOMContentLoaded already fired
function initLightweightChart() {
  // Wait for LightweightCharts library to be available
  if (typeof LightweightCharts === 'undefined') {
    console.error('LightweightCharts library not loaded');
    return;
  }

  const config = window.CHART_CONFIG;

  // ===== State =====
  let currentSymbol = config.symbol;
  let currentName = config.name;
  let rawOhlc = config.ohlcData;
  let chartType = "candlestick";
  let chartInterval = "1d";
  let chart;
  let series;
  let currIntervalButton;
  let isLoading = false;
  let fetchInFlight = false;
  let pendingViewport = null;
  let debounceTimer = null;
  const DEBOUNCE_MS = 300;

  // ===== Data Cache =====
  // Cache stores all fetched OHLC data to avoid redundant API calls
  // Key: timestamp (seconds), Value: {time, open, high, low, close}
  // We'll use unix seconds everywhere to match LightweightCharts getVisibleRange()
  // which returns seconds in the version used here.
  const dataCache = new Map();

  // Helper to normalize time values for LightweightCharts.
  // For daily ('1d') intervals we provide a date string (YYYY-MM-DD) so
  // LightweightCharts treats it as a day bar and avoids timezone shifts.
  // For intraday intervals we provide unix seconds.
  // Return an object with numeric key (seconds since epoch at UTC midnight for 1d)
  // and a value suitable for LightweightCharts time field (either YYYY-MM-DD or seconds)
  function formatPointTime(pointX) {
    // Normalize input
    const raw = String(pointX);
    if (chartInterval === '1d') {
      // Try to extract YYYY-MM-DD
      const m = raw.match(/^(\d{4}-\d{2}-\d{2})/);
      let dateStr;
      if (m) {
        dateStr = m[1];
      } else {
        const d = new Date(raw);
        dateStr = d.getUTCFullYear().toString().padStart(4, '0') + '-' +
                  (d.getUTCMonth() + 1).toString().padStart(2, '0') + '-' +
                  d.getUTCDate().toString().padStart(2, '0');
      }
      // numeric key: seconds at UTC midnight for that date (used for cache range comparisons)
      const utcMidnight = Date.UTC(Number(dateStr.slice(0,4)), Number(dateStr.slice(5,7)) - 1, Number(dateStr.slice(8,10)));
      return { key: Math.floor(utcMidnight / 1000), chartTime: dateStr };
    }

    // intraday: use unix seconds as both key and chart time
    const sec = Math.floor(Date.parse(raw) / 1000);
    return { key: sec, chartTime: sec };
  }

  // Initialize cache with initial data
  function initCache(rawData) {
    rawData.forEach(point => {
      const t = formatPointTime(point.x);
      dataCache.set(t.key, {
        time: t.chartTime,
        open: point.o,
        high: point.h,
        low: point.l,
        close: point.c
      });
    });
  }

  // Get data from cache for a given range
  function getFromCache(minTime, maxTime) {
    const result = [];
    const sortedKeys = Array.from(dataCache.keys()).sort((a, b) => a - b);
    
    for (const timestamp of sortedKeys) {
      if (timestamp >= minTime && timestamp <= maxTime) {
        result.push(dataCache.get(timestamp));
      }
    }
    
    return result;
  }

  // Return true if cache has at least one data point for every expected bar
  // between minTime and maxTime (approximately). This helps avoid refetching
  // ranges we already covered.
  function cacheHasFullRange(minTime, maxTime) {
    const allKeys = Array.from(dataCache.keys()).sort((a, b) => a - b);
    if (allKeys.length === 0) return false;

    // Count cached points inside range
    let count = 0;
    for (const k of allKeys) {
      if (k >= minTime && k <= maxTime) count++;
    }

    if (count === 0) return false;

    // Estimate expected number of points by dividing span by interval seconds
    const expected = Math.max(1, Math.round((maxTime - minTime) / getIntervalSec(chartInterval)));
    // If we have at least 60% of expected bars cached, treat as full coverage
    return count >= Math.floor(expected * 0.6);
  }

  // Add data to cache
  function addToCache(rawData) {
    rawData.forEach(point => {
      const t = formatPointTime(point.x);
      dataCache.set(t.key, {
        time: t.chartTime,
        open: point.o,
        high: point.h,
        low: point.l,
        close: point.c
      });
    });
  }

  // Get all cached data sorted by time
  function getAllCachedData() {
    // dataCache keys are numeric seconds (UTC midnight for 1d or unix sec for intraday)
    // sort by the numeric key to ensure ascending order even when stored 'time'
    // is a YYYY-MM-DD string for daily bars.
    return Array.from(dataCache.entries())
      .sort((a, b) => a[0] - b[0])
      .map(entry => entry[1]);
  }

  // Get the time range of cached data
  function getCacheBounds() {
    if (dataCache.size === 0) return null;
    const timestamps = Array.from(dataCache.keys()).sort((a, b) => a - b);
    return {
      min: timestamps[0],
      max: timestamps[timestamps.length - 1]
    };
  }

  // ===== Loading Overlay =====
  function showLoadingOverlay() {
    isLoading = true;
    const container = document.querySelector('.chart-container');
    let overlay = container.querySelector('.chart-loading-overlay');
    
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.className = 'chart-loading-overlay';
      overlay.innerHTML = '<div class="chart-loading-spinner"></div>';
      container.appendChild(overlay);
    } else {
      overlay.style.display = 'flex';
    }
  }

  function hideLoadingOverlay() {
    isLoading = false;
    const overlay = document.querySelector('.chart-loading-overlay');
    if (overlay) {
      overlay.style.display = 'none';
    }
  }

  // ===== Favorites =====
  const favBtn = document.getElementById("fav-btn");
  const favIcon = document.getElementById("fav-icon");

  favBtn.addEventListener("click", () => {
    const isFav = favIcon.classList.contains("fas");

    // Temporary pop animation
    favIcon.classList.add("active");
    setTimeout(() => favIcon.classList.remove("active"), 200);

    // Toggle Font Awesome classes
    favIcon.classList.toggle("fas", !isFav);
    favIcon.classList.toggle("far", isFav);

    const url = `/toggle_favorite/${encodeURIComponent(currentSymbol)}?
                 name=${encodeURIComponent(currentName)}`;

    console.log(" url " + url);
    fetch(url, { method: "POST" })
      .then(resp => resp.json())
      .then(data => console.log("Favorite updated:", data))
      .catch(err => console.error("Error updating favorite:", err));
  });

  // ===== Chart helpers =====
  function toOhlcData(rawData) {
    return rawData.map(point => {
      const t = formatPointTime(point.x);
      return {
        time: t.chartTime,
        open: point.o,
        high: point.h,
        low: point.l,
        close: point.c
      };
    });
  }

  function toLineData(rawData) {
    return rawData.map(point => {
      const t = formatPointTime(point.x);
      return { time: t.chartTime, value: point.c };
    });
  }

  // Get milliseconds per bar for each interval
  // Get seconds per bar for each interval
  function getIntervalSec(interval) {
    const intervalMap = {
      '30m': 30 * 60,
      '1h': 60 * 60,
      '4h': 4 * 60 * 60,
      '1d': 24 * 60 * 60,
      '1wk': 7 * 24 * 60 * 60
    };
    return intervalMap[interval] || 24 * 60 * 60;
  }

  // Lightweight Charts colors
  const colors = {
    upColor: '#26a69a',
    downColor: '#ef5350',
    borderUpColor: '#26a69a',
    borderDownColor: '#ef5350',
    wickUpColor: '#26a69a',
    wickDownColor: '#ef5350',
    lineColor: '#2962FF',
    lineWidth: 2,
  };

  // Create chart instance
  function createChart() {
    const container = document.getElementById('stockChart');
    const containerParent = container.parentElement;
    
    // CrosshairMode may be at different location depending on version
    const CrosshairMode = LightweightCharts.CrosshairMode || { Normal: 0 };
    
    const chartOptions = {
      width: containerParent.clientWidth - 32,
      height: 400,
      layout: {
        background: { type: 'solid', color: 'white' },
        textColor: '#333',
      },
      grid: {
        vertLines: { color: '#f0f0f0' },
        horzLines: { color: '#f0f0f0' },
      },
      crosshair: {
        mode: typeof CrosshairMode === 'object' ? CrosshairMode.Normal : CrosshairMode.Normal,
      },
      rightPriceScale: {
        borderColor: '#cccccc',
      },
      timeScale: {
        borderColor: '#cccccc',
        timeVisible: true,
        secondsVisible: false,
      },
    };

    console.log('Creating chart with options:', chartOptions);
    chart = LightweightCharts.createChart(container, chartOptions);
    console.log('Chart created successfully');

    // Handle window resize
    window.addEventListener('resize', () => {
      if (chart) {
        chart.applyOptions({ width: containerParent.clientWidth - 32 });
      }
    });

    return chart;
  }

  // Ensure Y-axis (price scale) is auto-scaled to the currently visible bars.
  // In some LightweightCharts builds the initial autoscale computation may lag
  // behind the initial fitContent()/setData(). Calling this explicitly after
  // data/time-scale changes makes the Y range fit the presented data.
  function autoFitPriceScale() {
    if (!chart) return;
    try {
      // v3+: chart.priceScale('right')
      if (typeof chart.priceScale === 'function') {
        const ps = chart.priceScale('right');
        if (ps && typeof ps.applyOptions === 'function') {
          ps.applyOptions({
            autoScale: true,
            // Slight margins improve readability while still using most of the UI.
            scaleMargins: { top: 0.08, bottom: 0.08 },
          });
        }
      }

      // Also try to enforce autoscale on the series price scale (when available)
      if (series && typeof series.priceScale === 'function') {
        const sps = series.priceScale();
        if (sps && typeof sps.applyOptions === 'function') {
          sps.applyOptions({ autoScale: true });
        }
      }
    } catch (e) {
      console.warn('autoFitPriceScale failed (non-fatal):', e);
    }
  }

  // Create series based on type
  function createSeries(type) {
    const ohlcData = toOhlcData(rawOhlc);
    const lineData = toLineData(rawOhlc);

    console.log('=== createSeries called ===');
    console.log('Type:', type);
    console.log('Chart object:', chart);
    
    // Check all available methods
    if (chart) {
      console.log('Chart own methods:', Object.keys(chart));
      try {
        const protoMethods = Object.getOwnPropertyNames(Object.getPrototypeOf(chart));
        console.log('Chart prototype methods:', protoMethods);
      } catch (e) {
        console.log('Could not get prototype methods');
      }
      console.log('addCandlestickSeries exists:', typeof chart.addCandlestickSeries);
      console.log('addLineSeries exists:', typeof chart.addLineSeries);
      console.log('addSeries exists:', typeof chart.addSeries);
    }
    
    if (series) {
      try {
        chart.removeSeries(series);
      } catch (e) {
        console.warn('Could not remove series:', e);
      }
    }

    try {
      if (type === 'line') {
        console.log('Creating line series...');
        series = chart.addLineSeries({
          color: colors.lineColor,
          lineWidth: colors.lineWidth,
        });
        series.setData(lineData);
      } else if (type === 'candlestick' || type === 'ohlc') {
        console.log('Creating candlestick series...');
        series = chart.addCandlestickSeries({
          upColor: colors.upColor,
          downColor: colors.downColor,
          borderUpColor: colors.borderUpColor,
          borderDownColor: colors.borderDownColor,
          wickUpColor: colors.wickUpColor,
          wickDownColor: colors.wickDownColor,
        });
        series.setData(ohlcData);
      }
      console.log('Series created successfully:', series);
    } catch (error) {
      console.error('=== ERROR creating series ===');
      console.error('Error message:', error.message);
      console.error('Error stack:', error.stack);
      throw error;
    }

    return series;
  }

  // Switch chart type
  function switchChartType(newType) {
    chartType = newType;
    createSeries(newType);
    // New series may have different scale; refresh autoscale
    requestAnimationFrame(autoFitPriceScale);

    // Update button styles
    document.getElementById("btn-line").classList.toggle("chart-btn-active", newType === "line");
    document.getElementById("btn-candlestick").classList.toggle("chart-btn-active", newType === "candlestick");
    document.getElementById("btn-ohlc").classList.toggle("chart-btn-active", newType === "ohlc");
  }

  // Load data for interval
  function loadData(interval, intervalButton, oldIntervalButton) {
    // Clear cache when changing interval
    dataCache.clear();
    chartInterval = interval;

    fetch(`/get_ohlc?symbol=${currentSymbol}&interval=${interval}`)
      .then((response) => response.json())
      .then((data) => {
        rawOhlc = data.ohlc;
        
        // Initialize cache with new data
        initCache(rawOhlc);

        // Update series with new data
        if (chartType === "line") {
          series.setData(toLineData(rawOhlc));
        } else {
          series.setData(toOhlcData(rawOhlc));
        }

        // Fit content to show all data
        chart.timeScale().fitContent();
        // Ensure the Y range matches the now-visible data
        requestAnimationFrame(autoFitPriceScale);

        intervalButton.classList.add("chart-btn-active");
        oldIntervalButton.classList.remove("chart-btn-active");
      });
  }

  // Check if the viewport extends beyond cached data
  // NOTE: startTimestamp and endTimestamp here should be in milliseconds
  function viewportNeedsFetch(startTimestamp, endTimestamp) {
    const cacheBounds = getCacheBounds();
    if (!cacheBounds) return true;

    const buffer = Math.floor(getIntervalSec(chartInterval) / 2);
    const viewportExtendsLeft = startTimestamp < cacheBounds.min - buffer;
    const viewportExtendsRight = endTimestamp > cacheBounds.max + buffer;
    if (!viewportExtendsLeft && !viewportExtendsRight) {
      console.log('Using cached data (cache bounds:', 
                  new Date(cacheBounds.min * 1000).toLocaleDateString(), '-', 
                  new Date(cacheBounds.max * 1000).toLocaleDateString() + ')');
      return false;
    }

    console.log('Viewport extends beyond cache:', 
                viewportExtendsLeft ? 'LEFT' : '', 
                viewportExtendsRight ? 'RIGHT' : '',
                '(viewport:', new Date(startTimestamp * 1000).toLocaleDateString(), '-', new Date(endTimestamp * 1000).toLocaleDateString() + ')',
                '(cache:', new Date(cacheBounds.min * 1000).toLocaleDateString(), '-', new Date(cacheBounds.max * 1000).toLocaleDateString() + ')');
    return true;
  }

  // Re-check if the current viewport still needs more data after a fetch completes
  function checkViewportAfterFetch() {
    if (pendingViewport) {
      const { startDate, endDate } = pendingViewport;
      pendingViewport = null;
      // Normalize pending viewport values to milliseconds
      const startTimestamp = (startDate > 1e12) ? startDate : Math.floor(startDate * 1000);
      const endTimestamp = (endDate > 1e12) ? endDate : Math.floor(endDate * 1000);

      if (viewportNeedsFetch(startTimestamp, endTimestamp)) {
        console.log('Viewport still needs more data after fetch, fetching again...');
        fetchAndLoadData(startDate, endDate, true);
      }
    }
  }

  // Fetch data for visible range when pan extends beyond cached data
  // startDate/endDate passed may be either ms timestamps or seconds depending on
  // the LightweightCharts callback — normalize to milliseconds for cache comparisons
  function fetchAndLoadData(startDate, endDate, showOverlay = true) {
    const startTimestamp = (startDate > 1e12) ? startDate : Math.floor(startDate * 1000);
    const endTimestamp = (endDate > 1e12) ? endDate : Math.floor(endDate * 1000);
    
    // Before fetching, check if cache already has near-complete coverage for this range
    const startSec = Math.floor(startTimestamp / 1000);
    const endSec = Math.floor(endTimestamp / 1000);
    if (cacheHasFullRange(startSec, endSec)) {
      console.log('Cache already covers requested range, skipping fetch');
      return;
    }

    // Check if viewport extends beyond cached data bounds
    if (!viewportNeedsFetch(startTimestamp, endTimestamp)) {
      console.log('Viewport within cached data, no fetch needed');
      return;
    }

    // If a fetch is already in flight, save this viewport as pending and return
    if (fetchInFlight) {
      console.log('Fetch already in flight, saving viewport as pending');
      pendingViewport = { startDate, endDate };
      return;
    }

    // Mark fetch as in flight
    fetchInFlight = true;
    
    // Need to fetch from server
    if (showOverlay) showLoadingOverlay();
    
    // Convert to ISO using millisecond timestamps and encode the values for the URL
    const startIso = new Date(Number(startTimestamp)).toISOString();
    const endIso = new Date(Number(endTimestamp)).toISOString();
    const startDateStr = encodeURIComponent(startIso);
    const endDateStr = encodeURIComponent(endIso);

    console.log('Fetching range:', startIso, endIso);

    fetch(`/get_ohlc_range?symbol=${encodeURIComponent(currentSymbol)}&interval=${encodeURIComponent(chartInterval)}&start=${startDateStr}&end=${endDateStr}`)
      .then((response) => response.json())
      .then((data) => {
        if (data.error) {
          console.error('Error fetching range:', data.error);
          return;
        }
        
        if (!data.ohlc || data.ohlc.length === 0) {
          console.warn('No data returned for range:', startDateStr, 'to', endDateStr);
          return;
        }
        
        console.log('Received', data.ohlc.length, 'data points for range');
        
        // Add fetched data to cache
        addToCache(data.ohlc);
        
        // Get all cached data (including newly fetched)
        const allCachedData = getAllCachedData();

        // Update series with all cached data
        if (chartType === "line") {
          series.setData(allCachedData.map(d => ({ time: d.time, value: d.close })));
        } else {
          series.setData(allCachedData);
        }

        // Data set changed for the currently visible window -> refresh autoscale
        requestAnimationFrame(autoFitPriceScale);
      })
      .catch((err) => {
        console.error('Pan fetch error:', err);
      })
      .finally(() => {
        fetchInFlight = false;
        if (showOverlay) hideLoadingOverlay();
        // Re-check if viewport still needs more data (e.g., user panned further during fetch)
        checkViewportAfterFetch();
      });
  }

  // ===== Initialize chart =====
  currIntervalButton = document.getElementById("btn-1d");
  
  // Initialize data cache with initial data
  initCache(rawOhlc);
  
  // Create chart and series
  chart = createChart();
  series = createSeries(chartType);
  
  // Fit content to show all data
  chart.timeScale().fitContent();
  // Ensure Y-axis fits the initial visible data
  requestAnimationFrame(autoFitPriceScale);

  // ===== Event listeners =====
  // Interval buttons
  document.querySelectorAll(".interval-button").forEach((button) => {
    button.addEventListener("click", () => {
      loadData(button.dataset.interval, button, currIntervalButton);
      currIntervalButton = button;
    });
  });

  // Chart type buttons
  document.getElementById("btn-line").addEventListener("click", () => switchChartType("line"));
  document.getElementById("btn-candlestick").addEventListener("click", () => switchChartType("candlestick"));
  document.getElementById("btn-ohlc").addEventListener("click", () => switchChartType("ohlc"));

  // Reset zoom button - fit content to show all data
  document.getElementById("btn-reset-zoom").addEventListener("click", () => {
    chart.timeScale().fitContent();
    requestAnimationFrame(autoFitPriceScale);
  });

  // Use getVisibleRange() explicitly (more consistent across versions) and normalize to ms
  let initialVisibleRangeIgnored = true;
  chart.timeScale().subscribeVisibleTimeRangeChange(() => {
    // We intentionally ignore the provided timeRange payload and call getVisibleRange()
    const vr = chart.timeScale().getVisibleRange();
    if (!vr) return;

    // vr.from/vr.to can be in several shapes depending on LightweightCharts build:
    // - numeric seconds (or ms)
    // - objects representing business days: {year, month, day}
    // - objects with a 'time' or 'timestamp' field
    const rawFrom = vr.from;
    const rawTo = vr.to;

    function normalizeVisibleValue(v) {
      if (v == null) return null;
      // numeric
      if (typeof v === 'number') return v > 1e12 ? Math.floor(v / 1000) : Math.floor(v);
      // object with time/timestamp
      if (typeof v === 'object') {
        if (typeof v.time === 'number') return v.time > 1e12 ? Math.floor(v.time / 1000) : Math.floor(v.time);
        if (typeof v.timestamp === 'number') return v.timestamp > 1e12 ? Math.floor(v.timestamp / 1000) : Math.floor(v.timestamp);
        // business day object {year, month, day} - convert to UTC midnight seconds
        if (v.year && v.month && v.day) {
          const utc = Date.UTC(Number(v.year), Number(v.month) - 1, Number(v.day));
          return Math.floor(utc / 1000);
        }
        // fallback: try parsing string representation
        const asStr = String(v);
        const parsed = Date.parse(asStr);
        if (!isNaN(parsed)) return Math.floor(parsed / 1000);
      }
      return NaN;
    }

    // Normalize to seconds for internal comparisons
    const startSec = normalizeVisibleValue(rawFrom);
    const endSec = normalizeVisibleValue(rawTo);

    // Debug logs to help validate units and decisions
    console.log('visibleRange via getVisibleRange:', { rawFrom, rawTo, startSec, endSec });
    const cacheBounds = getCacheBounds();
    if (cacheBounds) console.log('cacheBounds sec:', cacheBounds);

    // Ignore initial callback (chart initialization) to avoid fetching on load
    if (initialVisibleRangeIgnored) {
      initialVisibleRangeIgnored = false;
      return;
    }

    // When the user pans/zooms, keep Y-axis fitted to the currently visible window.
    // (Debounced fetch below will update data as needed, but we can autoscale
    // immediately to improve perceived responsiveness.)
    requestAnimationFrame(autoFitPriceScale);

    // Debounce fetches
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      // If the chart won't move further left because data starts at cache.min,
      // proactively request the previous window (one viewport width) so panning left
      // will be populated.
      const cacheBounds = getCacheBounds();
      if (cacheBounds && startSec <= cacheBounds.min + Math.floor(getIntervalSec(chartInterval) / 2)) {
        const viewportWidthSec = endSec - startSec;
        const fetchStartSec = cacheBounds.min - viewportWidthSec;
        const fetchEndSec = cacheBounds.min - 1; // up to just before cached min
        console.log('User panned to left edge; fetching previous window (sec):', fetchStartSec, fetchEndSec);
        fetchAndLoadData(fetchStartSec, fetchEndSec, true);
      } else {
        fetchAndLoadData(startSec, endSec, true);
      }
    }, DEBOUNCE_MS);
  });

} // end initLightweightChart

// Initialize immediately if DOM already loaded, otherwise wait for DOMContentLoaded
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initLightweightChart);
} else {
  initLightweightChart();
}