const API_BASE = window.REFERRAL_API_BASE || "";
const TOKEN_STORAGE_KEY = "trainer_token";
let trainerId = "";
let trainerName = "";
let trainerToken = localStorage.getItem(TOKEN_STORAGE_KEY) || "";
let currentClientId = null;
let cachedClients = [];
let dateBase = null;

function qs(id){
  return document.getElementById(id);
}

function api(path, options = {}){
  const headers = { "Content-Type": "application/json" };
  if (trainerToken) {
    headers["X-Trainer-Token"] = trainerToken;
  }
  return fetch(`${API_BASE}${path}`, {
    headers,
    ...options,
  }).then(async (res) => {
    if (!res.ok) {
      const text = await res.text();
      if (res.status === 401) {
        trainerToken = "";
        localStorage.removeItem(TOKEN_STORAGE_KEY);
        setLoginOverlayVisible(true);
        setLoginStatus("Сессия истекла. Войдите заново.", true);
      }
      throw new Error(text || `HTTP ${res.status}`);
    }
    return res.json();
  });
}

function formatDate(ts){
  if (!ts) return "—";
  const d = new Date(ts * 1000);
  return d.toLocaleDateString("ru-RU");
}

function todayISO(){
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function setStatus(text){
  const el = qs("saveStatus");
  el.textContent = text;
  el.classList.remove("is-ok", "is-error");
}

function setStatusState(text, state){
  const el = qs("saveStatus");
  el.textContent = text;
  el.classList.remove("is-ok", "is-error");
  if (state === "ok") el.classList.add("is-ok");
  if (state === "error") el.classList.add("is-error");
}

function setButtonState(btn, state){
  if (!btn) return;
  btn.classList.remove("is-loading", "is-saved");
  if (state === "loading") btn.classList.add("is-loading");
  if (state === "saved") btn.classList.add("is-saved");
}

function setLoginStatus(text, isError = false){
  const el = qs("loginStatus");
  el.textContent = text;
  el.style.color = isError ? "var(--danger)" : "var(--muted)";
}

function setLoginOverlayVisible(visible){
  const overlay = qs("loginOverlay");
  if (!overlay) return;
  overlay.classList.toggle("hidden", !visible);
}

function setTrainerHeader(){
  qs("trainerIdBadge").textContent = trainerId ? `ID: ${trainerId}` : "ID: —";
  qs("trainerNameTitle").textContent = trainerName || "Тренер";
}

function clearDashboard(){
  trainerId = "";
  trainerName = "";
  currentClientId = null;
  cachedClients = [];
  qs("clientsList").innerHTML = "";
  qs("promoList").textContent = "—";
  qs("clientName").textContent = "Выбери пользователя слева";
  qs("clientMeta").textContent = "—";
  qs("paidCount").textContent = "—";
  qs("paidTotal").textContent = "—";
  qs("daysLeft").textContent = "—";
  qs("lastPaid").textContent = "—";
  qs("workoutCount").textContent = "—";
  qs("workoutDays").textContent = "—";
  qs("mealsPlan").value = "";
  qs("workoutsPlan").value = "";
  setTrainerHeader();
}

function renderClients(clients){
  cachedClients = clients;
  const list = qs("clientsList");
  list.innerHTML = "";
  if (!clients.length) {
    list.innerHTML = `<div class="client-item">Пользователей пока нет</div>`;
    return;
  }
  clients.forEach((client) => {
    const item = document.createElement("div");
    item.className = "client-item";
    item.dataset.userId = client.user_id;
    if (String(client.user_id) === String(currentClientId)) {
      item.classList.add("active");
    }
    item.innerHTML = `
      <div class="client-id">ID ${client.user_id}</div>
      <div class="client-meta">Промокод: ${client.promo_code || "—"}</div>
    `;
    item.addEventListener("click", () => selectClient(client.user_id));
    list.appendChild(item);
  });
}

async function loadTrainer(){
  if (!trainerId) return;
  try {
    const data = await api(`/admin/referrals/trainers/${encodeURIComponent(trainerId)}/clients?days=90`);
    const clients = data.clients || [];
    renderClients(clients);
    await loadPricePromos();
    if (clients.length) {
      selectClient(clients[0].user_id);
    }
  } catch (e) {
    console.error(e);
    alert("Не удалось загрузить клиентов тренера");
  }
}

async function selectClient(userId){
  currentClientId = userId;
  renderClients(cachedClients);
  await loadClientSummary(userId);
  await loadPlans();
  Array.from(qs("clientsList").children).forEach((item) => {
    if (item.dataset.userId === String(userId)) {
      item.classList.add("active");
    } else {
      item.classList.remove("active");
    }
  });
}

async function loadClientSummary(userId){
  const summary = await api(`/admin/referrals/trainers/${encodeURIComponent(trainerId)}/clients/${encodeURIComponent(userId)}/summary?days=90`);
  qs("clientName").textContent = `ID ${summary.user_id}`;
  qs("clientMeta").textContent = `Промокод: ${summary.promo_code || "—"}`;
  qs("paidCount").textContent = summary.paid?.paid_count ?? "0";
  qs("paidTotal").textContent = `${Math.round(summary.paid?.paid_total_rub || 0)} ₽`;
  qs("daysLeft").textContent = summary.days_left ?? "0";
  qs("lastPaid").textContent = summary.paid?.last_paid_at ? `${formatDate(summary.paid.last_paid_at)}` : "—";
  qs("workoutCount").textContent = summary.workout_count ?? "0";
  const days = (summary.workout_days || []).slice(0, 14);
  qs("workoutDays").innerHTML = days.length
    ? days.map((d) => `<span class="activity-day">${d}</span>`).join("")
    : "Нет тренировок";
}

async function loadPricePromos(){
  const list = qs("promoList");
  list.textContent = "Загрузка...";
  try {
    const data = await api(`/admin/referrals/trainers/${encodeURIComponent(trainerId)}/price-promos`);
    const codes = data.codes || [];
    if (!codes.length) {
      list.textContent = "Промокоды не найдены";
      return;
    }
    list.innerHTML = codes.map((item) => {
      const price = Math.round(item.amount_rub || 0);
      const used = item.used_by_user_id ? " (использован)" : "";
      return `
        <div class="promo-chip">
          <span class="promo-code">${item.code}${used}</span>
          <span class="promo-price">${price} ₽</span>
          <button type="button" data-copy="${item.code}">Копировать</button>
        </div>
      `;
    }).join("");
    list.querySelectorAll("[data-copy]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const code = btn.getAttribute("data-copy");
        if (!code) return;
        await navigator.clipboard.writeText(code);
        btn.textContent = "Скопировано";
        setTimeout(() => { btn.textContent = "Копировать"; }, 1000);
      });
    });
  } catch (e) {
    console.error(e);
    list.textContent = "Не удалось загрузить промокоды";
  }
}

