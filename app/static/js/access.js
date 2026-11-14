let persons = [];
let devices = [];

function setupTabs() {
    document.querySelectorAll(".tab").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
            document.querySelectorAll(".tab-panel").forEach(p => p.classList.add("hidden"));
            btn.classList.add("active");
            document.getElementById(`tab-${btn.dataset.tab}`).classList.remove("hidden");
        });
    });
}

async function loadAccessData() {
    persons = await requestJson("/api/persons");
    devices = await requestJson("/api/access/devices");
    const records = await requestJson("/api/access/records");
    const visitors = await requestJson("/api/visitors");
    document.getElementById("personsBody").innerHTML = persons.map(p => `<tr><td>${p.id}</td><td>${p.name}</td><td>${p.role}</td><td>${p.department || ""}</td><td><span class="${statusClass(p.status)}">${p.status}</span></td></tr>`).join("");
    document.getElementById("devicesBody").innerHTML = devices.map(d => `<tr><td>${d.id}</td><td>${d.name}</td><td>${d.location}</td><td>${d.device_type}</td><td><span class="${statusClass(d.status)}">${d.status}</span></td></tr>`).join("");
    document.getElementById("simulatePerson").innerHTML = persons.map(p => `<option value="${p.id}">${p.name} (${p.status})</option>`).join("");
    document.getElementById("simulateDevice").innerHTML = devices.map(d => `<option value="${d.id}">${d.name}</option>`).join("");
    renderRecords(records);
    renderVisitors(visitors);
}

function renderRecords(records) {
    document.getElementById("recordsBody").innerHTML = records.map(r => `<tr><td>${formatTime(r.created_at)}</td><td>${r.person_name || "访客"}</td><td>${r.device_name || ""}</td><td>${r.access_type}</td><td>${r.auth_method}</td><td><span class="${statusClass(r.result)}">${r.result}</span></td><td>${r.message}</td></tr>`).join("");
}

function renderVisitors(visitors) {
    document.getElementById("visitorsBody").innerHTML = visitors.map(v => `<tr><td>${v.id}</td><td>${v.visitor_name}</td><td>${v.phone || ""}</td><td>${v.host_name || ""}</td><td>${v.reason || ""}</td><td><span class="${statusClass(v.status)}">${v.status}</span></td><td><button class="btn compact" onclick="visitorAction(${v.id}, 'approve')">通过</button><button class="btn compact danger" onclick="visitorAction(${v.id}, 'reject')">拒绝</button><button class="btn compact" onclick="visitorEntry(${v.id})">模拟入校</button></td></tr>`).join("");
}

async function visitorAction(id, action) {
    await requestJson(`/api/visitors/${id}/${action}`, { method: "POST" });
    await loadAccessData();
}

async function visitorEntry(id) {
    await requestJson(`/api/visitors/${id}/simulate-entry`, { method: "POST" });
    await loadAccessData();
}

document.addEventListener("DOMContentLoaded", () => {
    setupTabs();
    loadAccessData().catch(alert);
    connectAlarmSocket();
    document.getElementById("personForm").addEventListener("submit", async e => {
        e.preventDefault();
        await requestJson("/api/persons", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(formJson(e.target)) });
        e.target.reset();
        await loadAccessData();
    });
    document.getElementById("simulateForm").addEventListener("submit", async e => e.preventDefault());
    document.querySelectorAll("#simulateForm button").forEach(btn => btn.addEventListener("click", async e => {
        e.preventDefault();
        const data = formJson(document.getElementById("simulateForm"));
        data.access_type = btn.dataset.type;
        const res = await requestJson("/api/access/simulate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
        document.getElementById("simulateResult").textContent = `结果：${res.result}，${res.message}`;
        await loadAccessData();
    }));
    document.getElementById("recordFilter").addEventListener("submit", async e => {
        e.preventDefault();
        const data = formJson(e.target);
        const params = new URLSearchParams(Object.entries(data).filter(([, v]) => v));
        renderRecords(await requestJson(`/api/access/records?${params}`));
    });
    document.getElementById("visitorForm").addEventListener("submit", async e => {
        e.preventDefault();
        await requestJson("/api/visitors", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(formJson(e.target)) });
        e.target.reset();
        await loadAccessData();
    });
});
