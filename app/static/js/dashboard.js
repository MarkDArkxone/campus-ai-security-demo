async function loadDashboard() {
    const stats = await requestJson("/api/dashboard/stats");
    document.getElementById("todayAlarm").textContent = stats.today_alarm_count;
    document.getElementById("highAlarm").textContent = stats.high_alarm_count;
    document.getElementById("onlineDevice").textContent = stats.online_device_count;
    document.getElementById("personCount").textContent = stats.current_person_count;

    const latest = document.getElementById("latestAlarms");
    latest.innerHTML = stats.latest_alarms.map(a => `
        <div class="alarm-card ${a.event_level === "high" ? "high-flash" : ""}">
            <div class="alarm-card-head">
                <strong>${a.event_type}</strong>
                <span class="${levelClass(a.event_level)}">${a.event_level}</span>
            </div>
            <p>${a.message}</p>
            <small>${formatTime(a.created_at)} · ${a.location || ""}</small>
        </div>
    `).join("") || "<div class='empty'>暂无告警</div>";
    restartAutoScroll(latest);

    drawBars(stats.alarm_type_stats, stats.alarm_trend_24h || []);
    const total = stats.online_device_count + stats.offline_device_count;
    document.getElementById("deviceRate").textContent = total ? `${Math.round(stats.online_device_count / total * 100)}%` : "0%";
    drawDashboardMap();
}

function drawBars(stats, trend) {
    const entries = Object.entries(stats);
    const max = Math.max(...entries.map(([, v]) => v), 1);
    document.getElementById("alarmBars").innerHTML = entries.map(([k, v]) => `
        <div class="stat-bar">
            <span>${k}</span>
            <i style="width:${v / max * 100}%"></i>
            <b>${v}</b>
        </div>
    `).join("") || "<div class='empty'>暂无数据</div>";

    const maxTrend = Math.max(...trend.map(item => item.count), 1);
    document.getElementById("trendLine").innerHTML = trend.map(item => `<i style="height:${Math.max(2, item.count / maxTrend * 120)}px" title="${item.hour} · ${item.count} 条"></i>`).join("") || "<div class='empty'>暂无趋势数据</div>";
}

async function drawDashboardMap(flashId) {
    const data = await requestJson("/api/map-points");
    const map = document.getElementById("dashboardMap");
    map.innerHTML = "<div class='dash-building d1'>教学楼</div><div class='dash-building d2'>宿舍</div><div class='dash-building d3'>食堂</div><div class='dash-building d4'>操场</div><div class='dash-building d5'>配电房</div>";
    data.points.forEach(p => {
        const el = document.createElement("span");
        el.className = pointClass(p.status) + (flashId === p.id ? " flash-point" : "");
        el.style.left = `${p.x}%`;
        el.style.top = `${p.y}%`;
        el.title = `${p.name} / ${p.location}`;
        el.textContent = p.point_type[0].toUpperCase();
        map.appendChild(el);
    });
}

function restartAutoScroll(container) {
    container.scrollTop = 0;
    if (window.dashboardScrollTimer) clearInterval(window.dashboardScrollTimer);
    window.dashboardScrollTimer = setInterval(() => {
        if (!container) return;
        if (container.scrollHeight <= container.clientHeight) return;
        container.scrollTop += 1;
        if (container.scrollTop + container.clientHeight >= container.scrollHeight - 2) {
            container.scrollTop = 0;
        }
    }, 80);
}

function tickTime() {
    document.getElementById("nowTime").textContent = formatTime(new Date());
}

document.addEventListener("DOMContentLoaded", () => {
    tickTime();
    setInterval(tickTime, 1000);
    loadDashboard().catch(alert);
    setInterval(() => loadDashboard().catch(() => {}), 5000);
    connectAlarmSocket(alarm => {
        loadDashboard().catch(() => {});
        drawDashboardMap(alarm.map_point_id).catch(() => {});
    });
});