function formatDateLabel(date){
  const day = date.getDate();
  const weekday = date.toLocaleDateString("ru-RU", { weekday: "short" });
  return { day, weekday };
}

function renderDateStrip(){
  const track = qs("dateTrack");
  track.innerHTML = "";
  const base = dateBase || new Date();
  for (let i = 0; i < 7; i += 1){
    const date = new Date(base);
    date.setDate(base.getDate() + i);
    const iso = date.toISOString().slice(0, 10);
    const { day, weekday } = formatDateLabel(date);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "date-pill";
    if (qs("planDate").value === iso) btn.classList.add("active");
    btn.innerHTML = `<span>${weekday}</span><strong>${day}</strong>`;
    btn.addEventListener("click", () => {
      qs("planDate").value = iso;
      renderDateStrip();
      loadPlans();
    });
    track.appendChild(btn);
  }
}

async function loadPlan(kind){
  if (!currentClientId) return;
  const date = qs("planDate").value;
  const data = await api(`/admin/referrals/trainers/${encodeURIComponent(trainerId)}/clients/${encodeURIComponent(currentClientId)}/plan?date=${encodeURIComponent(date)}&kind=${encodeURIComponent(kind)}`);
  return data.text || "";
}

async function loadPlans(){
  try {
    setStatus("Загрузка...");
    const meals = await loadPlan("meals");
    const plan = await loadPlan("plan");
    qs("mealsPlan").value = meals;
    qs("workoutsPlan").value = plan;
    setStatusState("Планы загружены", "ok");
  } catch (e) {
    console.error(e);
    setStatusState("Ошибка загрузки плана", "error");
  }
}

