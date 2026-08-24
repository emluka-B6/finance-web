document.addEventListener("DOMContentLoaded", () => {
  const config = window.CHART_CONFIG;

  // ===== State =====
  let currentSymbol = config.symbol;
  let currentName = config.name;
  let rawOhlc = config.ohlcData;
  let ohlc;
  let chartType = "candlestick";
  let chartInterval = "1d";
  let stockChart;
  let currIntervalButton;

  // ===== Custom Pan State =====
  let isPanning = false;
  let panStartX = 0;
  let panStartMin = null;
  let panStartMax = null;
  let panThreshold = 5; // Minimum pixels to trigger pan
  let initialViewportWidth = null; // Track the viewport width for maintaining size
  let isLoading = false; // Flag to prevent interactions during loading
  let fetchInFlight = false;
  let pendingViewport = null;

  // ===== Data Cache =====
  // Cache stores all fetched OHLC data to avoid redundant API calls
  // Key: timestamp (ms), Value: {x, o, h, l, c}
  const dataCache = new Map();

  // Initialize cache with initial data
  function initCache(rawData) {
    rawData.forEach(point => {
      const timestamp = Date.parse(point.x);
      dataCache.set(timestamp, {
        x: timestamp,
        o: point.o,
        h: point.h,
        l: point.l,
        c: point.c
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

  // Add data to cache
  function addToCache(rawData) {
    rawData.forEach(point => {
      const timestamp = Date.parse(point.x);
      dataCache.set(timestamp, {
        x: timestamp,
        o: point.o,
        h: point.h,
        l: point.l,
        c: point.c
      });
    });
  }

  // Check if cache has data for the entire requested range
  function cacheHasRange(minTime, maxTime) {
    // We need at least one data point in the range
    for (const timestamp of dataCache.keys()) {
      if (timestamp >= minTime && timestamp <= maxTime) {
        return true;
      }
    }
    return false;
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
    // Toggle icon state
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
  const isAxisShortLabel = (interval) => {
    return interval === "1d" || interval === "1wk" || interval === "4h";
  };

  const isTooltipShortLabel = (interval) => {
    return interval === "1d" || interval === "1wk";
  };

  function createTimeScale(interval) {
    return {
      type: "timeseries",
      adapters: {
        date: {
          locale: "en-GB", // <-- explicitly override browser locale
        },
      },
      time: {
        unit: isTooltipShortLabel(interval) ? "day" : "hour",
      },
      ticks: {
        source: "auto", // source of tick is X time, not X data index
        autoSkip: true,
        maxRotation: 0,
        maxTicksLimit: 5,
        minTicksLimit: 5,
        callback: function (value) {
          const date = new Date(value);
          const pad = (n) => String(n).padStart(2, "0");
          if (isAxisShortLabel(interval)) {
            // → 02/10/2025
            return `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()}`;
          } else {
            // → 02/10/2025 09:30
            return `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
          }
        },
      },
    };
  }

  function createTooltip(context) {
    const date = new Date(context[0].parsed.x);

    if (isTooltipShortLabel(chartInterval)) {
      // → 02.10.2025
      return date.toLocaleDateString("en-GB", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      });
    } else {
      // → 02.10.2025 09:30
      return date
        .toLocaleString("en-GB", {
          day: "2-digit",
          month: "2-digit",
          year: "numeric",
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
        })
        .replace(",", ""); // removes the comma between date and time in some locales
    }
  }

  function createDataset(type) {
    let dataset;
    if (type === "line") {
      dataset = {
        data: rawOhlc.map((d) => ({ x: Date.parse(d.x), y: d.c })),
        borderColor: "blue",
        backgroundColor: "lightblue",
        fill: false,
        tension: 0.3,
      };
    } else {
      dataset = {
        data: ohlc,
        color: {
          up: "green",
          down: "red",
          unchanged: "gray",
        },
      };
    }
    return dataset;
  }

  function createChart(type) {
    return new Chart(ctx, {
      type: type,
      data: {
        datasets: [createDataset(type)],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          tooltip: {
            mode: "index",
            intersect: false,
            callbacks: { title: createTooltip },
          },
          legend: { display: false },
          zoom: {
            pan: {
              enabled: false, // Disable default pan, we use custom handling
              mode: "x",
            },
            zoom: {
              wheel: {
                enabled: true,
              },
              mode: "x",
              onZoomComplete: function() {
                // Update the tracked viewport width after zoom
                const scale = stockChart.scales.x;
                initialViewportWidth = scale.max - scale.min;
              }
            },
          },
        },
        scales: { 
          x: createTimeScale(chartInterval),
          y: {
            beginAtZero: false,
          }
        },
      },
    });
  }

  function switchChartType(newType) {
    chartType = newType;
    stockChart.destroy();
    stockChart = createChart(chartType);

    // Update button styles
    document.getElementById("btn-line").classList.toggle("chart-btn-active", newType === "line");
    document.getElementById("btn-candlestick").classList.toggle("chart-btn-active", newType === "candlestick");
    document.getElementById("btn-ohlc").classList.toggle("chart-btn-active", newType === "ohlc");
  }

  function toOhlc(_rawOhlc) {
    return _rawOhlc.map((point) => ({
      x: Date.parse(point.x),
      o: point.o,
      h: point.h,
      l: point.l,
      c: point.c,
    }));
  }

  function loadData(interval, intervalButton, oldIntervalButton) {
    // Clear cache when changing interval
    dataCache.clear();
    chartInterval = interval;

    fetch(`/get_ohlc?symbol=${currentSymbol}&interval=${interval}`)
      .then((response) => response.json())
      .then((data) => {
        rawOhlc = data.ohlc;
        ohlc = toOhlc(rawOhlc);
        
        // Initialize cache with new data
        initCache(rawOhlc);

        if (chartType === "line")
          stockChart.data.datasets[0].data = rawOhlc.map((d) => ({ x: Date.parse(d.x), y: d.c }));
        else 
          stockChart.data.datasets[0].data = ohlc;

        stockChart.options.scales.x = createTimeScale(chartInterval);
        stockChart.update();
        // Reset zoom so the full new dataset is visible
        stockChart.resetZoom();

        intervalButton.classList.add("chart-btn-active");
        oldIntervalButton.classList.remove("chart-btn-active");
      });
  }

  // ===== Initialize chart =====
  const ctx = document.getElementById("stockChart").getContext("2d");
  currIntervalButton = document.getElementById("btn-1d");
  ohlc = toOhlc(rawOhlc);
  
  // Initialize data cache with initial data
  initCache(rawOhlc);
  
  stockChart = createChart(chartType);
  
  // Initialize viewport width tracking
  setTimeout(() => {
    const scale = stockChart.scales.x;
    initialViewportWidth = scale.max - scale.min;
  }, 100);

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

  // Reset zoom button
  document.getElementById("btn-reset-zoom").addEventListener("click", () => {
    stockChart.resetZoom();
  });

  // ===== Custom Pan Implementation =====
  // This implements true viewport panning: panning shifts the visible window
  // by fetching new data instead of extending the range (which looks like zoom out)

  function getViewportRange() {
    const scale = stockChart.scales.x;
    return { min: scale.min, max: scale.max };
  }

  // Get all cached data for display (for use during pan visual feedback)
  function getAllCachedData() {
    const allData = Array.from(dataCache.values()).sort((a, b) => a.x - b.x);
    return allData;
  }

  // Check if cache has data for the requested range (even partially)
  function hasDataInRange(minTime, maxTime) {
    for (const timestamp of dataCache.keys()) {
      if (timestamp >= minTime && timestamp <= maxTime) {
        return true;
      }
    }
    return false;
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

  function updateDatasetFromCache() {
    const allCachedData = getAllCachedData();
    if (allCachedData.length > 0) {
      if (chartType === "line")
        stockChart.data.datasets[0].data = allCachedData.map((d) => ({ x: d.x, y: d.c }));
      else
        stockChart.data.datasets[0].data = allCachedData;
    }
  }

  // Match Lightweight Charts' cache-bound check. The half-bar tolerance avoids
  // refetches caused by timestamp rounding at the first or last visible bar.
  function viewportNeedsFetch(startDate, endDate) {
    const cacheBounds = getCacheBounds();
    if (!cacheBounds) return true;

    const boundaryTolerance = getIntervalMs(chartInterval) / 2;
    const viewportExtendsLeft = startDate < cacheBounds.min - boundaryTolerance;
    const viewportExtendsRight = endDate > cacheBounds.max + boundaryTolerance;

    if (!viewportExtendsLeft && !viewportExtendsRight) {
      const cachedDataInRange = getFromCache(startDate, endDate);
      console.log('Using cached data:', cachedDataInRange.length, 'points (cache bounds:',
                  new Date(cacheBounds.min).toLocaleDateString(), '-',
                  new Date(cacheBounds.max).toLocaleDateString() + ')');
      return false;
    }

    console.log('Viewport extends beyond cache:',
                viewportExtendsLeft ? 'LEFT' : '',
                viewportExtendsRight ? 'RIGHT' : '',
                '(viewport:', new Date(startDate).toLocaleDateString(), '-', new Date(endDate).toLocaleDateString() + ')',
                '(cache:', new Date(cacheBounds.min).toLocaleDateString(), '-', new Date(cacheBounds.max).toLocaleDateString() + ')');
    return true;
  }

  function checkViewportAfterFetch() {
    if (!pendingViewport) return;

    const { startDate, endDate } = pendingViewport;
    pendingViewport = null;
    if (viewportNeedsFetch(startDate, endDate)) {
      fetchAndLoadData(startDate, endDate);
    }
  }

  function fetchAndLoadData(startDate, endDate, showOverlay = true) {
    // Always show every cached bar while panning, so cached buffer data is
    // immediately available before a request is necessary.
    updateDatasetFromCache();

    // Check if viewport extends beyond cached data bounds.
    const cacheBounds = getCacheBounds();
    if (!viewportNeedsFetch(startDate, endDate)) {
      stockChart.zoomScale('x', { min: startDate, max: endDate }, 'none');
      return;
    }

    // Do not issue overlapping range requests. Preserve the most recent user
    // viewport and evaluate it against the expanded cache when this fetch ends.
    if (fetchInFlight) {
      pendingViewport = { startDate, endDate };
      return;
    }

    fetchInFlight = true;
    // Need to fetch from server
    if (showOverlay) showLoadingOverlay();

    const boundaryTolerance = getIntervalMs(chartInterval) / 2;
    const viewportWidth = Math.max(endDate - startDate, getIntervalMs(chartInterval));
    const viewportExtendsLeft = !cacheBounds || startDate < cacheBounds.min - boundaryTolerance;
    const viewportExtendsRight = !cacheBounds || endDate > cacheBounds.max + boundaryTolerance;

    // Fetch one extra visible window in the direction being explored. This is
    // the cache buffer that reduces repeated /get_ohlc_range calls on panning.
    const fetchStart = viewportExtendsLeft ? startDate - viewportWidth : startDate;
    const fetchEnd = viewportExtendsRight ? endDate + viewportWidth : endDate;
    const startDateStr = encodeURIComponent(new Date(fetchStart).toISOString());
    const endDateStr = encodeURIComponent(new Date(fetchEnd).toISOString());

    fetch(`/get_ohlc_range?symbol=${encodeURIComponent(currentSymbol)}&interval=${encodeURIComponent(chartInterval)}&start=${startDateStr}&end=${endDateStr}`)
      .then((response) => response.json())
      .then((data) => {
        if (data.error) {
          console.error('Error fetching range:', data.error);
          return;
        }
        
        if (!data.ohlc || data.ohlc.length === 0) {
          console.warn('No data returned for range:', startDateStr, 'to', endDateStr);
          // Still update viewport even if no data
          stockChart.zoomScale('x', { min: startDate, max: endDate }, 'none');
          return;
        }
        
        console.log('Received', data.ohlc.length, 'data points for range');
        
        // Add fetched data to cache
        addToCache(data.ohlc);
        
        // Display all cached data, including the extra prefetch buffer.
        updateDatasetFromCache();

        // Set the viewport by zooming to the new range
        stockChart.zoomScale('x', { min: startDate, max: endDate }, 'none');
        
        // Update viewport width tracking
        initialViewportWidth = endDate - startDate;
      })
      .catch((err) => {
        console.error('Pan fetch error:', err);
        // Still update viewport even on error
        stockChart.zoomScale('x', { min: startDate, max: endDate }, 'none');
      })
      .finally(() => {
        fetchInFlight = false;
        if (showOverlay) hideLoadingOverlay();
        checkViewportAfterFetch();
      });
  }
  
  // Get milliseconds per bar for each interval
  function getIntervalMs(interval) {
    const intervalMap = {
      '30m': 30 * 60 * 1000,
      '1h': 60 * 60 * 1000,
      '4h': 4 * 60 * 60 * 1000,
      '1d': 24 * 60 * 60 * 1000,
      '1wk': 7 * 24 * 60 * 60 * 1000
    };
    return intervalMap[interval] || 24 * 60 * 60 * 1000; // default to 1 day
  }

  // Mouse down - start pan
  ctx.canvas.addEventListener('mousedown', (e) => {
    if (isLoading) return; // Prevent panning while loading
    isPanning = true;
    panStartX = e.clientX;
    const range = getViewportRange();
    panStartMin = range.min;
    panStartMax = range.max;
    
    // Ensure all cached data is in the dataset for smooth panning
    const allCachedData = getAllCachedData();
    if (chartType === "line")
      stockChart.data.datasets[0].data = allCachedData.map((d) => ({ x: d.x, y: d.c }));
    else
      stockChart.data.datasets[0].data = allCachedData;
    
    ctx.canvas.style.cursor = 'grabbing';
    e.preventDefault();
  });

  // Mouse move - calculate pan distance
  ctx.canvas.addEventListener('mousemove', (e) => {
    if (!isPanning) return;
    
    const deltaX = e.clientX - panStartX;
    
    // Visual feedback during pan - shift the visible range
    const viewportWidth = panStartMax - panStartMin;
    const pixelWidth = ctx.canvas.clientWidth;
    
    // Calculate the time shift based on pixel movement (inverted for natural drag)
    const timeShift = (deltaX / pixelWidth) * viewportWidth;
    
    // Apply visual feedback - shift the axis range
    const newMin = panStartMin - timeShift;
    const newMax = panStartMax - timeShift;
    
    // Use zoomScale for visual feedback (this doesn't lock the axis)
    stockChart.zoomScale('x', { min: newMin, max: newMax }, 'none');
  });

  // Mouse up - complete pan
  ctx.canvas.addEventListener('mouseup', (e) => {
    if (!isPanning) return;
    isPanning = false;
    ctx.canvas.style.cursor = 'default';

    const deltaX = e.clientX - panStartX;
    
    // Only fetch new data if we actually moved
    if (Math.abs(deltaX) < panThreshold) {
      // Reset to original position if below threshold
      stockChart.zoomScale('x', { min: panStartMin, max: panStartMax }, 'none');
      return;
    }

    const viewportWidth = panStartMax - panStartMin;
    const pixelWidth = ctx.canvas.clientWidth;
    const timeShift = (deltaX / pixelWidth) * viewportWidth;

    const newMin = panStartMin - timeShift;
    const newMax = panStartMax - timeShift;

    // Fetch new data for the panned viewport
    fetchAndLoadData(newMin, newMax);
  });

  // Mouse leave - cancel pan (reset to start position)
  ctx.canvas.addEventListener('mouseleave', () => {
    if (!isPanning) return;
    
    isPanning = false;
    ctx.canvas.style.cursor = 'default';
    
    // Reset to original position
    stockChart.zoomScale('x', { min: panStartMin, max: panStartMax }, 'none');
  });

  // Prevent default drag behavior
  ctx.canvas.addEventListener('dragstart', (e) => e.preventDefault());
});
