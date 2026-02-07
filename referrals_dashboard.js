const API_BASE = window.REFERRAL_API_BASE || "";
let currentDays = 7;
let cachedTrainers = [];
let activePopoverId = null;

function qs(id) {
  return document.getElementById(id);
}

async function api(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

function showToast(text = "Скопировано") {
  const toast = qs("toast");
  toast.textContent = text;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 1400);
}

function formatRub(value) {
  return `${Math.round(value || 0)} ₽`;
}

function renderSummary(trainers) {
  const totalClients = trainers.reduce((sum, t) => sum + (t.paid_clients || 0), 0);
  const totalPayout = trainers.reduce((sum, t) => sum + (t.payout_rub || 0), 0);
  const summary = qs("summaryStats");
  summary.innerHTML = `
    <span class="kpi-chip">Всего оплат: ${totalClients}</span>
    <span class="kpi-chip">Выплаты: ${totalPayout.toFixed(0)} ₽</span>
  `;
}

function normalizeQuery(value) {
  return (value || "").toLowerCase();
}

function buildPromoMap(trainer) {
  const promoList = (trainer.promos && trainer.promos.length) ? trainer.promos : [];
  const pricePromosRaw = (trainer.price_promos && trainer.price_promos.length) ? trainer.price_promos : [];
  const pricePromos = pricePromosRaw;
  const priceCodes = new Set(pricePromos.map(item => item.code));
  const generalPromos = promoList.filter(code => !priceCodes.has(code));
  return { promoList, pricePromos, generalPromos };
}

function renderEmptyState() {
  qs("trainersTable").innerHTML = `<div class="hint">Тренеров пока нет — создайте первого.</div>`;
}

function renderTrainers(trainers) {
  const table = qs("trainersTable");
  table.innerHTML = "";
  if (!trainers.length) {
    renderEmptyState();
    renderSummary([]);
    return;
  }
  renderSummary(trainers);
  const head = document.createElement("div");
  head.className = "table-head";
  head.innerHTML = `
    <div>Тренер</div>
    <div>Логин</div>
    <div>Пароль</div>
    <div>Клиенты</div>
    <div>Оплаты</div>
    <div>К выплате</div>
    <div>Промокоды</div>
    <div>Действия</div>
  `;
  table.appendChild(head);

  trainers.forEach((t) => {
    const { promoList, pricePromos, generalPromos } = buildPromoMap(t);
    const row = document.createElement("div");
    row.className = "table-row";
    row.dataset.trainerId = t.trainer_id;
    row.innerHTML = `
      <div class="table-cell">
        <strong>${t.name}</strong>
        <span class="table-meta">ID: ${t.trainer_id}</span>
      </div>
      <div class="table-cell">
        <span>${t.login || "—"}</span>
        <button class="link-btn" data-copy-login="${t.trainer_id}">Копировать</button>
      </div>
      <div class="table-cell">
        <span>${t.password_plain || "—"}</span>
        <button class="link-btn" data-copy-password="${t.trainer_id}">Копировать</button>
      </div>
      <div class="table-cell">
        <span>${t.bound_clients || 0}</span>
        <button class="link-btn" data-clients="${t.trainer_id}">Показать список</button>
      </div>
      <div class="table-cell">
        <span>${t.paid_clients || 0}</span>
        <span class="table-meta">за ${currentDays} дн.</span>
      </div>
      <div class="table-cell">
        <span class="badge">${formatRub(t.payout_rub)}</span>
      </div>
      <div class="table-cell" style="position:relative;">
        <button class="link-btn" data-promos="${t.trainer_id}">Открыть промокоды</button>
        <div class="popover" id="pop-${t.trainer_id}">
          <h4>Ценовые промокоды</h4>
          ${pricePromos.length ? pricePromos.map(item => `
            <div class="code-row"><span>${Math.round(item.amount_rub)} ₽</span><strong>${item.code}</strong></div>
          `).join("") : `<div class="code-row"><span>—</span><span>Нет</span></div>`}
          <h4>Общие промокоды</h4>
          ${generalPromos.length ? generalPromos.map(code => `
            <div class="code-row"><span>Код</span><strong>${code}</strong></div>
          `).join("") : `<div class="code-row"><span>—</span><span>Нет</span></div>`}
        </div>
      </div>
      <div class="actions">
        <button data-reset="${t.trainer_id}" title="Сбросить пароль">Сбросить пароль</button>
        <button data-delete="${t.trainer_id}" title="Удалить">Удалить</button>
      </div>
    `;
    table.appendChild(row);

    const list = document.createElement("div");
    list.className = "table-row";
    list.dataset.clientsList = t.trainer_id;
    list.style.display = "none";
    list.innerHTML = `<div class="table-cell" style="grid-column:1/-1;" id="list-${t.trainer_id}"></div>`;
    table.appendChild(list);
  });
}