async function savePlan(kind, text){
  if (!currentClientId) return;
  const date = qs("planDate").value;
  await api(`/admin/referrals/trainers/${encodeURIComponent(trainerId)}/clients/${encodeURIComponent(currentClientId)}/plan`, {
    method: "POST",
    body: JSON.stringify({ date, kind, text })
  });
}

qs("planDate").value = todayISO();
dateBase = new Date(qs("planDate").value);
renderDateStrip();

qs("planDate").addEventListener("change", () => {
  dateBase = new Date(qs("planDate").value);
  renderDateStrip();
  loadPlans();
});

qs("saveMealsBtn").addEventListener("click", async () => {
  const btn = qs("saveMealsBtn");
  try {
    setButtonState(btn, "loading");
    await savePlan("meals", qs("mealsPlan").value);
    setButtonState(btn, "saved");
    setStatusState("Питание сохранено", "ok");
    setTimeout(() => setButtonState(btn, ""), 1200);
  } catch (e) {
    console.error(e);
    setButtonState(btn, "");
    setStatusState("Ошибка сохранения питания", "error");
  }
});

qs("saveWorkoutsBtn").addEventListener("click", async () => {
  const btn = qs("saveWorkoutsBtn");
  try {
    setButtonState(btn, "loading");
    await savePlan("plan", qs("workoutsPlan").value);
    setButtonState(btn, "saved");
    setStatusState("План тренировок сохранен", "ok");
    setTimeout(() => setButtonState(btn, ""), 1200);
  } catch (e) {
    console.error(e);
    setButtonState(btn, "");
    setStatusState("Ошибка сохранения тренировок", "error");
  }
});

const params = new URLSearchParams(window.location.search);
const fromQuery = (params.get("trainer_id") || "").trim();

async function restoreSession(){
  if (!trainerToken) {
    setLoginOverlayVisible(true);
    return;
  }
  try {
    const session = await api("/admin/referrals/trainer/session");
    trainerId = session.trainer_id;
    trainerName = session.name || "";
    setTrainerHeader();
    setLoginOverlayVisible(false);
    await loadTrainer();
  } catch (e) {
    console.error(e);
    trainerToken = "";
    localStorage.removeItem(TOKEN_STORAGE_KEY);
    setLoginOverlayVisible(true);
  }
}

async function handleLogin(){
  const login = qs("loginInput").value.trim();
  const password = qs("passwordInput").value.trim();
  if (!login || !password) {
    setLoginStatus("Введите логин и пароль", true);
    return;
  }
  try {
    setLoginStatus("Входим...");
    const res = await api("/admin/referrals/trainer/login", {
      method: "POST",
      body: JSON.stringify({ login, password }),
    });
    trainerToken = res.token || "";
    if (trainerToken) {
      localStorage.setItem(TOKEN_STORAGE_KEY, trainerToken);
    }
    trainerId = res.trainer_id;
    trainerName = res.name || "";
    setTrainerHeader();
    setLoginOverlayVisible(false);
    qs("passwordInput").value = "";
    await loadTrainer();
  } catch (e) {
    console.error(e);
    setLoginStatus("Ошибка входа. Проверь логин и пароль.", true);
  }
}

qs("loginBtn").addEventListener("click", handleLogin);
qs("passwordInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter") handleLogin();
});
qs("loginInput").addEventListener("keydown", (e) => {
  if (e.key === "Enter") handleLogin();
});
qs("logoutBtn").addEventListener("click", () => {
  trainerToken = "";
  localStorage.removeItem(TOKEN_STORAGE_KEY);
  clearDashboard();
  setLoginStatus("Введите логин и пароль", false);
  setLoginOverlayVisible(true);
});

if (fromQuery && !trainerToken) {
  trainerId = fromQuery;
  trainerName = "";
  setTrainerHeader();
}

setTrainerHeader();
restoreSession();
