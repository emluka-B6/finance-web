document.addEventListener("DOMContentLoaded", () => {
  const config = window.CHART_CONFIG;
  let currentSymbol = config.symbol;
  let currentName = config.name;
  let chartType = "candlestick";
  let chartInterval = "1d";
  let stockChart;
  let currIntervalButton;
  let isPanning = false;
  let panStartX = 0;
  let panStartMin = null;
  let panStartMax = null;
  const panThreshold = 5;
  let isLoading = false;

  function setDataset(rawOhlc) {
    stockChart.data.datasets[0].data = chartType === "line"
      ? rawOhlc.map((point) => ({ x: Date.parse(point.x), y: point.c }))
      : rawOhlc.map((point) => ({ x: Date.parse(point.x), o: point.o, h: point.h, l: point.l, c: point.c }));
  }

  const dataController = new ChartDataController({
    symbol: currentSymbol,
    initialOhlc: config.ohlcData,
    onDataChange: (rawOhlc, metadata) => {
      chartInterval = metadata.interval;
      setDataset(rawOhlc);
      stockChart.update("none");
      // Updating Chart.js data may otherwise recalculate the time scale. Keep
      // the viewport used for the historical request before the next pan.
      if (metadata.reason === "historical" && metadata.viewport) {
        stockChart.zoomScale("x", {
          min: metadata.viewport.startDate,
          max: metadata.viewport.endDate,
        }, "none");
      }
    },
    onLoadingChange: (loading) => { isLoading = loading; },
  });

  const isAxisShortLabel = (interval) => interval === "1d" || interval === "1wk" || interval === "4h";
  const isTooltipShortLabel = (interval) => interval === "1d" || interval === "1wk";

  function createTimeScale(interval) {
    return {
      type: "timeseries",
      adapters: { date: { locale: "en-GB" } },
      time: { unit: isTooltipShortLabel(interval) ? "day" : "hour" },
      ticks: {
        source: "auto", autoSkip: true, maxRotation: 0, maxTicksLimit: 5, minTicksLimit: 5,
        callback(value) {
          const date = new Date(value);
          const pad = (number) => String(number).padStart(2, "0");
          const dateLabel = `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()}`;
          return isAxisShortLabel(interval) ? dateLabel : `${dateLabel} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
        },
      },
    };
  }

  function createTooltip(context) {
    const date = new Date(context[0].parsed.x);
    return isTooltipShortLabel(chartInterval)
      ? date.toLocaleDateString("en-GB", { day: "2-digit", month: "2-digit", year: "numeric" })
      : date.toLocaleString("en-GB", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false }).replace(",", "");
  }

  function createDataset(type) {
    const rawOhlc = dataController.getData();
    return type === "line"
      ? { data: rawOhlc.map((point) => ({ x: Date.parse(point.x), y: point.c })), borderColor: "blue", backgroundColor: "lightblue", fill: false, tension: 0.3 }
      : { data: rawOhlc.map((point) => ({ x: Date.parse(point.x), o: point.o, h: point.h, l: point.l, c: point.c })), color: { up: "green", down: "red", unchanged: "gray" } };
  }

  function createChart(type) {
    return new Chart(ctx, {
      type,
      data: { datasets: [createDataset(type)] },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: {
          tooltip: { mode: "index", intersect: false, callbacks: { title: createTooltip } },
          legend: { display: false },
          zoom: { pan: { enabled: false, mode: "x" }, zoom: { wheel: { enabled: true }, mode: "x" } },
        },
        scales: { x: createTimeScale(chartInterval), y: { beginAtZero: false } },
      },
    });
  }

  function switchChartType(newType) {
    chartType = newType;
    stockChart.destroy();
    stockChart = createChart(chartType);
    document.getElementById("btn-line").classList.toggle("chart-btn-active", newType === "line");
    document.getElementById("btn-candlestick").classList.toggle("chart-btn-active", newType === "candlestick");
    document.getElementById("btn-ohlc").classList.toggle("chart-btn-active", newType === "ohlc");
  }

  async function loadData(interval, intervalButton, oldIntervalButton) {
    const changed = await dataController.changeInterval(interval);
    if (!changed || dataController.interval !== interval) return;
    chartInterval = interval;
    stockChart.options.scales.x = createTimeScale(chartInterval);
    stockChart.update();
    stockChart.resetZoom();
    intervalButton.classList.add("chart-btn-active");
    oldIntervalButton.classList.remove("chart-btn-active");
  }

  const ctx = document.getElementById("stockChart").getContext("2d");
  currIntervalButton = document.getElementById("btn-1d");
  stockChart = createChart(chartType);

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
  document.getElementById("btn-reset-zoom").addEventListener("click", () => stockChart.resetZoom());

  function getViewportRange() {
    const scale = stockChart.scales.x;
    return { min: scale.min, max: scale.max };
  }

  ctx.canvas.addEventListener("mousedown", (event) => {
    if (isLoading) return;
    isPanning = true;
    panStartX = event.clientX;
    ({ min: panStartMin, max: panStartMax } = getViewportRange());
    setDataset(dataController.getData());
    ctx.canvas.style.cursor = "grabbing";
    event.preventDefault();
  });
  ctx.canvas.addEventListener("mousemove", (event) => {
    if (!isPanning) return;
    const shift = ((event.clientX - panStartX) / ctx.canvas.clientWidth) * (panStartMax - panStartMin);
    stockChart.zoomScale("x", { min: panStartMin - shift, max: panStartMax - shift }, "none");
  });
  ctx.canvas.addEventListener("mouseup", (event) => {
    if (!isPanning) return;
    isPanning = false;
    ctx.canvas.style.cursor = "default";
    const deltaX = event.clientX - panStartX;
    if (Math.abs(deltaX) < panThreshold) {
      stockChart.zoomScale("x", { min: panStartMin, max: panStartMax }, "none");
      return;
    }
    const shift = (deltaX / ctx.canvas.clientWidth) * (panStartMax - panStartMin);
    dataController.loadHistorical(panStartMin - shift, panStartMax - shift);
  });
  ctx.canvas.addEventListener("mouseleave", () => {
    if (!isPanning) return;
    isPanning = false;
    ctx.canvas.style.cursor = "default";
    stockChart.zoomScale("x", { min: panStartMin, max: panStartMax }, "none");
  });
  ctx.canvas.addEventListener("dragstart", (event) => event.preventDefault());
});