async function loadTrainers() {
  qs("tableStatus").textContent = "Загрузка...";
  const data = await api(`/admin/referrals/trainers?days=${currentDays}`);
  cachedTrainers = data.trainers || [];
  qs("tableStatus").textContent = `${cachedTrainers.length} тренеров`;
  applyFilter();
}

function applyFilter() {
  const query = normalizeQuery(qs("trainerSearch").value);
  if (!query) {
    renderTrainers(cachedTrainers);
    return;
  }
  const filtered = cachedTrainers.filter((t) => {
    const name = normalizeQuery(t.name);
    const login = normalizeQuery(t.login);
    const promos = normalizeQuery((t.promos || []).join(","));
    const pricePromos = normalizeQuery((t.price_promos || []).map(p => p.code).join(","));
    return name.includes(query) || login.includes(query) || promos.includes(query) || pricePromos.includes(query) || normalizeQuery(t.trainer_id).includes(query);
  });
  renderTrainers(filtered);
}

function generateCode() {
  return String(Math.floor(1000 + Math.random() * 9000));
}

function fillPromoInput(inputId) {
  const input = qs(inputId);
  if (!input) return;
  input.value = generateCode();
}

async function addTrainer() {
  const nameEl = qs("trainerName");
  const buttonEl = qs("addTrainerBtn");
  const promoInputs = {
    1000: qs("promo1000"),
    2000: qs("promo2000"),
    3000: qs("promo3000"),
    4000: qs("promo4000"),
    5000: qs("promo5000"),
  };
  const name = nameEl.value.trim();
  const pricePromos = {};
  Object.entries(promoInputs).forEach(([amount, input]) => {
    const value = (input.value || "").replace(/\D/g, "").slice(0, 4);
    if (value) {
      pricePromos[amount] = value;
    }
    input.value = value;
  });
  if (!name) {
    showToast("Введите имя тренера");
    return;
  }
  try {
    buttonEl.disabled = true;
    buttonEl.textContent = "Добавляем...";
    const res = await api("/admin/referrals/trainers", {
      method: "POST",
      body: JSON.stringify({
        name,
        price_promos: Object.keys(pricePromos).length ? pricePromos : undefined,
      }),
    });
    nameEl.value = "";
    Object.values(promoInputs).forEach((input) => { input.value = ""; });
    await loadTrainers();
    let credentials = res.credentials || {};
    if (!credentials?.login || !credentials?.password) {
      try {
        const reset = await api(`/admin/referrals/trainers/${res.trainer?.trainer_id}/reset-password`, {
          method: "POST",
        });
        credentials = reset?.credentials || credentials;
      } catch (_) {
        // ignore reset errors; modal will show placeholders
      }
    }
    if (credentials?.login || credentials?.password) {
      const id = res.trainer?.trainer_id;
      const existing = cachedTrainers.find(t => t.trainer_id === id);
      if (existing) {
        if (credentials?.login) {
          existing.login = credentials.login;
        }
        if (credentials?.password) {
          existing.password_plain = credentials.password;
        }
        renderTrainers(cachedTrainers);
      }
    }
    openCredentialsModal(res.trainer, credentials);
  } catch (e) {
    let message = e?.message || "Ошибка добавления тренера";
    try {
      const parsed = JSON.parse(message);
      if (parsed?.detail) {
        message = parsed.detail;
      }
    } catch (_) {}
    showToast(message);
  } finally {
    buttonEl.disabled = false;
    buttonEl.textContent = "Добавить тренера";
  }
}

