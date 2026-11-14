async function loadMapPoints(flashId) {
    const data = await requestJson("/api/map-points");
    const map = document.getElementById("campusMap");
    map.querySelectorAll(".point").forEach(p => p.remove());
    data.points.forEach(p => {
        const el = document.createElement("button");
        el.className = pointClass(p.status) + (flashId === p.id ? " flash-point" : "");
        el.style.left = `${p.x}%`;
        el.style.top = `${p.y}%`;
        el.title = p.name;
        el.textContent = p.point_type[0].toUpperCase();
        el.onclick = () => showPoint(p, data.latest_alarm);
        map.appendChild(el);
    });
}

function showPoint(p, latest) {
    document.getElementById("pointDetail").innerHTML = `<p><strong>${p.name}</strong></p><p>类型：${p.point_type}</p><p>位置：${p.location}</p><p>状态：<span class="${statusClass(p.status)}">${p.status}</span></p><p>最近告警：${latest ? latest.event_type + " / " + latest.message : "暂无"}</p>`;
}

document.addEventListener("DOMContentLoaded", () => {
    loadMapPoints().catch(alert);
    setInterval(() => loadMapPoints().catch(() => {}), 8000);
    connectAlarmSocket(alarm => loadMapPoints(alarm.map_point_id).catch(() => {}));
});
