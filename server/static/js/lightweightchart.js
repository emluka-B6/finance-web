// Lightweight Charts rendering and viewport integration.
// Shared OHLC caching and network requests are in chart-data-controller.js.
function initLightweightChart() {
  if (typeof LightweightCharts === "undefined") {
    console.error("LightweightCharts library not loaded");
    return;
  }

  const config = window.CHART_CONFIG;
  let currentSymbol = config.symbol;
  let currentName = config.name;
  let chartType = "candlestick";
  let chartInterval = "1d";
  let chart;
  let series;
  let currIntervalButton;
  let isLoading = false;
  let debounceTimer = null;
  const DEBOUNCE_MS = 300;

  function formatPointTime(pointX) {
    const raw = String(pointX);
    if (chartInterval === "1d") {
      const match = raw.match(/^(\d{4}-\d{2}-\d{2})/);
      const date = match ? match[1] : new Date(raw).toISOString().slice(0, 10);
      return date;
    }
    return Math.floor(Date.parse(raw) / 1000);
  }

  function toOhlcData(rawOhlc) {
    return rawOhlc.map((point) => ({
      time: formatPointTime(point.x), open: point.o, high: point.h, low: point.l, close: point.c,
    }));
  }

  function toLineData(rawOhlc) {
    return rawOhlc.map((point) => ({ time: formatPointTime(point.x), value: point.c }));
  }

  function setSeriesData(rawOhlc) {
    if (!series) return;
    series.setData(chartType === "line" ? toLineData(rawOhlc) : toOhlcData(rawOhlc));
  }

  const dataController = new ChartDataController({
    symbol: currentSymbol,
    initialOhlc: config.ohlcData,
    onDataChange: (rawOhlc, metadata) => {
      chartInterval = metadata.interval;
      setSeriesData(rawOhlc);
      requestAnimationFrame(autoFitPriceScale);
    },
    onLoadingChange: (loading) => { isLoading = loading; },
  });

  const colors = {
    upColor: "#26a69a", downColor: "#ef5350", borderUpColor: "#26a69a",
    borderDownColor: "#ef5350", wickUpColor: "#26a69a", wickDownColor: "#ef5350",
    lineColor: "#2962FF", lineWidth: 2,
  };

  function createChart() {
    const container = document.getElementById("stockChart");
    const containerParent = container.parentElement;
    chart = LightweightCharts.createChart(container, {
      width: containerParent.clientWidth - 32,
      height: 400,
      layout: { background: { type: "solid", color: "white" }, textColor: "#333" },
      grid: { vertLines: { color: "#f0f0f0" }, horzLines: { color: "#f0f0f0" } },
      crosshair: { mode: (LightweightCharts.CrosshairMode || { Normal: 0 }).Normal },
      rightPriceScale: { borderColor: "#cccccc" },
      timeScale: { borderColor: "#cccccc", timeVisible: true, secondsVisible: false },
    });
    window.addEventListener("resize", () => {
      if (chart) chart.applyOptions({ width: containerParent.clientWidth - 32 });
    });
    return chart;
  }

  function autoFitPriceScale() {
    try {
      const priceScale = chart && chart.priceScale && chart.priceScale("right");
      if (priceScale) priceScale.applyOptions({ autoScale: true, scaleMargins: { top: 0.08, bottom: 0.08 } });
      const seriesPriceScale = series && series.priceScale && series.priceScale();
      if (seriesPriceScale) seriesPriceScale.applyOptions({ autoScale: true });
    } catch (error) {
      console.warn("autoFitPriceScale failed (non-fatal):", error);
    }
  }

  function createSeries(type) {
    if (series) chart.removeSeries(series);
    if (type === "line") {
      series = chart.addLineSeries({ color: colors.lineColor, lineWidth: colors.lineWidth });
    } else {
      series = chart.addCandlestickSeries({
        upColor: colors.upColor, downColor: colors.downColor,
        borderUpColor: colors.borderUpColor, borderDownColor: colors.borderDownColor,
        wickUpColor: colors.wickUpColor, wickDownColor: colors.wickDownColor,
      });
    }
    setSeriesData(dataController.getData());
    return series;
  }

  function switchChartType(newType) {
    chartType = newType;
    createSeries(newType);
    requestAnimationFrame(autoFitPriceScale);
    document.getElementById("btn-line").classList.toggle("chart-btn-active", newType === "line");
    document.getElementById("btn-candlestick").classList.toggle("chart-btn-active", newType === "candlestick");
    document.getElementById("btn-ohlc").classList.toggle("chart-btn-active", newType === "ohlc");
  }

  async function loadData(interval, intervalButton, oldIntervalButton) {
    const changed = await dataController.changeInterval(interval);
    if (!changed || dataController.interval !== interval) return;
    chartInterval = interval;
    chart.timeScale().fitContent();
    requestAnimationFrame(autoFitPriceScale);
    intervalButton.classList.add("chart-btn-active");
    oldIntervalButton.classList.remove("chart-btn-active");
  }

  function normalizeVisibleValue(value) {
    if (typeof value === "number") return value > 1e12 ? value : value * 1000;
    if (value && typeof value === "object") {
      if (typeof value.time === "number") return value.time > 1e12 ? value.time : value.time * 1000;
      if (typeof value.timestamp === "number") return value.timestamp > 1e12 ? value.timestamp : value.timestamp * 1000;
      if (value.year && value.month && value.day) return Date.UTC(value.year, value.month - 1, value.day);
    }
    return NaN;
  }

  currIntervalButton = document.getElementById("btn-1d");
  chart = createChart();
  series = createSeries(chartType);
  chart.timeScale().fitContent();
  requestAnimationFrame(autoFitPriceScale);

  const favBtn = document.getElementById("fav-btn");
  const favIcon = document.getElementById("fav-icon");
  favBtn.addEventListener("click", () => {
    const isFav = favIcon.classList.contains("fas");
    favIcon.classList.add("active");
    setTimeout(() => favIcon.classList.remove("active"), 200);
    favIcon.classList.toggle("fas", !isFav);
    favIcon.classList.toggle("far", isFav);
    fetch(`/toggle_favorite/${encodeURIComponent(currentSymbol)}?name=${encodeURIComponent(currentName)}`, { method: "POST" })
      .then((response) => response.json()).then((data) => console.log("Favorite updated:", data))
      .catch((error) => console.error("Error updating favorite:", error));
  });

  document.querySelectorAll(".interval-button").forEach((button) => {
    button.addEventListener("click", () => {
      loadData(button.dataset.interval, button, currIntervalButton);
      currIntervalButton = button;
    });
  });
  document.getElementById("btn-line").addEventListener("click", () => switchChartType("line"));
  document.getElementById("btn-candlestick").addEventListener("click", () => switchChartType("candlestick"));
  document.getElementById("btn-ohlc").addEventListener("click", () => switchChartType("ohlc"));
  document.getElementById("btn-reset-zoom").addEventListener("click", () => {
    chart.timeScale().fitContent();
    requestAnimationFrame(autoFitPriceScale);
  });

  let initialVisibleRangeIgnored = true;
  chart.timeScale().subscribeVisibleTimeRangeChange(() => {
    const visibleRange = chart.timeScale().getVisibleRange();
    if (!visibleRange) return;
    const startDate = normalizeVisibleValue(visibleRange.from);
    const endDate = normalizeVisibleValue(visibleRange.to);
    if (!Number.isFinite(startDate) || !Number.isFinite(endDate)) return;
    if (initialVisibleRangeIgnored) {
      initialVisibleRangeIgnored = false;
      return;
    }
    requestAnimationFrame(autoFitPriceScale);
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      const cacheBounds = dataController.getCacheBounds();
      const intervalTolerance = dataController.getIntervalMs() / 2;
      if (cacheBounds && startDate <= cacheBounds.min + intervalTolerance) {
        // Lightweight Charts clamps at the earliest bar, so request the
        // preceding window when the user reaches the left data edge.
        dataController.loadPreviousWindow(endDate - startDate);
      } else {
        // Moving right toward newer data never triggers a network request.
        dataController.loadHistorical(startDate, endDate);
      }
    }, DEBOUNCE_MS);
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initLightweightChart);
} else {
  initLightweightChart();
}