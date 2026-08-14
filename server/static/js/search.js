let searchTimer = null;
let isFetching = false;
let pendingQuery = null;
let lastResults = [];
const tickersOutput = document.getElementById("search-results");
const tickersInputt = document.getElementById("ticker-search");

tickersOutput.classList.remove("show");

function showTickers(resultArray) {
  tickersOutput.innerHTML = "";
  resultArray.slice(0, 8).forEach(item => {

    const li = document.createElement("li");
    li.className = "list-group-item list-group-item-action";
    li.innerHTML = `<strong>${item.symbol}</strong> - ${item.name}`;

    console.log(" item.name " + item.name);
    li.onclick = () => {
      window.location.href = `/chartjs/${item.symbol}`;
    };
    tickersOutput.appendChild(li);
  });
  if (resultArray.length)
    tickersOutput.classList.add("show");
  else
    tickersOutput.classList.remove("show");
}

function fetchPendingTickers(query) {
    // process any query that arrived while fetching
    if (pendingQuery && pendingQuery !== query) {
      const nextQuery = pendingQuery;
      pendingQuery = null;
      fetchTickers(nextQuery);
    }
    else {
      //remove loading class
    }
}

function showLastTickers(query) {
  if (lastResults.length > 0) {
    const filtered = lastResults.filter(item =>
      item.name.toLowerCase().includes(query.toLowerCase()) ||
      item.symbol.toLowerCase().includes(query.toLowerCase())
    );

    if (filtered.length > 0) {
      showTickers(filtered);
      return true;
    }
  }
  return false;
}

function shoulPostpone(query) {
  // if a fetch is running, remember we have a pending query
  if (isFetching) {
    pendingQuery = query;
    return true;
  }
  return false;
}

async function fetchTickers(query) {
  if (shoulPostpone(query))
    return
  try {
    isFetching = true;
    //add loading class
    const response = await fetch(`/search_ttl_cache_ticker?q=${encodeURIComponent(query)}`);
    if (!response.ok) 
      throw new Error("Fetch error " + response.status);

    lastResults = await response.json();

    if (pendingQuery)
      showLastTickers(pendingQuery);
    else
      showTickers(lastResults);

  } catch (err) {
    console.error("Ticker search failed:", err);
  } finally {
    isFetching = false;
    fetchPendingTickers();
  }
}

// Debounce the input

tickersInputt.addEventListener("input", (e) => {
  const query = e.target.value.trim();
  if (!query || query.length < 3)
    return showTickers([]);

  showLastTickers(query);
  
  clearTimeout(searchTimer);                                        //cancel 400ms timer
  const FETCH_DELAY = 400;
  searchTimer = setTimeout(() => fetchTickers(query), FETCH_DELAY); //after 400ms call fetchTickers
});

// Hide on click outside
document.addEventListener("click", e => {
  if (!tickersOutput.contains(e.target) && e.target !== tickersInputt) {
    tickersOutput.classList.remove("show");
  }
});