async function updateFavorites() {
    try {
        const response = await fetch("/favorites_data");
        const data = await response.json();

        const tbody = document.getElementById("favorites-body");
        tbody.innerHTML = "";

        data.forEach(item => {
            const tr = document.createElement("tr");
            const changeClass = item.change >= 0 ? "text-success" : "text-danger";
            console.log("item name " + item.name);
            tr.innerHTML = `
                <td><a class="news-link" href="/chartjs/${item.symbol}">${item.name}</a></td>
                <td>${item.price.toFixed(2)}</td>
                <td class="${changeClass}">${item.change.toFixed(2)}%</td>
                <td>${item.time}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error("Error updating favorites:", err);
    }
}

// Update every 60 seconds
updateFavorites();
setInterval(updateFavorites, 60 * 1000);