function openCredentialsModal(trainer, credentials) {
  const modal = qs("credentialsModal");
  qs("credentialsTitle").textContent = trainer?.name ? `Доступы: ${trainer.name}` : "Доступы тренера";
  const loginValue = credentials?.login || trainer?.login || "—";
  const passwordValue = credentials?.password || trainer?.password_plain || "";
  qs("credLogin").textContent = loginValue;
  qs("credPassword").textContent = passwordValue || "—";
  modal.classList.add("show");
  modal.dataset.login = loginValue === "—" ? "" : loginValue;
  modal.dataset.password = passwordValue;
}

function closeCredentialsModal() {
  const modal = qs("credentialsModal");
  modal.classList.remove("show");
  modal.dataset.login = "";
  modal.dataset.password = "";
  qs("credLogin").textContent = "—";
  qs("credPassword").textContent = "—";
}

async function resetPassword(trainerId) {
  const ok = confirm("Сбросить пароль тренера? Новый пароль будет показан один раз.");
  if (!ok) return;
  const res = await api(`/admin/referrals/trainers/${encodeURIComponent(trainerId)}/reset-password`, {
    method: "POST",
  });
  const trainer = cachedTrainers.find(t => t.trainer_id === trainerId);
  openCredentialsModal(trainer, res.credentials);
}

async function deleteTrainer(trainerId, name) {
  const ok = confirm(`Удалить тренера "${name}"? Все привязки и промокоды будут удалены.`);
  if (!ok) return;
  await api(`/admin/referrals/trainers/${encodeURIComponent(trainerId)}`, { method: "DELETE" });
  await loadTrainers();
}

qs("addTrainerBtn").addEventListener("click", addTrainer);
qs("trainerSearch").addEventListener("input", applyFilter);
qs("closeModalBtn").addEventListener("click", closeCredentialsModal);
qs("closeModalBtn2").addEventListener("click", closeCredentialsModal);

qs("credentialsModal").addEventListener("click", (e) => {
  if (e.target.id === "credentialsModal") {
    closeCredentialsModal();
  }
});

qs("credentialsModal").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-copy]");
  if (!btn) return;
  const modal = qs("credentialsModal");
  const login = modal.dataset.login || "";
  const password = modal.dataset.password || "";
  if (btn.dataset.copy === "login") {
    navigator.clipboard.writeText(login);
    showToast("Логин скопирован");
  }
  if (btn.dataset.copy === "password") {
    navigator.clipboard.writeText(password);
    showToast("Пароль скопирован");
  }
  if (btn.dataset.copy === "all") {
    navigator.clipboard.writeText(`Логин: ${login}\nПароль: ${password}`);
    showToast("Доступы скопированы");
  }
});

Object.values({
  promo1000: qs("promo1000"),
  promo2000: qs("promo2000"),
  promo3000: qs("promo3000"),
  promo4000: qs("promo4000"),
  promo5000: qs("promo5000"),
}).forEach((input) => {
  input.addEventListener("input", () => {
    input.value = (input.value || "").replace(/\D/g, "").slice(0, 4);
  });
});

