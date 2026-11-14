const consoleState = {
    socket: null,
    reconnectTimer: null,
    mutedUntil: Number(sessionStorage.getItem("alarmMutedUntil") || 0),
    latestAlarm: null,
    alarmListeners: new Set(),
};

function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>'"]/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]);
}

async function requestJson(url, options = {}) {
    return window.CampusAPI.request(url, options);
}

function formJson(form) {
    const data = Object.fromEntries(new FormData(form).entries());
    for (const key of Object.keys(data)) {
        if (data[key] === "") data[key] = null;
        if (["threshold_value", "x", "y", "person_id", "device_id"].includes(key) && data[key] !== null) data[key] = Number(data[key]);
    }
    return data;
}

function formatTime(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "—";
    const parts = new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).formatToParts(date);
    const get = type => parts.find(part => part.type === type)?.value || "";
    return `${get("year")}-${get("month")}-${get("day")} ${get("hour")}:${get("minute")}:${get("second")}`;
}

function levelClass(level) {
    if (level === "high") return "level-high";
    if (level === "medium") return "level-medium";
    return "level-low";
}

function statusClass(status) {
    if (["alarm", "blacklist", "denied", "offline"].includes(status)) return "level-high";
    if (["warning", "disabled", "pending", "unhandled"].includes(status)) return "level-medium";
    return "level-low";
}

function pointClass(status) {
    if (status === "alarm") return "point alarm";
    if (status === "warning") return "point warning";
    if (status === "offline") return "point offline";
    return "point normal";
}

function showToast(message, type = "info") {
    const stack = document.getElementById("toastStack");
    if (!stack) return;
    const toast = document.createElement("div");
    toast.className = `toast ${type === "error" ? "error" : ""}`;
    toast.textContent = message;
    stack.appendChild(toast);
    setTimeout(() => toast.remove(), 3600);
}

function addAlarmCard(alarm) {
    const feed = document.getElementById("alarmFeed");
    if (!feed) return;
    feed.querySelector(".empty")?.remove();
    const item = document.createElement("div");
    item.className = "alarm-card flash";
    const snapshotUrl = alarm.snapshot_path ? window.CampusAPI.assetUrl(alarm.snapshot_path) : null;
    item.innerHTML = `<div class="alarm-card-head"><strong>${escapeHtml(alarm.event_type)}</strong><span class="${levelClass(alarm.event_level)}">${escapeHtml(alarm.event_level)}</span></div><p>${escapeHtml(alarm.message)}</p><small>${formatTime(alarm.created_at)} · ${escapeHtml(alarm.location || "未标注位置")}</small>${snapshotUrl ? `<a href="${encodeURI(snapshotUrl)}" target="_blank" rel="noopener">查看截图</a>` : ""}`;
    feed.prepend(item);
}

function setConnectionState(state) {
    const connected = state === "connected";
    const disconnected = state === "disconnected";
    const label = connected ? "实时连接正常" : disconnected ? "实时连接已断开" : "正在连接";
    const badge = document.getElementById("globalConnectionState");
    const side = document.getElementById("sidebarConnection");
    const dot = document.getElementById("sidebarConnectionDot");
    const banner = document.getElementById("connectionBanner");
    if (badge) { badge.textContent = label; badge.className = `status-badge ${connected ? "normal" : disconnected ? "high" : "pending"}`; }
    if (side) side.textContent = label;
    if (dot) dot.className = `connection-dot ${connected ? "connected" : disconnected ? "disconnected" : ""}`;
    if (banner) banner.classList.toggle("hidden", !disconnected);
}

