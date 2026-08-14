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
              enabled: true,
              mode: "x",
            },
            zoom: {
              wheel: {
                enabled: true,
                speed: 0.1,
              },
              pinch: {
                enabled: true,
              },
              drag: {
                enabled: true,
                modifierKey: "shift",
                backgroundColor: "rgba(0, 123, 255, 0.2)",
                borderColor: "rgba(0, 123, 255, 0.5)",
                borderWidth: 1,
              },
              mode: "x",
            },
          },
        },
        scales: { x: createTimeScale(chartInterval) },
      },
    });
  }

  function switchChartType(newType) {
    chartType = newType;
    stockChart.destroy();
    stockChart = createChart(chartType);

    // Update button styles
    document.getElementById("btn-line").classList.toggle("btn-primary", newType === "line");
    document.getElementById("btn-line").classList.toggle("btn-outline-primary", newType !== "line");

    document.getElementById("btn-candlestick").classList.toggle("btn-primary", newType === "candlestick");
    document.getElementById("btn-candlestick").classList.toggle("btn-outline-primary", newType !== "candlestick");

    document.getElementById("btn-ohlc").classList.toggle("btn-primary", newType === "ohlc");
    document.getElementById("btn-ohlc").classList.toggle("btn-outline-primary", newType !== "ohlc");
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
    fetch(`/get_ohlc?symbol=${currentSymbol}&interval=${interval}`)
      .then((response) => response.json())
      .then((data) => {
        rawOhlc = data.ohlc;
        ohlc = toOhlc(rawOhlc);
        chartInterval = interval;

        if (chartType === "line")
          stockChart.data.datasets[0].data = rawOhlc.map((d) => ({ x: Date.parse(d.x), y: d.c }));
        else 
          stockChart.data.datasets[0].data = ohlc;

        stockChart.options.scales.x = createTimeScale(chartInterval);
        stockChart.update();
        // Reset zoom so the full new dataset is visible
        stockChart.resetZoom();

        intervalButton.classList.remove("btn-outline-primary");
        intervalButton.classList.add("btn-primary");
        oldIntervalButton.classList.remove("btn-primary");
        oldIntervalButton.classList.add("btn-outline-primary");
      });
  }

  // ===== Initialize chart =====
  const ctx = document.getElementById("stockChart").getContext("2d");
  currIntervalButton = document.getElementById("btn-1d");
  ohlc = toOhlc(rawOhlc);
  stockChart = createChart(chartType);

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
});