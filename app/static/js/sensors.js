async function loadSensors() {
    const sensors = await requestJson("/api/sensors");
    const data = await requestJson("/api/sensor-data");
    document.getElementById("sensorsBody").innerHTML = sensors.map(s => `<tr><td>${s.id}</td><td>${s.name}</td><td>${s.sensor_type}</td><td>${s.location}</td><td>${s.threshold_value}${s.unit}</td><td><span class="${statusClass(s.status)}">${s.status}</span></td></tr>`).join("");
    document.getElementById("sensorDataBody").innerHTML = data.map(d => `<tr><td>${formatTime(d.created_at)}</td><td>${d.sensor_name}</td><td>${d.sensor_type}</td><td>${d.location}</td><td>${d.value}${d.unit}</td><td>${d.threshold_value}${d.unit}</td></tr>`).join("");
    drawSensorChart(data.slice(0, 24).reverse());
}

function drawSensorChart(rows) {
    const max = Math.max(...rows.map(r => r.value), 1);
    document.getElementById("sensorChart").innerHTML = rows.map(r => `<div class="bar" title="${r.sensor_name} ${r.value}${r.unit}" style="height:${Math.max(8, r.value / max * 100)}%"></div>`).join("");
}

document.addEventListener("DOMContentLoaded", () => {
    loadSensors().catch(alert);
    setInterval(() => loadSensors().catch(() => {}), 5000);
    connectAlarmSocket(() => loadSensors().catch(() => {}));
    document.getElementById("sensorForm").addEventListener("submit", async e => {
        e.preventDefault();
        await requestJson("/api/sensors", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(formJson(e.target)) });
        e.target.reset();
        await loadSensors();
    });
    document.getElementById("sensorStart").onclick = () => requestJson("/api/sensors/simulate/start", { method: "POST" }).then(loadSensors);
    document.getElementById("sensorStop").onclick = () => requestJson("/api/sensors/simulate/stop", { method: "POST" }).then(loadSensors);
    document.querySelectorAll("[data-abnormal]").forEach(btn => btn.onclick = () => requestJson(`/api/sensors/simulate/abnormal?sensor_type=${btn.dataset.abnormal}`, { method: "POST" }).then(loadSensors));
});