qs("trainersTable").addEventListener("click", async (e) => {
  const deleteBtn = e.target.closest("[data-delete]");
  const resetBtn = e.target.closest("[data-reset]");
  const copyLoginBtn = e.target.closest("[data-copy-login]");
  const copyPasswordBtn = e.target.closest("[data-copy-password]");
  const clientsBtn = e.target.closest("[data-clients]");
  const promosBtn = e.target.closest("[data-promos]");
  const genBtn = e.target.closest("[data-gen]");
  const copyInputBtn = e.target.closest("[data-copy-input]");

  if (deleteBtn) {
    const row = deleteBtn.closest(".table-row");
    const name = row.querySelector("strong")?.textContent || "тренера";
    await deleteTrainer(deleteBtn.dataset.delete, name);
    return;
  }
  if (resetBtn) {
    await resetPassword(resetBtn.dataset.reset);
    return;
  }
  if (copyLoginBtn) {
    const trainer = cachedTrainers.find(t => t.trainer_id === copyLoginBtn.dataset.copyLogin);
    if (trainer?.login) {
      await navigator.clipboard.writeText(trainer.login);
      showToast("Логин скопирован");
    }
    return;
  }
  if (copyPasswordBtn) {
    const trainer = cachedTrainers.find(t => t.trainer_id === copyPasswordBtn.dataset.copyPassword);
    if (trainer?.password_plain) {
      await navigator.clipboard.writeText(trainer.password_plain);
      showToast("Пароль скопирован");
    }
    return;
  }
  if (clientsBtn) {
    const trainerId = clientsBtn.dataset.clients;
    const listRow = document.querySelector(`[data-clients-list="${trainerId}"]`);
    const listEl = document.querySelector(`#list-${trainerId}`);
    if (!listRow || !listEl) return;
    if (listRow.dataset.loaded !== "1") {
      const data = await api(`/admin/referrals/trainers/${encodeURIComponent(trainerId)}/clients?days=${currentDays}`);
      const items = data.clients || [];
      listEl.innerHTML = items.length
        ? items.map(c => `<div class="table-meta">ID: ${c.user_id} · ${c.promo_code}</div>`).join("")
        : `<div class="table-meta">Клиентов пока нет</div>`;
      listRow.dataset.loaded = "1";
    }
    const isHidden = listRow.style.display === "none";
    listRow.style.display = isHidden ? "grid" : "none";
    clientsBtn.textContent = isHidden ? "Скрыть список" : "Показать список";
    return;
  }
  if (promosBtn) {
    const trainerId = promosBtn.dataset.promos;
    const popover = qs(`pop-${trainerId}`);
    if (!popover) return;
    if (activePopoverId && activePopoverId !== trainerId) {
      const prev = qs(`pop-${activePopoverId}`);
      if (prev) prev.classList.remove("show");
    }
    popover.classList.toggle("show");
    activePopoverId = popover.classList.contains("show") ? trainerId : null;
    return;
  }
  if (genBtn) {
    fillPromoInput(genBtn.dataset.gen);
    return;
  }
  if (copyInputBtn) {
    const input = qs(copyInputBtn.dataset.copyInput);
    if (input?.value) {
      await navigator.clipboard.writeText(input.value);
      showToast("Промокод скопирован");
    }
  }
});

document.addEventListener("click", (e) => {
  if (!activePopoverId) return;
  const popover = qs(`pop-${activePopoverId}`);
  if (!popover) return;
  if (!popover.contains(e.target) && !e.target.closest(`[data-promos="${activePopoverId}"]`)) {
    popover.classList.remove("show");
    activePopoverId = null;
  }
});

document.querySelectorAll(".period-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    document.querySelectorAll(".period-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    currentDays = parseInt(btn.dataset.days, 10);
    await loadTrainers();
  });
});

loadTrainers().catch((e) => {
  console.error(e);
  qs("tableStatus").textContent = "Ошибка загрузки";
});

// Promo action buttons
["promo1000","promo2000","promo3000","promo4000","promo5000"].forEach((id) => {
  const genBtn = document.querySelector(`[data-gen="${id}"]`);
  const copyBtn = document.querySelector(`[data-copy-input="${id}"]`);
  genBtn?.addEventListener("click", () => fillPromoInput(id));
  copyBtn?.addEventListener("click", async () => {
    const input = qs(id);
    if (input?.value) {
      await navigator.clipboard.writeText(input.value);
      showToast("Промокод скопирован");
    }
  });
});
