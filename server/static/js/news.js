async function updateFavorites() {
    try {
        const response = await fetch("/favorites_data");
        if (!response.ok) {
            throw new Error(`Fetch error ${response.status}`);
        }
        const data = await response.json();

        const tbody = document.getElementById("favorites-body");

        data.forEach(item => {
            const tr = Array.from(tbody.rows).find(row => row.dataset.symbol === item.symbol);
            if (!tr) {
                return;
            }

            const changeClass = item.change >= 0 ? "text-success" : "text-danger";
            tr.querySelector(".favorite-price").textContent = item.price.toFixed(2);

            const changeCell = tr.querySelector(".favorite-change");
            changeCell.textContent = `${item.change.toFixed(2)}%`;
            changeCell.className = `favorite-change ${changeClass}`;

            tr.querySelector(".favorite-time").textContent = item.time;
        });
    } catch (err) {
        console.error("Error updating favorites:", err);
    }
}

// Update every 60 seconds
updateFavorites();
setInterval(updateFavorites, 60 * 1000);