function connectAlarmSocket(onAlarm) {
    if (onAlarm) consoleState.alarmListeners.add(onAlarm);
    if (consoleState.socket && [WebSocket.OPEN, WebSocket.CONNECTING].includes(consoleState.socket.readyState)) return consoleState.socket;
    setConnectionState("connecting");
    const socket = new WebSocket(window.CampusAPI.websocketUrl());
    consoleState.socket = socket;
    socket.onopen = () => setConnectionState("connected");
    socket.onmessage = event => {
        try {
            const alarm = JSON.parse(event.data);
            consoleState.latestAlarm = alarm;
            addAlarmCard(alarm);
            consoleState.alarmListeners.forEach(listener => {
                try { listener(alarm); } catch (error) { console.warn("Alarm listener failed", error); }
            });
            refreshGlobalSummary().catch(() => {});
            if (Date.now() >= consoleState.mutedUntil) playAlarmCue();
        } catch (error) {
            console.warn("Invalid alarm message", error);
        }
    };
    socket.onclose = event => {
        consoleState.socket = null;
        setConnectionState("disconnected");
        if (event.code !== 1008) {
            clearTimeout(consoleState.reconnectTimer);
            consoleState.reconnectTimer = setTimeout(() => connectAlarmSocket(), 2500);
        }
    };
    socket.onerror = () => socket.close();
    return socket;
}

function playAlarmCue() {
    try {
        const context = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = context.createOscillator();
        const gain = context.createGain();
        oscillator.frequency.value = 740;
        gain.gain.setValueAtTime(.05, context.currentTime);
        gain.gain.exponentialRampToValueAtTime(.001, context.currentTime + .16);
        oscillator.connect(gain).connect(context.destination);
        oscillator.start();
        oscillator.stop(context.currentTime + .16);
    } catch (_) { /* Browser audio may require prior user interaction. */ }
}

function muteAlarms(seconds = 30) {
    consoleState.mutedUntil = Date.now() + seconds * 1000;
    sessionStorage.setItem("alarmMutedUntil", String(consoleState.mutedUntil));
    showToast(`浏览器报警声音已静音 ${seconds} 秒`);
}

async function refreshGlobalSummary() {
    const [health, stats] = await Promise.all([requestJson("/api/health"), requestJson("/api/dashboard/stats").catch(() => null)]);
    const status = health.status || {};
    const running = Boolean(status.running);
    const system = document.getElementById("globalSystemState");
    if (system) { system.textContent = running ? "系统运行中" : "系统已停止"; system.className = `status-badge ${running ? "info" : "muted"}`; }
    if (stats) {
        const unread = (stats.latest_alarms || []).filter(item => item.status !== "handled").length || stats.today_alarm_count || 0;
        ["globalAlarmCount", "navAlarmCount"].forEach(id => { const el = document.getElementById(id); if (el) el.textContent = unread; });
        const device = document.getElementById("navDeviceCount");
        if (device) device.textContent = stats.offline_device_count || 0;
        const highest = document.getElementById("globalHighestRisk");
        if (highest) highest.textContent = stats.high_alarm_count ? `高危事件 ${stats.high_alarm_count}` : "当前无高危";
    }
    return { health, stats };
}

async function startDetection() {
    const result = await requestJson("/api/start", { method: "POST" });
    showToast("视频分析已启动");
    await refreshGlobalSummary().catch(() => {});
    return result;
}

async function stopDetection() {
    if (!window.confirm("停止后将暂停视频采集和检测。确认停止分析？")) return null;
    const result = await requestJson("/api/stop", { method: "POST" });
    showToast("视频分析已停止");
    await refreshGlobalSummary().catch(() => {});
    return result;
}

function bindControlButtons() {
    document.querySelectorAll("#startBtn, #globalStartBtn").forEach(button => button.addEventListener("click", () => startDetection().catch(error => showToast(error.message, "error"))));
    document.querySelectorAll("#stopBtn, #globalStopBtn").forEach(button => button.addEventListener("click", () => stopDetection().catch(error => showToast(error.message, "error"))));
}

