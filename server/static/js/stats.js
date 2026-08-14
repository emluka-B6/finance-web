
  document.addEventListener("DOMContentLoaded", () => {
    //Option3
    // const dataElement = document.getElementById("stats-data");
    // if (!dataElement) 
    //     return;
    // const { hours, counts } = JSON.parse(dataElement.textContent);

    const ctx = document.getElementById("activityChart");
    new Chart(ctx, {
        type: "bar",
        data: {
        labels: hours,
        datasets: [{
            label: "Hourly Activity",
            data: counts,
            backgroundColor: "rgba(54, 162, 235, 0.6)",
            borderColor: 'rgba(54, 162, 235, 1)',
            borderWidth: 1,
            borderRadius: 5            
        }]
        },
        options: {
        scales: {
            x: { title: { display: true, text: "Hour" } },
            y: { title: { display: true, text: "Activity Count" }, beginAtZero: true }
        }
        }
    });
});