function bindDemoButtons() {
    const result = document.getElementById("demoActionResult");
    const runAction = async (button, url, successText) => {
        button.disabled = true;
        try { const data = await requestJson(url, { method: "POST" }); if (result) result.textContent = successText(data); showToast(data.message || "操作完成"); }
        catch (error) { showToast(error.message, "error"); }
        finally { button.disabled = false; }
    };
    const initBtn = document.getElementById("initDemoBtn");
    initBtn?.addEventListener("click", () => runAction(initBtn, "/api/demo/init", data => `${data.message}：${JSON.stringify(data.data)}`));
    const runBtn = document.getElementById("runDemoBtn");
    runBtn?.addEventListener("click", () => runAction(runBtn, "/api/demo/run", data => `${data.message}：${data.data.triggered.join("、")}`));
    document.querySelectorAll("[data-demo-trigger]").forEach(button => button.addEventListener("click", () => runAction(button, `/api/demo/trigger/${button.dataset.demoTrigger}`, data => `已触发：${data.data.event_type}`)));
}

async function refreshHealth() {
    const data = await requestJson("/api/health");
    const status = data.status || {};
    const text = document.getElementById("statusText");
    const dot = document.getElementById("statusDot");
    if (text) text.textContent = status.running ? "检测运行中" : "检测未启动";
    if (dot) dot.classList.toggle("on", Boolean(status.running));
    const list = document.getElementById("configList");
    if (list) list.innerHTML = Object.entries(status.config || {}).map(([key, value]) => `<div><span>${escapeHtml(key)}</span><strong>${escapeHtml(value)}</strong></div>`).join("");
    return data;
}

async function loadAlarms() {
    const alarms = await requestJson("/api/alarms");
    const body = document.getElementById("alarmTableBody");
    if (!body) return alarms;
    body.innerHTML = alarms.length ? alarms.map(alarm => `<tr><td>${formatTime(alarm.created_at)}</td><td><code>${escapeHtml(alarm.event_type)}</code></td><td><span class="${levelClass(alarm.event_level)}">${escapeHtml(alarm.event_level)}</span></td><td>${escapeHtml(alarm.location || "—")}</td><td>${escapeHtml(alarm.message)}</td><td>${alarm.snapshot_path ? `<a href="${encodeURI(window.CampusAPI.assetUrl(alarm.snapshot_path))}" target="_blank" rel="noopener">查看</a>` : "—"}</td><td>${escapeHtml(alarm.status)}</td></tr>`).join("") : `<tr><td colspan="7" class="empty-cell">暂无告警记录</td></tr>`;
    return alarms;
}

function initHomePage() {
    bindDemoButtons();
    refreshHealth().catch(() => {});
    setInterval(() => refreshHealth().catch(() => {}), 3000);
}

function initMonitorPage() { /* Kept for legacy callers; monitor.js owns page behavior. */ }
function initAlarmsPage() { loadAlarms().catch(error => showToast(error.message, "error")); }

async function initUsersPage() {
    async function load() {
        const users = await requestJson("/api/users");
        document.getElementById("usersBody").innerHTML = users.map(user => `<tr><td>${user.id}</td><td>${escapeHtml(user.username)}</td><td>${escapeHtml(user.role)}</td><td>${escapeHtml(user.display_name || "")}</td><td>${user.is_active}</td></tr>`).join("");
    }
    document.getElementById("userForm")?.addEventListener("submit", async event => {
        event.preventDefault();
        try { await requestJson("/api/users", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(formJson(event.target)) }); event.target.reset(); await load(); }
        catch (error) { showToast(error.message, "error"); }
    });
    await load();
}

function initAppShell() {
    const page = document.body.dataset.page;
    document.querySelector(`[data-nav="${page}"]`)?.classList.add("active");
    document.getElementById("menuToggle")?.addEventListener("click", () => document.getElementById("sidebar")?.classList.toggle("open"));
    document.getElementById("globalMuteBtn")?.addEventListener("click", () => muteAlarms(30));
    document.getElementById("globalFullscreenBtn")?.addEventListener("click", () => document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen());
    const clock = document.getElementById("globalClock");
    const tick = () => { if (clock) clock.textContent = formatTime(new Date()); };
    tick();
    setInterval(tick, 1000);
    bindControlButtons();
    refreshGlobalSummary().catch(() => setConnectionState("disconnected"));
    connectAlarmSocket();
}

document.addEventListener("DOMContentLoaded", initAppShell);
