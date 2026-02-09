(() => {
  const $ = (q) => document.querySelector(q);
  
  // АБСОЛЮТНОЕ УНИЧТОЖЕНИЕ БЛОКА БЫСТРЫХ ШАБЛОНОВ
  (function() {
    function kill() {
      const els = document.querySelectorAll('.quick-templates, #quickTemplates, [id*="quickTemplate"], [class*="quick-template"], [class*="template"]');
      els.forEach(el => {
        try { el.remove(); } catch(e) { if (el.parentNode) el.parentNode.removeChild(el); }
        el.style.cssText = 'display: none !important; visibility: hidden !important; opacity: 0 !important; height: 0 !important; width: 0 !important; position: absolute !important; left: -99999px !important; top: -99999px !important; pointer-events: none !important; z-index: -99999 !important;';
        Object.defineProperty(el.style, 'display', {value: 'none', writable: false, configurable: false});
      });
    }
    kill();
    if (document.body) {
      const obs = new MutationObserver(kill);
      obs.observe(document.body, {childList: true, subtree: true, attributes: true});
    }
    document.addEventListener('DOMContentLoaded', kill);
    window.addEventListener('load', kill);
    // setInterval удален - используется только MutationObserver для оптимизации производительности
  })();
  const $$ = (q) => document.querySelectorAll(q);

  const API_ROOT = (() => {
    try {
      const params = new URLSearchParams(window.location.search);
      const fromQuery = (params.get("api_base") || params.get("apiBase") || "").trim();
      const fromStorage = (localStorage.getItem("api_base") || "").trim();
      const fromWindow = (window.API_BASE || "").toString().trim();
      const host = (window.location && window.location.hostname) ? window.location.hostname : "";
      if (host === "sport-helper-robot.online") {
        const forced = "https://sport-helper-robot.online";
        try { localStorage.setItem("api_base", forced); } catch (e) {}
        return forced;
      }
      const value = fromWindow || fromQuery || fromStorage;
      if (value) {
        return value.replace(/\/+$/, "");
      }
      return "";
    } catch (e) {
      return "";
    }
  })();

  function withApiBase(url) {
    if (!API_ROOT) return url;
    if (!url) return url;
    if (/^https?:\/\//i.test(url) || url.startsWith("//")) return url;
    const prefix = url.startsWith("/") ? "" : "/";
    return `${API_ROOT}${prefix}${url}`;
  }

  const OFFLINE_PREFIX = "offline_api_v1";
  const NOTIFY_OPTIONS = [
    { value: "3_per_day", label: "3 раза в день" },
    { value: "1_per_day", label: "1 раз в день" },
    { value: "1_per_week", label: "1 раз в неделю" },
    { value: "disabled", label: "Отключено" }
  ];

  function offlineKey(uid, name) {
    return `${OFFLINE_PREFIX}:${uid}:${name}`;
  }

  function readJson(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return fallback;
      const parsed = JSON.parse(raw);
      return parsed === null || parsed === undefined ? fallback : parsed;
    } catch (e) {
      return fallback;
    }
  }

  function writeJson(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch (e) {}
  }

  function apiPath(url) {
    try {
      const full = new URL(url, window.location.origin);
      return full.pathname;
    } catch (e) {
      return (url || "").split("?")[0];
    }
  }

  function offlineNotesKey(uid) {
    return offlineKey(uid, "notes");
  }

  function offlineGetNote(uid, d, kind) {
    const map = readJson(offlineNotesKey(uid), {});
    const key = `${d}|${kind}`;
    return { text: map[key] || "" };
  }

  function offlineSetNote(uid, d, kind, text) {
    const map = readJson(offlineNotesKey(uid), {});
    const key = `${d}|${kind}`;
    map[key] = text || "";
    writeJson(offlineNotesKey(uid), map);
    return { text: map[key] };
  }

  function offlineTodayKey(uid) {
    try {
      const p = mskParts(new Date());
      const d = iso(p.y, p.m, p.d);
      return offlineKey(uid, `workout_plan:${d}`);
    } catch (e) {
      return offlineKey(uid, "workout_plan:today");
    }
  }

  function offlineGetWorkoutPlan(uid) {
    return readJson(offlineTodayKey(uid), { exercises: [] });
  }

  function offlineSetWorkoutPlan(uid, plan) {
    writeJson(offlineTodayKey(uid), plan || { exercises: [] });
    return plan || { exercises: [] };
  }

  function offlineGetProfile(uid) {
    return readJson(offlineKey(uid, "profile"), {});
  }

  function offlineSetProfile(uid, data) {
    const current = readJson(offlineKey(uid, "profile"), {});
    const next = { ...current, ...(data || {}) };
    writeJson(offlineKey(uid, "profile"), next);
    return next;
  }

  function offlineGetReminders(uid) {
    return readJson(offlineKey(uid, "reminders"), { enabled: true });
  }

  function offlineSetReminders(uid, enabled) {
    const next = { enabled: !!enabled };
    writeJson(offlineKey(uid, "reminders"), next);
    return next;
  }

  function offlineGetNotifications(uid) {
    const stored = readJson(offlineKey(uid, "notifications"), {});
    const frequency = stored.frequency || "1_per_day";
    const isEnabled = frequency !== "disabled";
    const label = (NOTIFY_OPTIONS.find(o => o.value === frequency) || NOTIFY_OPTIONS[1]).label;
    return {
      frequency,
      frequency_label: label,
      is_enabled: isEnabled,
      options: NOTIFY_OPTIONS
    };
  }

  function offlineSetNotifications(uid, frequency) {
    const safe = NOTIFY_OPTIONS.some(o => o.value === frequency) ? frequency : "1_per_day";
    const next = { frequency: safe };
    writeJson(offlineKey(uid, "notifications"), next);
    return offlineGetNotifications(uid);
  }

  function offlineGetGoals(uid) {
    return readJson(offlineKey(uid, "goals"), { weekly_workouts: 3 });
  }

  function offlineSetGoals(uid, data) {
    const current = offlineGetGoals(uid);
    const next = { ...current, ...(data || {}) };
    writeJson(offlineKey(uid, "goals"), next);
    return next;
  }

  function offlineExport(uid) {
    return {
      notes: readJson(offlineNotesKey(uid), {}),
      profile: offlineGetProfile(uid),
      goals: offlineGetGoals(uid),
      reminders: offlineGetReminders(uid),
      notifications: offlineGetNotifications(uid)
    };
  }

  const API = "/api/notes";
  const STATS_API = "/api/stats";
  const NOTIFICATIONS_API = "/api/notifications/settings";
  const WORKOUT_PLAN_API = "/api/workout-plan/today";
  const MEASUREMENTS_KIND = "measurements";
  const MEASUREMENTS_HISTORY_LIMIT = 10;
  const TZ = "Europe/Moscow";
  const DOW = ["вс","пн","вт","ср","чт","пт","сб"];
  const MONTHS = ["январь","февраль","март","апрель","май","июнь","июль","август","сентябрь","октябрь","ноябрь","декабрь"];
  const MONTHS_GENITIVE = ["января","февраля","марта","апреля","мая","июня","июля","августа","сентября","октября","ноября","декабря"];
  const WEEKDAYS_SHORT = ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"];
  const MEASUREMENT_FIELDS = [
    { key: "waist_cm", id: "measureWaist", label: "Талия" },
    { key: "hips_cm", id: "measureHips", label: "Бедра" },
    { key: "chest_cm", id: "measureChest", label: "Грудь" },
    { key: "shoulders_cm", id: "measureShoulders", label: "Плечи" },
    { key: "biceps_cm", id: "measureBiceps", label: "Бицепс" },
    { key: "glutes_cm", id: "measureGlutes", label: "Ягодицы" }
  ];

  let calendarCurrentMonth = null;
  let calendarCurrentYear = null;

  function getDayWord(count) {
    const mod10 = count % 10;
    const mod100 = count % 100;
    
    if (mod100 >= 11 && mod100 <= 19) {
      return "дней";
    }
    if (mod10 === 1) {
      return "день";
    }
    if (mod10 >= 2 && mod10 <= 4) {
      return "дня";
    }
    return "дней";
  }

  function getWorkoutWord(count) {
    const mod10 = count % 10;
    const mod100 = count % 100;
    
    if (mod100 >= 11 && mod100 <= 19) {
      return "тренировок";
    }
    if (mod10 === 1) {
      return "тренировка";
    }
    if (mod10 >= 2 && mod10 <= 4) {
      return "тренировки";
    }
    return "тренировок";
  }

  function mskParts(date = new Date()){
    const fmt = new Intl.DateTimeFormat("ru-RU", {
      timeZone: TZ,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      weekday: "short",
    });
    const parts = fmt.formatToParts(date);
    const get = (t) => parts.find(p => p.type === t)?.value;
    const y = Number(get("year"));
    const m = Number(get("month"));
    const d = Number(get("day"));
    const wd = (get("weekday") || "").replace(".", "").toLowerCase();
    return {y,m,d,wd};
  }

  function iso(y,m,d){
    const mm = String(m).padStart(2,"0");
    const dd = String(d).padStart(2,"0");
    return `${y}-${mm}-${dd}`;
  }

  function parseISO(s){
    const [y,m,d] = s.split("-").map(Number);
    return {y,m,d};
  }

  function weekStartISO(dayISO){
    const {y,m,d} = parseISO(dayISO);
    const dt = new Date(Date.UTC(y, m-1, d, 12, 0, 0));
    const wd = new Intl.DateTimeFormat("ru-RU", { timeZone: TZ, weekday: "short"}).format(dt).replace(".","").toLowerCase();
    const idx = ["пн","вт","ср","чт","пт","сб","вс"].indexOf(wd);
    const diff = idx;
    dt.setUTCDate(dt.getUTCDate() - diff);
    const p = mskParts(dt);
    return iso(p.y,p.m,p.d);
  }

  function addDaysISO(dayISO, n){
    const {y,m,d} = parseISO(dayISO);
    const dt = new Date(Date.UTC(y, m-1, d, 12, 0, 0));
    dt.setUTCDate(dt.getUTCDate() + n);
    const p = mskParts(dt);
    return iso(p.y,p.m,p.d);
  }

  function getUserId(){
    const tg = window.Telegram?.WebApp;
    let uid = null;
    
    console.log("🔍 Поиск User ID...", {
      hasTelegram: !!window.Telegram,
      hasWebApp: !!tg,
      hasInitDataUnsafe: !!tg?.initDataUnsafe,
      hasUser: !!tg?.initDataUnsafe?.user,
      hasUserId: !!tg?.initDataUnsafe?.user?.id,
      hasInitData: !!tg?.initData
    });
    
    // Пробуем получить из Telegram WebApp
    if (tg?.initDataUnsafe?.user?.id) {
      uid = tg.initDataUnsafe.user.id;
      console.log("✅ User ID из initDataUnsafe:", uid);
    }
    
    // Если не получили, пробуем из initData (строка)
    if (!uid && tg?.initData) {
      try {
        console.log("🔍 Парсим initData строку...");
        const params = new URLSearchParams(tg.initData);
        const userStr = params.get('user');
        if (userStr) {
          const user = JSON.parse(userStr);
          uid = user.id;
          console.log("✅ User ID из initData строки:", uid);
        }
      } catch (e) {
        console.warn("⚠️ Не удалось распарсить initData:", e);
      }
    }
    
    // Если не получили, пробуем из versionData
    if (!uid && tg?.versionData) {
      try {
        const userStr = tg.versionData.user;
        if (userStr) {
          const user = typeof userStr === 'string' ? JSON.parse(userStr) : userStr;
          uid = user.id;
          console.log("✅ User ID из versionData:", uid);
        }
      } catch (e) {
        console.warn("⚠️ Не удалось получить из versionData:", e);
      }
    }
    
    // Если получили ID, сохраняем в localStorage
    if (uid) {
      const v = String(uid);
      localStorage.setItem("tracker_user_id", v);
      console.log("✅ User ID сохранен в localStorage:", v);
      return v;
    }
    
    // Пробуем из localStorage
    const stored = localStorage.getItem("tracker_user_id");
    if (stored) {
      console.log("✅ User ID из localStorage:", stored);
      return stored;
    }
    
    // Пробуем получить из URL параметров (резервный вариант)
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const userIdFromUrl = urlParams.get('user_id') || urlParams.get('userId') || urlParams.get('user');
      if (userIdFromUrl) {
        console.log("✅ User ID из URL параметров:", userIdFromUrl);
        localStorage.setItem("tracker_user_id", userIdFromUrl);
        return userIdFromUrl;
      }
    } catch (e) {
      console.warn("⚠️ Не удалось получить user_id из URL:", e);
    }
    
    console.warn("⚠️ User ID не найден ни в Telegram, ни в localStorage, ни в URL");
    console.log("🔍 Полная информация о Telegram WebApp:", {
      Telegram: window.Telegram,
      WebApp: tg,
      initDataUnsafe: tg?.initDataUnsafe,
      initDataUnsafeKeys: tg?.initDataUnsafe ? Object.keys(tg.initDataUnsafe) : [],
      initDataUnsafeFull: JSON.stringify(tg?.initDataUnsafe, null, 2),
      initData: tg?.initData ? "есть (строка)" : "нет",
      initDataLength: tg?.initData ? tg.initData.length : 0,
      url: window.location.href
    });
    
    // Пробуем получить из других мест в WebApp
    if (tg) {
      console.log("🔍 Проверяем другие свойства WebApp:", {
        platform: tg.platform,
        version: tg.version,
        colorScheme: tg.colorScheme,
        themeParams: tg.themeParams,
        startParam: tg.startParam,
        allKeys: Object.keys(tg)
      });
      
      // Пробуем получить из startParam (может быть передан user_id)
      if (tg.startParam && /^\d+$/.test(tg.startParam)) {
        console.log("✅ User ID из startParam:", tg.startParam);
        localStorage.setItem("tracker_user_id", tg.startParam);
        return tg.startParam;
      }
      
      // Пробуем из URL напрямую через window.location
      try {
        const urlMatch = window.location.href.match(/[?&]user[_-]?id=(\d+)/i);
        if (urlMatch && urlMatch[1]) {
          console.log("✅ User ID из URL:", urlMatch[1]);
          localStorage.setItem("tracker_user_id", urlMatch[1]);
          return urlMatch[1];
        }
      } catch (e) {
        console.warn("⚠️ Не удалось получить из URL:", e);
      }
    }
    
    // ВАЖНО: возвращаем "0" для демо-режима вместо пустой строки
    // Это позволит приложению работать даже без user_id
    console.log("ℹ️ Используем демо-режим (user_id: 0)");
    return "0";
  }

  async function apiGetNote(d, kind){
    const uid = getUserId() || "0";
    const url = withApiBase(`${API}?d=${encodeURIComponent(d)}&kind=${encodeURIComponent(kind)}`);
    try {
      const r = await fetch(url, {
        headers: { "X-User-Id": uid }
      });
      if (!r.ok) {
        const errorText = await r.text();
        console.error(`❌ GET ${url} failed: ${r.status}`, errorText);
        throw new Error(`GET ${r.status}: ${errorText}`);
      }
      return await r.json();
    } catch (e) {
      console.error(`❌ GET ${url} error:`, e);
      return offlineGetNote(uid, d, kind);
    }
  }

  async function apiPut(d, kind, text){
    const uid = getUserId() || "0";
    try {
      const r = await fetch(withApiBase(`${API}?d=${encodeURIComponent(d)}&kind=${encodeURIComponent(kind)}`), {
        method: "PUT",
        headers: { "X-User-Id": uid, "Content-Type":"application/json" },
        body: JSON.stringify({ text })
      });
      if (!r.ok) {
        const errorText = await r.text();
        console.error(`❌ PUT ${API} failed: ${r.status}`, errorText);
        throw new Error(`PUT ${r.status}: ${errorText}`);
      }
      return await r.json();
    } catch (e) {
      console.error(`❌ PUT ${API} error:`, e);
      return offlineSetNote(uid, d, kind, text);
    }
  }

  async function apiGetStats(days = 90, previousPeriod = false){
    const uid = getUserId() || "0";
    const url = withApiBase(`${STATS_API}?days=${days}${previousPeriod ? '&previous=true' : ''}`);
    try {
      const r = await fetch(withApiBase(url), {
        headers: { "X-User-Id": uid }
      });
      if (!r.ok) {
        const errorText = await r.text();
        console.error(`❌ GET ${url} failed: ${r.status}`, errorText);
        throw new Error(`Stats ${r.status}: ${errorText}`);
      }
      return await r.json();
    } catch (e) {
      console.error(`❌ GET ${url} error:`, e);
      return { chart_data: [], summary: {}, workouts: 0 };
    }
  }

  async function apiGet(url){
    let uid = getUserId();
    
    // Если ID не найден, пробуем подождать инициализации Telegram
    if (!uid) {
      const tg = window.Telegram?.WebApp;
      if (tg) {
        if (tg.ready) tg.ready();
        await new Promise(resolve => setTimeout(resolve, 200));
        uid = getUserId();
      }
    }
    
    // Если всё ещё нет ID, пробуем получить из URL
    if (!uid) {
      const urlParams = new URLSearchParams(window.location.search);
      const userIdFromUrl = urlParams.get('user_id') || urlParams.get('userId');
      if (userIdFromUrl) {
        uid = userIdFromUrl;
        localStorage.setItem("tracker_user_id", uid);
      }
    }
    
    // Если ID всё ещё не найден, используем "0" как fallback для демо-режима
    if (!uid) {
      console.warn("⚠️ User ID не найден, используем демо-режим (ID: 0)");
      uid = "0";
    }
    
    try {
      const fullUrl = withApiBase(url);
      const logUrl = fullUrl || url;
      const r = await fetch(fullUrl, {
        headers: { "X-User-Id": uid }
      });
      if (!r.ok) {
        const errorText = await r.text();
        // Не логируем ошибки для /api/goals, так как это опциональный эндпоинт
        if (!logUrl.includes("/api/goals")) {
          console.error(`❌ GET ${logUrl} failed: ${r.status}`, errorText);
        }
        throw new Error(`GET ${r.status}: ${errorText}`);
      }
      return await r.json();
    } catch (e) {
      // Не логируем ошибки для /api/goals, так как это опциональный эндпоинт
      if (!url.includes("/api/goals")) {
        console.error(`❌ GET ${url} error:`, e);
      }
      const path = apiPath(url);
      if (path === "/api/profile") return offlineGetProfile(uid);
      if (path === "/api/reminders/settings") return offlineGetReminders(uid);
      if (path === "/api/notifications/settings") return offlineGetNotifications(uid);
      if (path === "/api/export/data") return offlineExport(uid);
      if (path === "/api/goals") return offlineGetGoals(uid);
      throw e;
    }
  }

  async function apiPost(url, data){
    let uid = getUserId();
    
    // Если ID не найден, пробуем подождать инициализации Telegram
    if (!uid) {
      const tg = window.Telegram?.WebApp;
      if (tg) {
        if (tg.ready) tg.ready();
        await new Promise(resolve => setTimeout(resolve, 200));
        uid = getUserId();
      }
    }
    
    // Если ID всё ещё не найден, используем "0" как fallback
    if (!uid) {
      console.warn("⚠️ User ID не найден для POST, используем демо-режим (ID: 0)");
      uid = "0";
    }
    
    try {
      const fullUrl = withApiBase(url);
      const logUrl = fullUrl || url;
      const r = await fetch(fullUrl, {
        method: "POST",
        headers: { "X-User-Id": uid, "Content-Type": "application/json" },
        body: JSON.stringify(data)
      });
      if (!r.ok) {
        const errorText = await r.text();
        console.error(`❌ POST ${logUrl} failed: ${r.status}`, errorText);
        throw new Error(`POST ${r.status}: ${errorText}`);
      }
      return await r.json();
    } catch (e) {
      console.error(`❌ POST ${url} error:`, e);
      const path = apiPath(url);
      if (path === "/api/profile") return offlineSetProfile(uid, data);
      if (path === "/api/reminders/settings") return offlineSetReminders(uid, data?.enabled);
      if (path === "/api/notifications/settings") return offlineSetNotifications(uid, data?.frequency);
      if (path === "/api/goals") return offlineSetGoals(uid, data);
      throw e;
    }
  }

  const state = {
    kind: "workouts",
    day: null,
    weekStart: null,
    savingTimer: null,
    lastLoadedText: "",
    statsDays: 90,
    statsData: null,
    currentPage: "today",
    planKind: "workouts",  // Для страницы "План" - какой раздел выбран
    measurementsPrevValues: null,
    measurementsHistory: [],
    trainerInfo: null,
    trainerLocked: false
  };

  async function loadTrainerBinding() {
    const uid = getUserId() || "0";
    if (!uid || uid === "0") return;
    try {
      const r = await fetch(`/admin/referrals/user/${encodeURIComponent(uid)}/trainer`);
      if (!r.ok) return;
      const data = await r.json();
      if (data && data.trainer) {
        state.trainerInfo = data.trainer;
        state.trainerLocked = true;
        applyTrainerLock();
      }
    } catch (e) {
      console.warn("⚠️ Не удалось проверить привязку к тренеру:", e);
    }
  }

  function applyTrainerLock() {
    const noteEl = $("#notePlan");
    if (noteEl) {
      noteEl.setAttribute("contenteditable", "false");
      noteEl.setAttribute("data-locked", "1");
    }
    const hintPlan = $("#hintPlan");
    if (hintPlan) {
      hintPlan.textContent = "План назначен тренером — редактирование отключено.";
    }
    const clearBtn = $("#clearPlanBtn");
    if (clearBtn) {
      clearBtn.setAttribute("disabled", "disabled");
      clearBtn.classList.add("is-disabled");
    }
  }

  function setStatus(t){
    const statusEl = $("#status");
    if (statusEl) statusEl.textContent = t || "";
  }

  function renderHeader(page = "plan"){
    const ws = state.weekStart;
    const we = addDaysISO(ws, 6);
    const {y,m} = parseISO(ws);
    const monthEl = page === "results" ? $("#monthTitleResults") : $("#monthTitle");
    const rangeEl = page === "results" ? $("#weekRangeResults") : $("#weekRange");
    if (monthEl) monthEl.textContent = `${MONTHS[m-1]} ${y}`.toUpperCase();
    if (rangeEl) rangeEl.textContent = `${ws} — ${we}`;
  }

  function renderDays(page = "plan"){
    const el = page === "results" ? $("#daysResults") : $("#days");
    if (!el) return;
    el.innerHTML = "";
    for (let i=0;i<7;i++){
      const d = addDaysISO(state.weekStart, i);
      const {y,m,day} = (() => { const p = parseISO(d); return {y:p.y,m:p.m,day:p.d}; })();
      const dt = new Date(Date.UTC(y, m-1, day, 12,0,0));
      const wd = new Intl.DateTimeFormat("ru-RU",{timeZone:TZ,weekday:"short"}).format(dt).replace(".","").toLowerCase();
      const b = document.createElement("div");
      b.className = "day" + (d === state.day ? " active":"");
      b.innerHTML = `<div class="dow">${wd}</div><div class="num">${day}</div>`;
      b.addEventListener("click", () => {
        state.day = d;
        state.weekStart = weekStartISO(state.day);
        renderHeader(page);
        renderDays(page);
        loadNote();
      });
      el.appendChild(b);
    }
  }

  function dedupeTabIcons(){
    document.querySelectorAll(".tab").forEach(btn => {
      const icons = Array.from(btn.querySelectorAll("svg"));
      if (icons.length <= 1) {
        return;
      }
      const primaryIcon = btn.querySelector("svg.tab-icon") || icons[0];
      icons.forEach(icon => {
        if (icon !== primaryIcon) {
          icon.remove();
        }
      });
    });
  }

  function renderTabs(){
    // Для страницы "План" используем planKind, для остальных - kind
    const activeKind = state.currentPage === "plan" ? state.planKind : state.kind;
    document.querySelectorAll(".tab").forEach(btn => {
      const k = btn.getAttribute("data-kind");
      // Проверяем, к какой странице относится таб
      const btnPage = btn.closest(".page");
      if (btnPage) {
        const pageId = btnPage.id;
        if (pageId === "pagePlan") {
          btn.classList.toggle("active", k === state.planKind);
        } else if (pageId === "pageResults") {
          btn.classList.toggle("active", k === state.kind);
        } else {
          btn.classList.toggle("active", k === activeKind);
        }
      } else {
        btn.classList.toggle("active", k === activeKind);
      }
    });
    dedupeTabIcons();
  }

  function showPage(pageName) {
    // Проверяем, что pageName передан
    if (!pageName || typeof pageName !== 'string') {
      console.error("❌ showPage: pageName не передан или не является строкой:", pageName);
      return;
    }
    
    console.log("🔄 Переключение на страницу:", pageName);
    
    // Получаем текущую и новую страницы
    const pageId = `page${pageName.charAt(0).toUpperCase() + pageName.slice(1)}`;
    console.log("🔍 Ищем страницу с ID:", pageId, "для pageName:", pageName);
    
    // Используем более надежный способ поиска с fallback
    let newPageEl = $(`#${pageId}`);
    if (!newPageEl) {
      console.warn("⚠️ Селектор $ не нашел элемент, пробуем document.getElementById");
      newPageEl = document.getElementById(pageId);
    }
    
    // Дополнительная проверка для calculator
    if (!newPageEl && pageName === "calculator") {
      console.warn("⚠️ Пробуем альтернативные способы поиска pageCalculator");
      newPageEl = document.querySelector("#pageCalculator");
      if (!newPageEl) {
        newPageEl = document.querySelector('[data-page="calculator"]');
      }
    }
    
    const currentPageEl = document.querySelector(".page:not([style*='display: none'])");
    
    if (!newPageEl) {
      console.error("❌ Страница не найдена:", pageId, "для pageName:", pageName);
      const allPages = Array.from(document.querySelectorAll(".page"));
      console.error("🔍 Доступные страницы:", allPages.map(p => ({id: p.id, dataPage: p.getAttribute("data-page")})));
      return;
    }
    
    console.log("✅ Страница найдена:", pageId, "элемент:", newPageEl);
    console.log("🔍 Текущий display:", newPageEl.style.display, "computed:", window.getComputedStyle(newPageEl).display);
    
    // Если страница уже активна, ничего не делаем
    if (newPageEl === currentPageEl && newPageEl.style.display !== "none") {
      return;
    }
    
    // Для калькулятора: сначала скрываем ВСЕ страницы, затем показываем калькулятор
    if (pageName === "calculator") {
      console.log("🧮 Скрываем все страницы перед показом калькулятора");
      document.querySelectorAll(".page").forEach(page => {
        if (page !== newPageEl) {
          page.style.display = "none";
          page.removeAttribute("data-active");
          page.classList.remove("show-calculator");
        }
      });
    } else {
      // Плавное скрытие текущей страницы для остальных страниц
      if (currentPageEl && currentPageEl !== newPageEl) {
        currentPageEl.style.opacity = "0";
        currentPageEl.style.transform = "translateY(-10px)";
        setTimeout(() => {
          if (currentPageEl) currentPageEl.style.display = "none";
        }, 300);
      }
    }
    
    // Показываем новую страницу
    if (newPageEl) {
      // Для страниц settings и calculator используем упрощенный показ без анимации
      if (pageName === "settings" || pageName === "calculator") {
        const pageType = pageName === "settings" ? "settings" : "calculator";
        console.log(`⚙️ Упрощенный показ страницы ${pageType} (без анимации)`);
        // ПОЛНОСТЬЮ удаляем атрибут style, чтобы убрать любые следы "display: none"
        newPageEl.removeAttribute("style");
        // Устанавливаем стили через отдельные свойства с !important
        newPageEl.setAttribute("data-active", "true");
        newPageEl.classList.add("show-calculator");
        newPageEl.style.setProperty("display", "block", "important");
        newPageEl.style.setProperty("opacity", "1", "important");
        newPageEl.style.setProperty("transform", "translateY(0)", "important");
        newPageEl.style.setProperty("visibility", "visible", "important");
        newPageEl.style.setProperty("position", "relative", "important");
        newPageEl.style.setProperty("z-index", "1", "important");
        
        // Принудительно показываем все дочерние элементы
        const allChildren = newPageEl.querySelectorAll("*");
        allChildren.forEach(child => {
          const childDisplay = window.getComputedStyle(child).display;
          if (childDisplay === "none" && !child.hasAttribute("data-keep-hidden")) {
            child.style.setProperty("display", "", "important");
          }
        });
        
        console.log(`✅ Страница ${pageType} показана, display:`, newPageEl.style.display);
        console.log(`🔍 Computed display после показа:`, window.getComputedStyle(newPageEl).display);
        console.log(`🔍 Computed visibility:`, window.getComputedStyle(newPageEl).visibility);
        console.log(`🔍 Computed opacity:`, window.getComputedStyle(newPageEl).opacity);
        console.log(`🔍 Height:`, newPageEl.offsetHeight, "px");
        console.log(`🔍 Children count:`, newPageEl.children.length);
      } else {
        // Для остальных страниц используем анимацию
        newPageEl.style.display = "block";
        // Используем requestAnimationFrame для плавной анимации
        requestAnimationFrame(() => {
          if (newPageEl) {
            newPageEl.style.opacity = "0";
            newPageEl.style.transform = "translateY(10px)";
            requestAnimationFrame(() => {
              if (newPageEl) {
                newPageEl.style.opacity = "1";
                newPageEl.style.transform = "translateY(0)";
                // Уничтожаем блок быстрых шаблонов после показа страницы (с задержкой, чтобы не блокировать анимацию)
                setTimeout(() => {
                  if (typeof destroyQuickTemplatesForever === 'function') {
                    destroyQuickTemplatesForever();
                  }
                }, 100);
              }
            });
          }
        });
      }
    }
    
    // Обновляем активную кнопку в меню
    document.querySelectorAll(".nav-item").forEach(item => {
      const wasActive = item.classList.contains("active");
      const isActive = item.getAttribute("data-page") === pageName;
      item.classList.toggle("active", isActive);
      
      // Добавляем haptic feedback для мобильных устройств
      if (isActive && !wasActive && window.Telegram?.WebApp?.HapticFeedback) {
        try {
          window.Telegram.WebApp.HapticFeedback.impactOccurred("light");
        } catch (e) {
          // Игнорируем ошибки
        }
      }
    });
    
    state.currentPage = pageName;
    
    if (pageName !== "calculator") {
      const calculatorPageEl = document.getElementById("pageCalculator");
      if (calculatorPageEl) {
        calculatorPageEl.style.display = "none";
        calculatorPageEl.removeAttribute("data-active");
        calculatorPageEl.classList.remove("show-calculator");
      }
    }
    
    // Загружаем данные для страницы
    if (pageName === "stats") {
      loadStats();
    } else if (pageName === "calculator") {
      console.log("🧮 Загрузка страницы калькулятора...");
      
      // ФИНАЛЬНАЯ ПРОВЕРКА: убеждаемся, что страница действительно видна
      const calculatorPageEl = document.getElementById("pageCalculator");
      if (calculatorPageEl) {
        // Проверяем computed стили
        const computedDisplay = window.getComputedStyle(calculatorPageEl).display;
        const computedVisibility = window.getComputedStyle(calculatorPageEl).visibility;
        const computedOpacity = window.getComputedStyle(calculatorPageEl).opacity;
        
        console.log("🔍 Финальная проверка калькулятора:");
        console.log("  - Computed display:", computedDisplay);
        console.log("  - Computed visibility:", computedVisibility);
        console.log("  - Computed opacity:", computedOpacity);
        console.log("  - Height:", calculatorPageEl.offsetHeight, "px");
        console.log("  - Children:", calculatorPageEl.children.length);
        
        // Если страница все еще скрыта, принудительно показываем
        if (computedDisplay === "none" || computedVisibility === "hidden" || computedOpacity === "0") {
          console.warn("⚠️ Страница калькулятора все еще скрыта, применяем принудительное отображение");
          calculatorPageEl.removeAttribute("style");
          calculatorPageEl.style.setProperty("display", "block", "important");
          calculatorPageEl.style.setProperty("opacity", "1", "important");
          calculatorPageEl.style.setProperty("transform", "translateY(0)", "important");
          calculatorPageEl.style.setProperty("visibility", "visible", "important");
          calculatorPageEl.style.setProperty("position", "relative", "important");
          calculatorPageEl.style.setProperty("z-index", "1", "important");
        }
        
        // ПРИНУДИТЕЛЬНО показываем все элементы внутри калькулятора
        const header = calculatorPageEl.querySelector('.page-header');
        const section = calculatorPageEl.querySelector('.settings-section');
        const form = calculatorPageEl.querySelector('.bju-calculator-form');
        
        if (header) {
          header.style.setProperty("display", "block", "important");
          header.style.setProperty("visibility", "visible", "important");
          header.style.setProperty("opacity", "1", "important");
        }
        if (section) {
          section.style.setProperty("display", "block", "important");
          section.style.setProperty("visibility", "visible", "important");
          section.style.setProperty("opacity", "1", "important");
        }
        if (form) {
          form.style.setProperty("display", "block", "important");
          form.style.setProperty("visibility", "visible", "important");
        }
        
        console.log("🔍 Header найден:", !!header, "display:", header ? window.getComputedStyle(header).display : "N/A");
        console.log("🔍 Section найдена:", !!section, "display:", section ? window.getComputedStyle(section).display : "N/A");
        console.log("🔍 Form найдена:", !!form, "display:", form ? window.getComputedStyle(form).display : "N/A");
        if (section) {
          console.log("🔍 Section height:", section.offsetHeight, "px");
          console.log("🔍 Section children:", section.children.length);
        }
      } else {
        console.error("❌ КРИТИЧЕСКАЯ ОШИБКА: pageCalculator не найден!");
        console.error("🔍 Пробуем найти через querySelector:", document.querySelector("#pageCalculator"));
        console.error("🔍 Пробуем найти через data-page:", document.querySelector('[data-page="calculator"]'));
      }
      
      try {
        // Загружаем профиль для предзаполнения полей калькулятора
        loadProfile().then(() => {
          console.log("✅ Профиль загружен для калькулятора");
          // Предзаполняем поля калькулятора данными из профиля, если они пустые
          const calcHeightEl = $("#calcHeight");
          const calcWeightEl = $("#calcWeight");
          const calcAgeEl = $("#calcAge");
          const calcSexEl = $("#calcSex");
          
          const profileHeightEl = $("#profileHeight");
          const profileWeightEl = $("#profileWeight");
          const profileAgeEl = $("#profileAge");
          const profileSexEl = $("#profileSex");
          
          if (calcHeightEl && profileHeightEl?.value && !calcHeightEl.value) {
            calcHeightEl.value = profileHeightEl.value;
            syncHeightControls(calcHeightEl.value);
          }
          if (calcWeightEl && profileWeightEl?.value && !calcWeightEl.value) {
            calcWeightEl.value = profileWeightEl.value;
            syncWeightControls(calcWeightEl.value);
          }
          if (calcAgeEl && profileAgeEl?.value && !calcAgeEl.value) {
            calcAgeEl.value = profileAgeEl.value;
          }
          if (calcSexEl && profileSexEl?.value && !calcSexEl.value) {
            calcSexEl.value = profileSexEl.value || 'male';
            syncSexTabs(calcSexEl.value);
          }
        }).catch(e => {
          console.warn("⚠️ Профиль не загружен, можно ввести данные вручную:", e);
        });
        
        // Настраиваем обработчик кнопки расчета БЖУ
        setTimeout(() => {
          try {
            setupCalculatorHandlers();
          } catch (e) {
            console.error("❌ Ошибка настройки обработчиков калькулятора:", e);
          }
        }, 100);
      } catch (e) {
        console.error("❌ Критическая ошибка при загрузке страницы калькулятора:", e);
      }
      
      // ФИНАЛЬНАЯ ПРОВЕРКА: принудительно показываем страницу еще раз в конце
      setTimeout(() => {
        const finalCheck = document.getElementById("pageCalculator");
        if (finalCheck && finalCheck.style.display === "none") {
          console.warn("⚠️ Страница calculator скрыта, принудительно показываем");
          finalCheck.style.display = "block";
          finalCheck.style.opacity = "1";
          finalCheck.style.visibility = "visible";
        }
      }, 200);
    } else if (pageName === "settings") {
      console.log("⚙️ Загрузка страницы настроек...");
      
      // ПРИНУДИТЕЛЬНО убеждаемся, что страница видна
      const settingsPageEl = document.getElementById("pageSettings");
      if (settingsPageEl) {
        settingsPageEl.style.display = "block";
        settingsPageEl.style.opacity = "1";
        settingsPageEl.style.visibility = "visible";
        settingsPageEl.style.transform = "translateY(0)";
        console.log("✅ Принудительно показана страница settings");
      } else {
        console.error("❌ КРИТИЧЕСКАЯ ОШИБКА: pageSettings не найден!");
      }
      
      // Убеждаемся, что страница показана даже при ошибках
      try {
        // Перепривязываем обработчики при переходе на страницу настроек
        setTimeout(() => {
          try {
            setupSettingsHandlers();
          } catch (e) {
            console.error("❌ Ошибка настройки обработчиков настроек:", e);
          }
        }, 100);
        // Загружаем все настройки асинхронно
        Promise.all([
          loadNotifications(),
          loadProfile(),
          loadReminders()
        ]).then(() => {
          console.log("✅ Все настройки загружены");
          try {
            updateWeeklyGoalProgress();
          } catch (e) {
            console.error("❌ Ошибка обновления прогресса цели:", e);
          }
        }).catch(e => {
          console.error("❌ Ошибка загрузки настроек:", e);
          // Страница все равно должна быть видна даже при ошибках
        });
      } catch (e) {
        console.error("❌ Критическая ошибка при загрузке страницы настроек:", e);
        // Страница все равно должна быть видна
      }
      
      // ФИНАЛЬНАЯ ПРОВЕРКА: принудительно показываем страницу еще раз в конце
      setTimeout(() => {
        const finalCheck = document.getElementById("pageSettings");
        if (finalCheck && finalCheck.style.display === "none") {
          console.warn("⚠️ Страница settings скрыта, принудительно показываем");
          finalCheck.style.display = "block";
          finalCheck.style.opacity = "1";
          finalCheck.style.visibility = "visible";
        }
      }, 200);
    } else if (pageName === "today") {
      // Умная загрузка: используем кеш если он свежий
      const cacheAge = workoutPlanCacheTime ? Date.now() - workoutPlanCacheTime : Infinity;
      if (!workoutPlanCache || cacheAge > CACHE_TTL) {
        loadWorkoutPlan();
      } else {
        // Используем кешированные данные для мгновенного отображения
        if (workoutPlanCache) {
          renderWorkoutPlan(workoutPlanCache);
          updateDailyAchievements(workoutPlanCache);
        }
        // Фоновая загрузка для обновления
        loadWorkoutPlan(false).catch(e => console.warn("Фоновая загрузка:", e));
      }
    } else if (pageName === "plan") {
      // При переключении на страницу "План" устанавливаем planKind и загружаем данные
      if (!state.planKind) {
        state.planKind = "workouts";  // По умолчанию "Тренировки"
      }
      renderTabs();
      loadNote();
      
    } else if (pageName === "results") {
      renderTabs();
      loadNote();
    }
  }

  function getNoteValue(noteEl){
    if (!noteEl) return "";
    if (noteEl.matches && noteEl.matches('[contenteditable="true"]')) {
      const text = (noteEl.innerText || "").replace(/\r/g, "");
      return text === "\n" ? "" : text;
    }
    return noteEl.value || "";
  }

  function setNoteValue(noteEl, value){
    if (!noteEl) return;
    if (noteEl.matches && noteEl.matches('[contenteditable="true"]')) {
      noteEl.textContent = value || "";
      return;
    }
    noteEl.value = value || "";
  }

  async function loadNote(){
    setStatus("Загрузка…");
    try{
      // На странице "План" используем "plan" для тренировок и "meals" для питания
      // На странице "Результаты" используем kind из вкладки (workouts/meals)
      const isPlanPage = state.currentPage === "plan";
      const isPlanMeals = isPlanPage && state.planKind === "meals";
      const kind = isPlanPage ? (isPlanMeals ? "meals" : "plan") : state.kind;
      
      // Убеждаемся, что user_id есть (даже если это "0")
      const uid = getUserId() || "0";
      
      // Для страницы "Результаты" проверяем, что kind установлен
      if (state.currentPage === "results" && !state.kind) {
        state.kind = "workouts"; // По умолчанию
      }
      
      let j = await apiGetNote(state.day, kind);
      // Совместимость со старым хранением: план тренировок мог сохраняться в kind="workouts"
      if (isPlanPage && !isPlanMeals) {
        const hasText = (j?.text || "").trim();
        if (!hasText) {
          const legacy = await apiGetNote(state.day, "workouts");
          if ((legacy?.text || "").trim()) {
            j = legacy;
          }
        }
      }
      const noteEl = state.currentPage === "plan" ? $("#notePlan") : 
                     state.currentPage === "results" ? $("#noteResults") : $("#note");
      if (noteEl) {
        setNoteValue(noteEl, j.text || "");
        state.lastLoadedText = getNoteValue(noteEl);
        
        // Обновляем placeholder в зависимости от раздела
        if (state.currentPage === "results" && "placeholder" in noteEl) {
          if (state.kind === "workouts") {
            noteEl.placeholder = "Запиши результаты тренировки здесь... 💪\n\nНапример:\n- Приседания: 3x10 по 60кг\n- Жим лежа: 4x8 по 80кг";
          } else if (state.kind === "meals") {
            noteEl.placeholder = "Запиши питание здесь... 🍎\n\nНапример:\n- Завтрак: овсянка, яйца\n- Обед: курица, рис, овощи";
          }
        }
      }
      if (state.currentPage === "results") {
        loadMeasurements();
      }
      setStatus(`✓ Загружено · ${state.day}`);
    } catch(e){
      console.error("Ошибка загрузки:", e);
      const errorMsg = e.message || "Не удалось загрузить данные";
      if (errorMsg.includes("401") || errorMsg.includes("403")) {
        setStatus("⚠ Ошибка доступа. Проверьте авторизацию.");
      } else if (errorMsg.includes("500") || errorMsg.includes("502") || errorMsg.includes("503")) {
        setStatus("⚠ Сервер временно недоступен. Попробуйте позже.");
      } else if (errorMsg.includes("NetworkError") || errorMsg.includes("Failed to fetch")) {
        setStatus("⚠ Нет подключения к интернету");
      } else {
        setStatus(`⚠ Ошибка загрузки: ${errorMsg}`);
      }
    }
  }

  (function initBjuPlaceholder(){
    const caloriesEl = $("#bjuCalories");
    const caloriesCard = $("#bjuCaloriesCard");
    const caloriesHint = $("#bjuCaloriesHint");
    if (!caloriesEl || !caloriesCard || !caloriesHint) return;
    const text = caloriesEl.textContent.trim();
    const isEmpty = !text || text === "—";
    caloriesCard.classList.toggle("is-empty", isEmpty);
    caloriesHint.style.display = isEmpty ? "block" : "none";
  })();

  function parseMeasurementPayload(text){
    if (!text) return null;
    try {
      const parsed = JSON.parse(text);
      if (!parsed || typeof parsed !== "object") return null;
      if (parsed.values && typeof parsed.values === "object") {
        return parsed;
      }
      return { version: 1, updatedAt: null, values: parsed };
    } catch (e) {
      console.warn("⚠️ Не удалось распарсить замеры:", e);
      return null;
    }
  }

  function formatMeasurementNumber(value){
    if (value === null || value === undefined || Number.isNaN(value)) return "";
    const rounded = Math.round(value * 10) / 10;
    return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
  }

  function formatMeasurementDate(dayISO){
    const { y, m, d } = parseISO(dayISO);
    return `${d} ${MONTHS_GENITIVE[m - 1]} ${y}`;
  }

  function readMeasurementInputs(){
    const values = {};
    MEASUREMENT_FIELDS.forEach(field => {
      const input = document.getElementById(field.id);
      if (!input) return;
      const num = Number(input.value);
      if (!Number.isNaN(num) && input.value !== "") {
        values[field.key] = num;
      }
    });
    return values;
  }

  function setMeasurementInputs(values){
    MEASUREMENT_FIELDS.forEach(field => {
      const input = document.getElementById(field.id);
      if (!input) return;
      const val = values && values[field.key] !== undefined ? values[field.key] : null;
      input.value = val === null ? "" : formatMeasurementNumber(val);
    });
  }

  function setMeasurementDelta(key, text, stateClass){
    const deltaEl = document.querySelector(`.measurement-delta[data-measurement-key="${key}"]`);
    if (!deltaEl) return;
    deltaEl.textContent = text;
    deltaEl.classList.remove("is-positive", "is-negative", "is-neutral", "is-empty");
    if (stateClass) {
      deltaEl.classList.add(stateClass);
    }
  }

  function updateMeasurementDeltas(currentValues, prevValues){
    MEASUREMENT_FIELDS.forEach(field => {
      const current = currentValues?.[field.key];
      const prev = prevValues?.[field.key];
      if (current === undefined || current === null || prev === undefined || prev === null) {
        setMeasurementDelta(field.key, "—", "is-empty");
        return;
      }
      const delta = Math.round((current - prev) * 10) / 10;
      if (delta === 0) {
        setMeasurementDelta(field.key, "0 см", "is-neutral");
        return;
      }
      const formatted = formatMeasurementNumber(delta);
      if (delta > 0) {
        setMeasurementDelta(field.key, `+${formatted} см`, "is-positive");
      } else {
        setMeasurementDelta(field.key, `${formatted} см`, "is-negative");
      }
    });
  }

  async function findPreviousMeasurements(dayISO, maxDaysBack = 90){
    for (let i = 1; i <= maxDaysBack; i++) {
      const prevDay = addDaysISO(dayISO, -i);
      try {
        const res = await apiGetNote(prevDay, MEASUREMENTS_KIND);
        const parsed = parseMeasurementPayload(res?.text);
        const values = parsed?.values || {};
        if (values && Object.keys(values).length > 0) {
          return { day: prevDay, values };
        }
      } catch (e) {
        console.warn("⚠️ Не удалось загрузить прошлые замеры:", e);
      }
    }
    return null;
  }

  function renderMeasurementsHistory(list){
    const listEl = $("#measurementsHistoryList");
    if (!listEl) return;
    if (!list || list.length === 0) {
      listEl.innerHTML = `<div class="measurements-history-empty">Нет сохраненных замеров</div>`;
      return;
    }
    listEl.innerHTML = list.map(item => {
      const values = item.values || {};
      const fields = MEASUREMENT_FIELDS
        .filter(field => values[field.key] !== undefined && values[field.key] !== null)
        .map(field => `${field.label.toLowerCase()}: ${formatMeasurementNumber(values[field.key])} см`)
        .join(" · ");
      return `
        <div class="measurements-history-item">
          <div class="measurements-history-date">${formatMeasurementDate(item.day)}</div>
          <div class="measurements-history-values">${fields || "Нет данных"}</div>
        </div>
      `;
    }).join("");
  }

  async function loadMeasurementsHistory(){
    if (state.currentPage !== "results" || !state.day) return;
    const history = [];
    for (let i = 0; i <= 90 && history.length < MEASUREMENTS_HISTORY_LIMIT; i++) {
      const checkDay = addDaysISO(state.day, -i);
      try {
        const res = await apiGetNote(checkDay, MEASUREMENTS_KIND);
        const parsed = parseMeasurementPayload(res?.text);
        const values = parsed?.values || {};
        if (values && Object.keys(values).length > 0) {
          history.push({ day: checkDay, values });
        }
      } catch (e) {
        console.warn("⚠️ Не удалось загрузить историю замеров:", e);
      }
    }
    state.measurementsHistory = history;
    renderMeasurementsHistory(history);
  }

  async function loadMeasurements(){
    if (state.currentPage !== "results") return;
    const card = $("#measurementsCard");
    if (!card || !state.day) return;
    try {
      const res = await apiGetNote(state.day, MEASUREMENTS_KIND);
      const parsed = parseMeasurementPayload(res?.text);
      const values = parsed?.values || {};
      const prev = await findPreviousMeasurements(state.day);
      state.measurementsPrevValues = prev?.values || null;
      setMeasurementInputs(values);
      updateMeasurementDeltas(values, state.measurementsPrevValues);
      loadMeasurementsHistory();
    } catch (e) {
      console.error("❌ Ошибка загрузки замеров:", e);
      setMeasurementInputs({});
      updateMeasurementDeltas({}, state.measurementsPrevValues);
      loadMeasurementsHistory();
    }
  }

  let measurementStatusTimer = null;
  function showMeasurementStatus(text, isError = false){
    const statusEl = $("#measurementStatus");
    if (!statusEl) return;
    const textEl = statusEl.querySelector(".status-text");
    if (textEl) textEl.textContent = text;
    statusEl.classList.toggle("error", Boolean(isError));
    statusEl.style.display = "flex";
    if (measurementStatusTimer) clearTimeout(measurementStatusTimer);
    measurementStatusTimer = setTimeout(() => {
      statusEl.style.display = "none";
    }, 2000);
  }

  async function saveMeasurements(){
    if (!state.day) return;
    const values = readMeasurementInputs();
    const payload = {
      version: 1,
      updatedAt: new Date().toISOString(),
      values
    };
    try {
      await apiPut(state.day, MEASUREMENTS_KIND, JSON.stringify(payload));
      const prev = await findPreviousMeasurements(state.day);
      state.measurementsPrevValues = prev?.values || null;
      updateMeasurementDeltas(values, state.measurementsPrevValues);
      loadMeasurementsHistory();
      showMeasurementStatus("Замеры сохранены");
      if (window.Telegram?.WebApp?.HapticFeedback) {
        try {
          window.Telegram.WebApp.HapticFeedback.notificationOccurred("success");
        } catch (e) {}
      }
    } catch (e) {
      console.error("❌ Ошибка сохранения замеров:", e);
      showMeasurementStatus("Ошибка сохранения", true);
    }
  }

  async function saveNoteNow(){
    const noteEl = state.currentPage === "plan" ? $("#notePlan") : 
                   state.currentPage === "results" ? $("#noteResults") : $("#note");
    if (!noteEl) return;
    if (state.currentPage === "plan" && state.trainerLocked) return;
    const val = getNoteValue(noteEl);
    if (val === state.lastLoadedText) return;
    setStatus("Сохранение…");
    try{
      // На странице "План" используем "plan" для тренировок и "meals" для питания
      // На странице "Результаты" используем kind из вкладки (workouts/meals)
      const isPlanPage = state.currentPage === "plan";
      const isPlanMeals = isPlanPage && state.planKind === "meals";
      let kind = isPlanPage ? (isPlanMeals ? "meals" : "plan") : state.kind;
      
      // Для страницы "Результаты" убеждаемся, что kind установлен
      if (state.currentPage === "results" && !kind) {
        kind = "workouts"; // По умолчанию
        state.kind = kind;
      }
      
      await apiPut(state.day, kind, val);
      // Совместимость: если это план тренировок, дублируем в kind="workouts"
      if (isPlanPage && !isPlanMeals) {
        try {
          await apiPut(state.day, "workouts", val);
        } catch (e) {
          console.warn("Не удалось сохранить план в legacy kind=workouts:", e);
        }
      }
      state.lastLoadedText = val;
      setStatus(`✓ Сохранено · ${state.day}`);
      
      // Haptic feedback при успешном сохранении
      if (window.Telegram?.WebApp?.HapticFeedback) {
        try {
          window.Telegram.WebApp.HapticFeedback.notificationOccurred("success");
        } catch(e) {}
      }
    } catch(e){
      console.error("Ошибка сохранения:", e);
      setStatus(`⚠ Ошибка сохранения: ${e.message || "Проверьте подключение"}`);
      
      // Показываем более информативное сообщение
      const errorMsg = e.message || "Не удалось сохранить данные";
      if (errorMsg.includes("401") || errorMsg.includes("403")) {
        setStatus("⚠ Ошибка доступа. Проверьте авторизацию.");
      } else if (errorMsg.includes("500") || errorMsg.includes("502") || errorMsg.includes("503")) {
        setStatus("⚠ Сервер временно недоступен. Попробуйте позже.");
      } else if (errorMsg.includes("NetworkError") || errorMsg.includes("Failed to fetch")) {
        setStatus("⚠ Нет подключения к интернету");
      } else {
        setStatus(`⚠ ${errorMsg}`);
      }
    }
  }

  // Улучшенный debouncing с индикацией сохранения
  function scheduleSave(){
    if (state.savingTimer) clearTimeout(state.savingTimer);
    if (state.currentPage === "plan" && state.trainerLocked) return;
    
    // Показываем индикатор сохранения
    const noteEl = state.currentPage === "plan" ? $("#notePlan") : 
                   state.currentPage === "results" ? $("#noteResults") : $("#note");
    if (noteEl && getNoteValue(noteEl) !== state.lastLoadedText) {
      setStatus("Сохранение…");
    }
    
    state.savingTimer = setTimeout(saveNoteNow, 450);
  }

  function updateCircleProgress(circleId, value, maxValue) {
    const circle = $(circleId);
    if (!circle) return;
    
    const percentage = maxValue > 0 ? Math.min(value / maxValue, 1) : 0;
    const circumference = 2 * Math.PI * 26;
    const offset = circumference * (1 - percentage);
    
    circle.style.strokeDasharray = `${circumference}`;
    circle.style.strokeDashoffset = offset;
  }

  function renderClassicCalendar(chartData, month, year) {
    const grid = $("#calendarGrid");
    const monthYearEl = $("#calendarMonthYear");
    
    if (!grid || !monthYearEl) {
      console.warn("⚠️ Элементы календаря не найдены");
      return;
    }
    
    grid.innerHTML = "";
    
    // Устанавливаем месяц и год
    monthYearEl.textContent = `${MONTHS[month].charAt(0).toUpperCase() + MONTHS[month].slice(1)} ${year}`;
    
    // Получаем первый день месяца и количество дней
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    const startingDayOfWeek = firstDay.getDay();
    const mondayIndex = startingDayOfWeek === 0 ? 6 : startingDayOfWeek - 1;
    
    // Создаем карту дат с тренировками
    const workoutDates = new Set();
    if (chartData) {
      chartData.forEach(item => {
        const date = new Date(item.date + "T12:00:00");
        if (date.getMonth() === month && date.getFullYear() === year && item.has_workout) {
          workoutDates.add(date.getDate());
        }
      });
    }
    
    // Добавляем дни предыдущего месяца
    const prevMonth = month === 0 ? 11 : month - 1;
    const prevYear = month === 0 ? year - 1 : year;
    const prevMonthLastDay = new Date(prevYear, prevMonth + 1, 0).getDate();
    
    for (let i = mondayIndex - 1; i >= 0; i--) {
      const day = prevMonthLastDay - i;
      const dayEl = document.createElement("div");
      dayEl.className = "calendar-day-classic other-month";
      dayEl.textContent = day;
      grid.appendChild(dayEl);
    }
    
    // Добавляем дни текущего месяца
    for (let day = 1; day <= daysInMonth; day++) {
      const dayEl = document.createElement("div");
      dayEl.className = "calendar-day-classic";
      
      const dateStr = iso(year, month + 1, day);
      const isToday = dateStr === state.day;
      const hasWorkout = workoutDates.has(day);
      
      if (hasWorkout) {
        dayEl.classList.add("has-workout");
        // Находим данные о тренировке для tooltip
        const workoutData = chartData?.find(item => {
          const itemDate = new Date(item.date + "T12:00:00");
          return itemDate.getDate() === day && itemDate.getMonth() === month && itemDate.getFullYear() === year;
        });
        if (workoutData) {
          dayEl.title = `Тренировка: ${workoutData.workout_count || 1} ${getWorkoutWord(workoutData.workout_count || 1)}`;
          dayEl.dataset.workoutCount = workoutData.workout_count || 1;
        }
      }
      
      if (isToday) {
        dayEl.classList.add("today");
      }
      
      dayEl.textContent = day;
      dayEl.dataset.date = dateStr;
      
      // Добавляем интерактивность
      dayEl.addEventListener("click", () => {
        if (hasWorkout) {
          // Haptic feedback
          if (window.Telegram?.WebApp?.HapticFeedback) {
            try {
              window.Telegram.WebApp.HapticFeedback.impactOccurred("light");
            } catch (e) {}
          }
        }
      });
      
      grid.appendChild(dayEl);
    }
    
    // Добавляем дни следующего месяца до заполнения сетки
    const totalCells = grid.children.length;
    const remainingCells = 42 - totalCells; // 6 недель * 7 дней
    
    for (let day = 1; day <= remainingCells; day++) {
      const dayEl = document.createElement("div");
      dayEl.className = "calendar-day-classic other-month";
      dayEl.textContent = day;
      grid.appendChild(dayEl);
    }
  }

  // === СИСТЕМА МАСКОТА И МОТИВАЦИИ ===
  
  // Определения достижений
  const ACHIEVEMENTS = [
    { id: "first_workout", name: "Первый шаг", icon: "🎯", description: "Выполни первую тренировку", check: (data) => data.streak.total >= 1 },
    { id: "week_streak", name: "Неделя силы", icon: "🔥", description: "7 дней подряд", check: (data) => data.streak.current >= 7 },
    { id: "month_streak", name: "Месяц чемпиона", icon: "💪", description: "30 дней подряд", check: (data) => data.streak.current >= 30 },
    { id: "hundred_workouts", name: "Сотня тренировок", icon: "💯", description: "100 тренировок", check: (data) => data.streak.total >= 100 },
    { id: "perfect_week", name: "Идеальная неделя", icon: "⭐", description: "7 тренировок за неделю", check: (data) => data.avg_per_week >= 7 },
    { id: "consistent", name: "Стабильность", icon: "📈", description: "50%+ активности", check: (data) => data.workout_percentage >= 50 },
    { id: "dedicated", name: "Преданность", icon: "🏅", description: "75%+ активности", check: (data) => data.workout_percentage >= 75 },
    { id: "legend", name: "Легенда", icon: "👑", description: "90%+ активности", check: (data) => data.workout_percentage >= 90 },
    { id: "max_streak_10", name: "Декада", icon: "🔟", description: "Максимальная серия 10+", check: (data) => data.streak.max >= 10 },
    { id: "max_streak_50", name: "Полвека", icon: "🎖️", description: "Максимальная серия 50+", check: (data) => data.streak.max >= 50 }
  ];
  
  let mascotActivityNote = "";

  function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
  }

  function lerp(a, b, t) {
    return Math.round(a + (b - a) * t);
  }

  function blendRgb(from, to, t) {
    return {
      r: lerp(from.r, to.r, t),
      g: lerp(from.g, to.g, t),
      b: lerp(from.b, to.b, t)
    };
  }

  function applyMascotActivityStyle(data) {
    const mascotSection = $("#mascotSection");
    if (!mascotSection) return { score: 0, message: "" };

    const percentage = clamp((data.workout_percentage || 0) / 100, 0, 1);
    const streakFactor = clamp((data.streak?.current || 0) / 10, 0, 1);
    const avgFactor = clamp((data.avg_per_week || 0) / 5, 0, 1);
    const score = clamp((percentage * 0.6) + (streakFactor * 0.25) + (avgFactor * 0.15), 0, 1);

    const inactive = { r: 122, g: 135, b: 152 };
    const active = { r: 90, g: 162, b: 255 };
    const glow = blendRgb(inactive, active, Math.min(1, score + 0.15));

    mascotSection.style.setProperty("--mascot-intensity", score.toFixed(2));
    mascotSection.style.setProperty("--mascot-accent-rgb", `${active.r}, ${active.g}, ${active.b}`);
    mascotSection.style.setProperty("--mascot-glow-rgb", `${glow.r}, ${glow.g}, ${glow.b}`);

    let message = "Я готов к твоим победам!";
    if (score >= 0.8) message = "Я сияю от твоей активности! Продолжай!";
    else if (score >= 0.55) message = "Я становлюсь ярче, так держать!";
    else if (score >= 0.3) message = "Я чуть тускнею, но верю в тебя!";
    else message = "Мне не хватает твоих тренировок — я блекну.";

    mascotActivityNote = message;
    return { score, message };
  }

  // Комментарии маскота на основе статистики
  function getMascotComment(data) {
    const streak = data.streak.current;
    const total = data.streak.total;
    const percentage = data.workout_percentage;
    const maxStreak = data.streak.max;
    
    if (streak === 0 && total === 0) {
      return "Привет! Начни свой путь к здоровью уже сегодня! 💪";
    }
    
    if (streak === 0 && total > 0) {
      return "Ты уже делал тренировки! Давай продолжим серию! 🔥";
    }
    
    if (streak >= 1 && streak < 3) {
      return `Отлично! У тебя уже ${streak} ${getDayWord(streak)} подряд! Продолжай! 💪`;
    }
    
    if (streak >= 3 && streak < 7) {
      return `Вау! ${streak} ${getDayWord(streak)} подряд! Ты на правильном пути! 🔥`;
    }
    
    if (streak >= 7 && streak < 14) {
      return `Невероятно! Целая неделя подряд! Ты настоящий боец! 💪🔥`;
    }
    
    if (streak >= 14 && streak < 30) {
      return `Две недели! Ты просто машина! Продолжай в том же духе! 🚀`;
    }
    
    if (streak >= 30) {
      return `МЕСЯЦ ПОДРЯД! Ты легенда! Это невероятно! 👑💪`;
    }
    
    if (percentage >= 90) {
      return `90%+ активности! Ты на вершине! Продолжай быть примером! 🌟`;
    }
    
    if (percentage >= 75) {
      return `Отличная активность! Ты очень стабилен! 💪`;
    }
    
    if (percentage >= 50) {
      return `Хорошая активность! Еще немного и будет идеально! 📈`;
    }
    
    if (maxStreak >= 50) {
      return `Твоя максимальная серия ${maxStreak} ${getDayWord(maxStreak)}! Впечатляет! 🏆`;
    }
    
    return `У тебя ${total} ${getWorkoutWord(total)}! Продолжай двигаться вперед! 💪`;
  }
  
  function renderAchievements(data) {
    const grid = $("#achievementsGrid");
    if (!grid) return;
    
    grid.innerHTML = "";
    let unlockedCount = 0;
    
    ACHIEVEMENTS.forEach(achievement => {
      const unlocked = achievement.check(data);
      if (unlocked) unlockedCount++;
      
      const achievementEl = document.createElement("div");
      achievementEl.className = `achievement-item ${unlocked ? 'unlocked' : 'locked'}`;
      achievementEl.innerHTML = `
        <div class="achievement-icon">${achievement.icon}</div>
        <div class="achievement-info">
          <div class="achievement-name">${achievement.name}</div>
          <div class="achievement-description">${achievement.description}</div>
        </div>
        ${unlocked ? '<div class="achievement-check">✓</div>' : ''}
      `;
      
      grid.appendChild(achievementEl);
    });
    
    const achievementsCountEl = $("#achievementsCount");
    if (achievementsCountEl) achievementsCountEl.textContent = `${unlockedCount}/${ACHIEVEMENTS.length}`;
  }
  
  function animateMascot(emotion = "happy") {
    const mascot = $("#mascotCharacter");
    if (!mascot) return;
    
    // Убираем предыдущие классы эмоций
    mascot.classList.remove("mascot-happy", "mascot-excited", "mascot-proud", "mascot-encouraging");
    mascot.classList.add(`mascot-${emotion}`);
    
    // Анимация прыжка
    mascot.style.animation = "none";
    setTimeout(() => {
      mascot.style.animation = "mascotJump 0.6s ease-in-out";
    }, 10);
  }
  
  function updateMascotMessage(message, activityNote = "") {
    const bubble = $("#mascotSpeechBubble");
    const messageEl = $("#mascotMessage");
    if (!bubble || !messageEl) return;
    
    // Анимация появления
    bubble.style.opacity = "0";
    bubble.style.transform = "translateY(10px)";
    
    setTimeout(() => {
      if (activityNote) {
        messageEl.innerHTML = `${message}<span class="mascot-activity-note">${activityNote}</span>`;
      } else {
        messageEl.textContent = message;
      }
      bubble.style.opacity = "1";
      bubble.style.transform = "translateY(0)";
    }, 200);
  }

  async function loadStats(days = null){
    const loading = $("#statsLoading");
    const content = $("#statsContent");
    const error = $("#statsError");
    
    // Используем переданное значение или значение из state
    const statsDays = days !== null ? days : (state.statsDays || 30);
    state.statsDays = statsDays;
    
    if (loading) loading.style.display = "flex";
    if (content) content.style.display = "none";
    if (error) error.style.display = "none";
    
    try {
      const data = await apiGetStats(statsDays);
      state.statsData = data;
      
      // Обновляем метрики
      const currentStreak = data.streak.current;
      const maxStreak = data.streak.max;
      const totalWorkouts = data.streak.total;
      
      const currentStreakEl = $("#currentStreak");
      const maxStreakEl = $("#maxStreak");
      const totalWorkoutsEl = $("#totalWorkouts");
      const currentStreakUnitEl = $("#currentStreakUnit");
      const maxStreakUnitEl = $("#maxStreakUnit");
      const totalWorkoutsUnitEl = $("#totalWorkoutsUnit");
      const currentPercentageEl = $("#currentPercentage");
      const currentAvgEl = $("#currentAvg");
      
      if (currentStreakEl) currentStreakEl.textContent = currentStreak;
      if (maxStreakEl) maxStreakEl.textContent = maxStreak;
      if (totalWorkoutsEl) totalWorkoutsEl.textContent = totalWorkouts;
      
      // Обновляем единицы измерения с правильной лексикой
      if (currentStreakUnitEl) currentStreakUnitEl.textContent = getDayWord(currentStreak);
      if (maxStreakUnitEl) maxStreakUnitEl.textContent = getDayWord(maxStreak);
      if (totalWorkoutsUnitEl) totalWorkoutsUnitEl.textContent = getWorkoutWord(totalWorkouts);
      
      // Обновляем метрики сравнения
      const currentPercentage = data.workout_percentage;
      const currentAvg = data.avg_per_week;
      
      // Процент активности (показываем только текущее значение)
      if (currentPercentageEl) currentPercentageEl.textContent = `${currentPercentage}%`;
      
      // Тренировок в неделю (показываем только текущее значение)
      if (currentAvgEl) currentAvgEl.textContent = currentAvg.toFixed(1);
      
      // Рендерим объединенный график
      renderUnifiedChart(data);
      
      // Загружаем мотивационную цитату для статистики
      loadMotivationalQuoteStat();
      
      // Обновляем круговые индикаторы
      const maxForNormalization = Math.max(maxStreak, currentStreak, 30);
      updateCircleProgress("#currentStreakCircle", currentStreak, maxForNormalization);
      updateCircleProgress("#maxStreakCircle", maxStreak, maxForNormalization);
      updateCircleProgress("#totalWorkoutsCircle", totalWorkouts, state.statsDays);
      
      // Инициализируем календарь на текущий месяц
      const now = mskParts(new Date());
      if (!calendarCurrentMonth) {
        calendarCurrentMonth = now.m - 1;
        calendarCurrentYear = now.y;
      }
      
      // Рендерим календарь
      renderClassicCalendar(data.chart_data, calendarCurrentMonth, calendarCurrentYear);
      
      // Обновляем прогресс недели
      renderWeekProgress(data);
      
      // Рендерим статистику по дням недели
      renderWeekdaysStats(data);
      
      // Рендерим сравнение с предыдущим периодом
      renderPeriodComparison(data, statsDays);
      
      // Обновляем маскота и достижения
      const comment = getMascotComment(data);
      const activityState = applyMascotActivityStyle(data);
      updateMascotMessage(comment, activityState.message);
      renderAchievements(data);
      
      // Определяем эмоцию маскота
      let emotion = "happy";
      if (currentStreak >= 30) emotion = "proud";
      else if (currentStreak >= 7) emotion = "excited";
      else if (currentStreak > 0) emotion = "encouraging";
      animateMascot(emotion);
      
      // Добавляем интерактивность маскоту
      const mascot = $("#mascotCharacter");
      if (mascot && !mascot.hasAttribute("data-interactive")) {
        mascot.setAttribute("data-interactive", "true");
        mascot.onclick = () => {
          // Случайные мотивирующие фразы при клике
          const randomPhrases = [
            "Ты можешь больше! 💪",
            "Каждый день - это шаг к цели! 🎯",
            "Ты на правильном пути! 🔥",
            "Продолжай в том же духе! ⚡",
            "Ты настоящий боец! 🏆",
            "Вперед к новым рекордам! 🚀",
            "Твоя сила в постоянстве! 💎",
            "Ты делаешь это! 🌟"
          ];
          const randomPhrase = randomPhrases[Math.floor(Math.random() * randomPhrases.length)];
          updateMascotMessage(randomPhrase, mascotActivityNote);
          animateMascot("excited");
        };
      }
      
      if (loading) loading.style.display = "none";
      if (content) content.style.display = "block";
    } catch(e) {
      if (loading) loading.style.display = "none";
      if (error) {
        error.style.display = "block";
        error.textContent = `Ошибка загрузки статистики: ${e.message}`;
      }
      console.error("Ошибка загрузки статистики:", e);
    }
  }

  function renderWeekProgress(data) {
    try {
      // Подсчитываем тренировки за текущую неделю
      const now = new Date();
      const weekStart = new Date(now);
      weekStart.setDate(now.getDate() - now.getDay() + 1); // Понедельник
      weekStart.setHours(0, 0, 0, 0);
      
      let weekWorkouts = 0;
      const goal = 3; // Цель по умолчанию
      
      if (data.chart_data && Array.isArray(data.chart_data)) {
        weekWorkouts = data.chart_data.filter(day => {
          try {
            const dayDate = new Date(day.date);
            return dayDate >= weekStart && dayDate <= now && day.has_workout;
          } catch (e) {
            return false;
          }
        }).length;
      }
      
      const progress = Math.min((weekWorkouts / goal) * 100, 100);
      
      const fillEl = $("#weekProgressFill");
      const workoutsEl = $("#weekWorkouts");
      const goalEl = $("#weekGoal");
      
      if (fillEl) {
        // Плавная анимация прогресса
        requestAnimationFrame(() => {
          fillEl.style.transition = "width 0.8s cubic-bezier(0.4, 0, 0.2, 1)";
          fillEl.style.width = `${progress}%`;
          
          // Добавляем эффект при достижении цели
          if (progress >= 100) {
            fillEl.classList.add("goal-reached");
            setTimeout(() => fillEl.classList.remove("goal-reached"), 2000);
          }
        });
      }
      if (workoutsEl) {
        // Анимация изменения числа
        workoutsEl.style.transform = "scale(1.2)";
        workoutsEl.textContent = weekWorkouts;
        setTimeout(() => {
          workoutsEl.style.transform = "scale(1)";
        }, 300);
      }
      if (goalEl) {
        goalEl.textContent = goal;
      }
    } catch (e) {
      console.error("Ошибка рендеринга прогресса недели:", e);
    }
  }

  // Keyboard navigation
  function initKeyboardNavigation() {
    // Навигация по страницам с помощью стрелок влево/вправо
    document.addEventListener('keydown', (e) => {
      // Игнорируем если пользователь вводит текст
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) {
        return;
      }
      
      const navItems = Array.from(document.querySelectorAll('.nav-item'));
      const currentActive = navItems.findIndex(item => item.classList.contains('active'));
      
      // Стрелки влево/вправо для навигации между страницами
      if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        e.preventDefault();
        let newIndex = currentActive;
        
        if (e.key === 'ArrowLeft') {
          newIndex = currentActive > 0 ? currentActive - 1 : navItems.length - 1;
        } else {
          newIndex = currentActive < navItems.length - 1 ? currentActive + 1 : 0;
        }
        
        if (navItems[newIndex]) {
          navItems[newIndex].click();
          navItems[newIndex].focus();
        }
      }
      
      // Быстрые клавиши для перехода на страницы (Ctrl/Cmd + цифра)
      if (e.ctrlKey || e.metaKey) {
        switch(e.key) {
          case '1':
            e.preventDefault();
            showPage('today');
            break;
          case '2':
            e.preventDefault();
            showPage('plan');
            break;
          case '3':
            e.preventDefault();
            showPage('results');
            break;
          case '4':
            e.preventDefault();
            showPage('stats');
            break;
          case '5':
            e.preventDefault();
            showPage('settings');
            break;
        }
      }
    });
  }

  function init(){
    const tg = window.Telegram?.WebApp;
    try { tg?.ready(); tg?.expand(); } catch(e){}
    try { tg?.disableClosingConfirmation(); } catch(e){}

    loadTrainerBinding();

    const now = mskParts(new Date());
    state.day = iso(now.y, now.m, now.d);
    state.weekStart = weekStartISO(state.day);
    calendarCurrentMonth = now.m - 1;
    calendarCurrentYear = now.y;

    renderHeader("plan");
    renderDays("plan");
    renderTabs();
    
    // Инициализируем календарь для страницы "Результаты"
    renderHeader("results");
    renderDays("results");
    
    // Инициализируем pull-to-refresh (если функция определена)
    if (typeof initPullToRefresh === 'function') {
      initPullToRefresh();
    }

    // Согласие при первом запуске
    const consentOverlay = $("#consentOverlay");
    const consentCheckbox = $("#consentCheckbox");
    const consentAcceptBtn = $("#consentAcceptBtn");
    const consentKey = "consent_accepted_v1";
    if (consentOverlay && consentCheckbox && consentAcceptBtn) {
      const isAccepted = localStorage.getItem(consentKey) === "true";
      if (!isAccepted) {
        consentOverlay.style.display = "flex";
        consentCheckbox.checked = false;
        consentAcceptBtn.disabled = true;
        consentCheckbox.addEventListener("change", () => {
          consentAcceptBtn.disabled = !consentCheckbox.checked;
        });
        consentAcceptBtn.addEventListener("click", () => {
          localStorage.setItem(consentKey, "true");
          consentOverlay.style.display = "none";
        });
      }
    }

    // Обработчики для страницы "План"
    $("#prevWeek")?.addEventListener("click", () => {
      state.weekStart = addDaysISO(state.weekStart, -7);
      state.day = state.weekStart;
      renderHeader("plan"); renderDays("plan");
      loadNote();
    });
    
    $("#nextWeek")?.addEventListener("click", () => {
      state.weekStart = addDaysISO(state.weekStart, 7);
      state.day = state.weekStart;
      renderHeader("plan"); renderDays("plan");
      loadNote();
    });

    // Обработчики для страницы "Результаты"
    $("#prevWeekResults")?.addEventListener("click", () => {
      state.weekStart = addDaysISO(state.weekStart, -7);
      state.day = state.weekStart;
      renderHeader("results"); renderDays("results");
      loadNote();
    });
    
    $("#nextWeekResults")?.addEventListener("click", () => {
      state.weekStart = addDaysISO(state.weekStart, 7);
      state.day = state.weekStart;
      renderHeader("results"); renderDays("results");
      loadNote();
    });

    document.querySelectorAll(".tab").forEach(btn => {
      btn.addEventListener("click", () => {
        const kind = btn.getAttribute("data-kind");
        // Определяем, к какой странице относится таб
        const btnPage = btn.closest(".page");
        if (btnPage) {
          const pageId = btnPage.id;
          if (pageId === "pagePlan") {
            // На странице "План" вкладки определяют, какой план загружать (workouts/meals)
            // План тренировок сохраняется в kind="workouts", а не kind="plan"!
            state.planKind = kind;
            renderTabs();
            // Перезагружаем данные для выбранного раздела
            loadNote();
          } else if (pageId === "pageResults") {
            // На странице "Результаты" вкладки определяют kind для загрузки данных
            state.kind = kind;
            renderTabs();
            // Перезагружаем данные для нового раздела
            loadNote();
          } else {
            state.kind = kind;
          }
        } else {
          state.kind = kind;
        }
        renderTabs();
        loadNote();
      });
      
      // Keyboard navigation для табов
      btn.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          btn.click();
        } else if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
          e.preventDefault();
          const tabs = Array.from(btn.closest(".tabs")?.querySelectorAll(".tab") || []);
          const currentIndex = tabs.indexOf(btn);
          let newIndex;
          if (e.key === "ArrowLeft") {
            newIndex = currentIndex > 0 ? currentIndex - 1 : tabs.length - 1;
          } else {
            newIndex = currentIndex < tabs.length - 1 ? currentIndex + 1 : 0;
          }
          if (tabs[newIndex]) {
            tabs[newIndex].focus();
            tabs[newIndex].click();
          }
        }
      });
    });

    // Обработчики нижнего меню навигации с интерактивными эффектами
    document.querySelectorAll(".nav-item").forEach(item => {
      // Добавляем тактильную обратную связь при клике
      item.addEventListener("click", (e) => {
        try {
          e.preventDefault();
          e.stopPropagation();
          
          const page = item.getAttribute("data-page");
          
          if (!page || page.trim() === '') {
            console.error("❌ data-page не найден или пуст для элемента навигации:", item.id || item.className);
            console.error("🔍 Элемент:", item);
            return;
          }
          
          console.log("🖱️ Клик по навигации:", page, "элемент:", item.id || item.className);
          
          // Добавляем эффект "ripple" при клике
          try {
            const ripple = document.createElement("div");
            ripple.style.cssText = `
              position: absolute;
              border-radius: 50%;
              background: rgba(90, 162, 255, 0.4);
              transform: scale(0);
              animation: ripple 0.6s ease-out;
              pointer-events: none;
              width: 80px;
              height: 80px;
              top: 50%;
              left: 50%;
              margin-left: -40px;
              margin-top: -40px;
            `;
            item.style.position = "relative";
            item.appendChild(ripple);
            
            // Удаляем ripple после анимации
            setTimeout(() => {
              try {
                ripple.remove();
              } catch (e) {
                console.warn("⚠️ Не удалось удалить ripple:", e);
              }
            }, 600);
          } catch (rippleError) {
            console.warn("⚠️ Ошибка при создании ripple эффекта:", rippleError);
          }
          
          // Вызываем showPage с улучшенной обработкой ошибок
          try {
            if (typeof showPage !== 'function') {
              console.error("❌ showPage не является функцией!");
              return;
            }
            console.log("🔍 Вызываем showPage с параметром:", page, "тип:", typeof page);
            
            // Для calculator добавляем дополнительную проверку
            if (page === "calculator") {
              console.log("🧮 Специальная обработка для calculator");
              const calcPage = document.getElementById("pageCalculator");
              if (!calcPage) {
                console.error("❌ pageCalculator не найден в DOM!");
                console.error("🔍 Все страницы:", Array.from(document.querySelectorAll(".page")).map(p => p.id));
                return;
              }
              console.log("✅ pageCalculator найден, вызываем showPage");
            }
            
            showPage(page);
            console.log("✅ showPage вызван для:", page);
            
            // Дополнительная проверка для calculator
            if (page === "calculator") {
              setTimeout(() => {
                const calcPage = document.getElementById("pageCalculator");
                if (calcPage) {
                  const computedDisplay = window.getComputedStyle(calcPage).display;
                  console.log("🔍 Проверка после showPage - computed display:", computedDisplay);
                  if (computedDisplay === "none") {
                    console.warn("⚠️ Страница calculator все еще скрыта, принудительно показываем");
                    calcPage.removeAttribute("style");
                    calcPage.style.display = "block";
                    calcPage.style.opacity = "1";
                    calcPage.style.visibility = "visible";
                  }
                }
              }, 100);
            }
          } catch (error) {
            console.error("❌ Ошибка при переключении страницы:", error);
            console.error("📋 Stack trace:", error.stack);
            // Пытаемся показать страницу напрямую как fallback
            try {
              const pageId = `page${page.charAt(0).toUpperCase() + page.slice(1)}`;
              const pageEl = document.getElementById(pageId);
              if (pageEl) {
                document.querySelectorAll(".page").forEach(p => {
                  p.style.display = "none";
                });
                pageEl.removeAttribute("style");
                pageEl.style.display = "block";
                pageEl.style.opacity = "1";
                pageEl.style.visibility = "visible";
                pageEl.style.transform = "translateY(0)";
                console.log("✅ Страница показана через fallback метод");
              }
            } catch (fallbackError) {
              console.error("❌ Критическая ошибка при fallback показе страницы:", fallbackError);
            }
          }
        } catch (e) {
          console.error("❌ Ошибка в обработчике клика навигации:", e);
        }
      });
      
      // Добавляем эффект при наведении
      item.addEventListener("mouseenter", () => {
        const icon = item.querySelector(".nav-icon");
        if (icon && !item.classList.contains("active")) {
          icon.style.transform = "scale(1.05) rotate(2deg)";
        }
      });
      
      item.addEventListener("mouseleave", () => {
        const icon = item.querySelector(".nav-icon");
        if (icon && !item.classList.contains("active")) {
          icon.style.transform = "";
        }
      });
    });
    
    // Добавляем CSS для ripple анимации
    const style = document.createElement("style");
    style.textContent = `
      @keyframes ripple {
        to {
          transform: scale(2);
          opacity: 0;
        }
      }
    `;
    document.head.appendChild(style);
    
    // Добавляем keyboard navigation для нижнего меню
    initKeyboardNavigation();

    // Обработчики навигации календаря
    $("#calendarPrevMonth").addEventListener("click", () => {
      calendarCurrentMonth--;
      if (calendarCurrentMonth < 0) {
        calendarCurrentMonth = 11;
        calendarCurrentYear--;
      }
      if (state.statsData) {
        renderClassicCalendar(state.statsData.chart_data, calendarCurrentMonth, calendarCurrentYear);
      }
    });

    $("#calendarNextMonth").addEventListener("click", () => {
      calendarCurrentMonth++;
      if (calendarCurrentMonth > 11) {
        calendarCurrentMonth = 0;
        calendarCurrentYear++;
      }
      if (state.statsData) {
        renderClassicCalendar(state.statsData.chart_data, calendarCurrentMonth, calendarCurrentYear);
      }
    });

    $("#note")?.addEventListener("input", scheduleSave);
    $("#notePlan")?.addEventListener("input", scheduleSave);
    $("#noteResults")?.addEventListener("input", scheduleSave);

    const saveMeasurementsBtn = $("#saveMeasurementsBtn");
    if (saveMeasurementsBtn) {
      saveMeasurementsBtn.addEventListener("click", (e) => {
        e.preventDefault();
        saveMeasurements();
      });
    }

    document.querySelectorAll(".measurement-input").forEach(input => {
      input.addEventListener("input", () => {
        const values = readMeasurementInputs();
        updateMeasurementDeltas(values, state.measurementsPrevValues);
        const statusEl = $("#measurementStatus");
        if (statusEl) statusEl.style.display = "none";
      });
    });

    const measurementsHistoryToggle = $("#measurementsHistoryToggle");
    if (measurementsHistoryToggle) {
      measurementsHistoryToggle.addEventListener("click", () => {
        const listEl = $("#measurementsHistoryList");
        if (!listEl) return;
        const isHidden = listEl.style.display === "none" || !listEl.style.display;
        listEl.style.display = isHidden ? "flex" : "none";
        measurementsHistoryToggle.classList.toggle("is-open", isHidden);
      });
    }

    const copyPlanBtn = $("#copyPlanBtn");
    if (copyPlanBtn) {
      copyPlanBtn.addEventListener("click", async () => {
        const noteEl = $("#notePlan");
        const text = getNoteValue(noteEl).trim();
        if (!text) {
          setStatus("ℹ️ Нечего копировать");
          return;
        }
        try {
          await navigator.clipboard.writeText(text);
          setStatus("✓ Скопировано");
        } catch (e) {
          const temp = document.createElement("textarea");
          temp.value = text;
          temp.setAttribute("readonly", "");
          temp.style.position = "absolute";
          temp.style.left = "-9999px";
          document.body.appendChild(temp);
          temp.select();
          try {
            document.execCommand("copy");
            setStatus("✓ Скопировано");
          } catch (err) {
            console.error("Copy failed:", err);
            setStatus("⚠ Не удалось скопировать");
          }
          document.body.removeChild(temp);
        }
      });
    }

    const clearPlanBtn = $("#clearPlanBtn");
    if (clearPlanBtn) {
      clearPlanBtn.addEventListener("click", () => {
        const noteEl = $("#notePlan");
        if (!noteEl) return;
        if (!getNoteValue(noteEl)) {
          setStatus("ℹ️ Поле уже пустое");
          return;
        }
        setNoteValue(noteEl, "");
        noteEl.focus();
        scheduleSave();
      });
    }

    const copyResultsBtn = $("#copyResultsBtn");
    if (copyResultsBtn) {
      copyResultsBtn.addEventListener("click", async () => {
        const noteEl = $("#noteResults");
        const text = getNoteValue(noteEl).trim();
        if (!text) {
          setStatus("ℹ️ Нечего копировать");
          return;
        }
        try {
          await navigator.clipboard.writeText(text);
          setStatus("✓ Скопировано");
        } catch (e) {
          const temp = document.createElement("textarea");
          temp.value = text;
          temp.setAttribute("readonly", "");
          temp.style.position = "absolute";
          temp.style.left = "-9999px";
          document.body.appendChild(temp);
          temp.select();
          try {
            document.execCommand("copy");
            setStatus("✓ Скопировано");
          } catch (err) {
            console.error("Copy failed:", err);
            setStatus("⚠ Не удалось скопировать");
          }
          document.body.removeChild(temp);
        }
      });
    }

    const clearResultsBtn = $("#clearResultsBtn");
    if (clearResultsBtn) {
      clearResultsBtn.addEventListener("click", () => {
        const noteEl = $("#noteResults");
        if (!noteEl) return;
        if (!getNoteValue(noteEl)) {
          setStatus("ℹ️ Поле уже пустое");
          return;
        }
        setNoteValue(noteEl, "");
        noteEl.focus();
        scheduleSave();
      });
    }

    // Обработчик кнопки "Зафиксировать результаты"
    document.addEventListener("click", (e) => {
      if (e.target.closest("#saveResultsBtn")) {
        e.preventDefault();
        e.stopPropagation();
        console.log("🔵 Клик по кнопке saveResultsBtn обнаружен через делегирование");
        handleSaveResults();
      }
    });

    // Загружаем мотивационную цитату при инициализации
    loadMotivationalQuote();
    
    // Показываем страницу "Сегодня" по умолчанию
    console.log("🚀 Инициализация завершена, показываем страницу 'Сегодня'");
    showPage("today");
    console.log("✅ showPage('today') вызвана");
    
    // Обработчик кнопки "Обновить" для списка упражнений
    const refreshBtn = $("#refreshWorkoutPlanBtn");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", handleRefreshWorkoutPlan);
      console.log("✅ Обработчик кнопки 'Обновить' добавлен");
    }
    
    // Обработчик кнопки "Перенести результаты"
    const transferBtn = $("#transferResultsBtn");
    if (transferBtn) {
      transferBtn.addEventListener("click", handleTransferResults);
      console.log("✅ Обработчик кнопки 'Перенести результаты' добавлен");
      console.log("🔍 Кнопка найдена:", transferBtn);
    } else {
      console.error("❌ Кнопка transferResultsBtn не найдена!");
      // Попробуем найти через более широкий поиск
      setTimeout(() => {
        const btn = document.getElementById("transferResultsBtn");
        if (btn) {
          btn.addEventListener("click", handleTransferResults);
          console.log("✅ Кнопка найдена и обработчик добавлен (через таймаут)");
        } else {
          console.error("❌ Кнопка transferResultsBtn не найдена даже после таймаута!");
        }
      }, 500);
    }
    
    // Обработчики фильтров периода статистики
    document.querySelectorAll(".period-filter-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const days = parseInt(btn.getAttribute("data-days"));
        
        // Обновляем активную кнопку
        document.querySelectorAll(".period-filter-btn").forEach(b => {
          b.classList.remove("active");
          b.setAttribute("aria-pressed", "false");
        });
        btn.classList.add("active");
        btn.setAttribute("aria-pressed", "true");
        
        // Загружаем статистику с новым периодом
        loadStats(days);
        
        // Haptic feedback
        handleHapticFeedback("light");
      });
      
      // Keyboard navigation для фильтров
      btn.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          btn.click();
        }
      });
    });
  }

  // Функция для переноса результатов тренировки в дневник
  async function handleTransferResults() {
    console.log("🔵 Перенос результатов тренировки в дневник...");
    
    const btn = $("#transferResultsBtn");
    if (btn) {
      btn.style.opacity = "0.6";
      btn.style.pointerEvents = "none";
    }
    
    try {
      // Получаем актуальные данные плана тренировок (принудительно, без кеша)
      const planData = await apiGetWorkoutPlan(true);
      
      if (!planData || !planData.exercises || planData.exercises.length === 0) {
        alert("Нет данных для переноса. Сначала загрузите план тренировок.");
        if (btn) {
          btn.style.opacity = "1";
          btn.style.pointerEvents = "auto";
        }
        return;
      }
      
      // Собираем выполненные упражнения
      const completedExercises = [];
      
      planData.exercises.forEach(exercise => {
        // Проверяем, есть ли выполненные подходы
        const completedSets = exercise.sets?.filter(set => set.completed) || [];
        const skippedSets = exercise.sets?.filter(set => set.skipped) || [];
        
        // Если упражнение полностью выполнено или есть хотя бы один выполненный подход
        if (exercise.completed || completedSets.length > 0) {
          const exerciseText = formatExerciseForResults(exercise, completedSets, skippedSets);
          if (exerciseText) {
            completedExercises.push(exerciseText);
          }
        }
      });
      
      if (completedExercises.length === 0) {
        alert("Нет выполненных упражнений для переноса. Отметьте хотя бы одно упражнение как выполненное.");
        if (btn) {
          btn.style.opacity = "1";
          btn.style.pointerEvents = "auto";
        }
        return;
      }
      
      // Формируем текст для вставки
      const today = new Date();
      const dateStr = today.toLocaleDateString('ru-RU', { 
        day: '2-digit', 
        month: '2-digit', 
        year: 'numeric' 
      });
      
      const resultsText = `Тренировка ${dateStr}\n\n${completedExercises.join('\n\n')}`;
      
      // Переключаемся на страницу "Результаты" и вставляем текст
      showPage("results");
      
      // Устанавливаем вкладку "Тренировки"
      state.kind = "workouts";
      renderTabs();
      
      // Ждем, пока страница отобразится
      setTimeout(() => {
        const resultsTextarea = $("#noteResults");
        if (resultsTextarea) {
          // Сохраняем текущий текст, если он есть
          const currentText = resultsTextarea.value.trim();
          
          // Добавляем новый текст (если есть старый, добавляем с разделителем)
          const newText = currentText 
            ? `${currentText}\n\n---\n\n${resultsText}`
            : resultsText;
          
          resultsTextarea.value = newText;
          
          // Фокус на textarea и прокрутка вниз
          resultsTextarea.focus();
          resultsTextarea.scrollTop = resultsTextarea.scrollHeight;
          
          // Триггерим событие input для автосохранения
          resultsTextarea.dispatchEvent(new Event('input', { bubbles: true }));
          
          // Haptic feedback
          handleHapticFeedback("medium");
          
          // Показываем уведомление об успехе
          showTransferSuccess();
        }
        
        if (btn) {
          btn.style.opacity = "1";
          btn.style.pointerEvents = "auto";
        }
      }, 300);
      
    } catch (e) {
      console.error("Ошибка переноса результатов:", e);
      alert("Ошибка при переносе результатов. Попробуйте еще раз.");
      if (btn) {
        btn.style.opacity = "1";
        btn.style.pointerEvents = "auto";
      }
    }
  }
  
  // Форматирование упражнения для результатов
  function formatExerciseForResults(exercise, completedSets, skippedSets) {
    if (!exercise.name) return null;
    
    let text = `**${exercise.name}**`;
    
    // Если есть выполненные подходы, добавляем их
    if (completedSets.length > 0) {
      const setsText = completedSets.map(set => {
        let setText = `${set.number} подход`;
        
        // Добавляем вес, если есть
        if (set.weight_kg) {
          setText += ` ${set.weight_kg}кг`;
        }
        
        // Добавляем повторения, если есть
        const repsValue = getSetRepsValue(set);
        if (repsValue) {
          setText += ` × ${repsValue}`;
        } else if (set.info) {
          // Пытаемся извлечь информацию из info
          const info = set.info.trim();
          if (info && !info.match(/^\d+\s*кг/i)) {
            setText += ` × ${info}`;
          }
        }
        
        return setText;
      }).join(', ');
      
      text += `\n${setsText}`;
    }
    
    // Если упражнение полностью выполнено, но нет подходов
    if (exercise.completed && (!completedSets || completedSets.length === 0)) {
      text += `\n✓ Выполнено`;
    }
    
    // Добавляем информацию о пропущенных подходах, если есть
    if (skippedSets.length > 0 && completedSets.length > 0) {
      text += `\n(Пропущено подходов: ${skippedSets.length})`;
    }
    
    return text;
  }
  
  // Показ уведомления об успешном переносе
  function showTransferSuccess() {
    // Создаем временное уведомление
    const notification = document.createElement('div');
    notification.className = 'transfer-success-notification';
    notification.innerHTML = `
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M20 6L9 17l-5-5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <span>Результаты перенесены в дневник</span>
    `;
    document.body.appendChild(notification);
    
    // Анимация появления
    requestAnimationFrame(() => {
      notification.style.opacity = "1";
      notification.style.transform = "translateY(0)";
    });
    
    // Удаляем через 3 секунды
    setTimeout(() => {
      notification.style.opacity = "0";
      notification.style.transform = "translateY(-20px)";
      setTimeout(() => notification.remove(), 300);
    }, 3000);
  }

  // Обработчик кнопки "Обновить" для списка упражнений
  async function handleRefreshWorkoutPlan() {
    console.log("🔵 Обновление списка упражнений...");
    const btn = $("#refreshWorkoutPlanBtn");
    if (btn) {
      btn.style.opacity = "0.5";
      btn.style.pointerEvents = "none";
      // Добавляем анимацию вращения
      const icon = btn.querySelector("svg");
      if (icon) {
        icon.style.animation = "spin 1s linear infinite";
      }
    }
    
    try {
      // Принудительно обновляем (сбрасываем кеш)
      workoutPlanCache = null;
      workoutPlanCacheTime = null;
      await loadWorkoutPlan(true);
      console.log("✅ Список упражнений обновлен");
    } catch (e) {
      console.error("❌ Ошибка при обновлении:", e);
    } finally {
      if (btn) {
        setTimeout(() => {
          btn.style.opacity = "1";
          btn.style.pointerEvents = "auto";
          const icon = btn.querySelector("svg");
          if (icon) {
            icon.style.animation = "";
          }
        }, 500);
      }
    }
  }

  // Автоматическое обновление плана каждые 10 секунд (если страница "Сегодня" активна)
  // Используем более длинный интервал и проверяем, что пользователь не прокручивает страницу
  let isScrolling = false;
  let scrollTimeout = null;
  
  window.addEventListener('scroll', () => {
    isScrolling = true;
    if (scrollTimeout) clearTimeout(scrollTimeout);
    scrollTimeout = setTimeout(() => {
      isScrolling = false;
    }, 150); // Считаем, что прокрутка закончилась через 150мс
  }, { passive: true });
  
  // Оптимизированное автообновление - только если кеш устарел
  let autoUpdateInterval = null;
  function startAutoUpdate() {
    if (autoUpdateInterval) clearInterval(autoUpdateInterval);
    autoUpdateInterval = setInterval(() => {
      if (state.currentPage === "today" && !isScrolling) {
        // Проверяем, нужно ли обновление (кеш старше 30 секунд)
        const cacheAge = workoutPlanCacheTime ? Date.now() - workoutPlanCacheTime : Infinity;
        if (cacheAge > 30000) { // Обновляем только если кеш старше 30 секунд
          loadWorkoutPlan(false).catch(e => console.warn("Фоновая загрузка плана:", e));
        }
      }
    }, 30000); // Проверяем каждые 30 секунд (вместо обновления каждые 10)
  }
  
  // Запускаем автообновление при инициализации
  startAutoUpdate();


  async function handleSaveResults() {
    console.log("🔵 handleSaveResults вызвана");
    const btn = $("#saveResultsBtn");
    const textarea = $("#noteResults");
    
    if (!btn || !textarea) {
      console.error("❌ Кнопка или textarea не найдены");
      return;
    }
    
    // Проверяем, что мы на странице "Результаты" и вкладке "Тренировки"
    if (state.currentPage !== "results" || state.kind !== "workouts") {
      console.warn("⚠️ Не на странице 'Результаты' или не вкладка 'Тренировки'");
      return;
    }
    
    const day = state.day || new Date().toISOString().split('T')[0];
    const text = textarea.value.trim();
    
    if (!text) {
      setStatus("⚠️ Нет данных для сохранения");
      return;
    }
    
    // Блокируем кнопку и меняем текст
    btn.disabled = true;
    btn.classList.add("generating");
    const btnText = btn.querySelector(".generate-btn-text");
    const originalText = btnText ? btnText.textContent : "Зафиксировать результаты";
    if (btnText) {
      btnText.textContent = "Сохраняю...";
    }
    
    try {
      setStatus("Сохранение результатов...");
      console.log("🔵 Сохранение результатов тренировки...");
      
      // Сохраняем в раздел workouts
      await apiPut(day, "workouts", text);
      state.lastLoadedText = text;
      
      setStatus(`✅ Результаты тренировки сохранены`);
      console.log("✅ Результаты успешно сохранены");
      
      // Очищаем textarea после сохранения
      textarea.value = "";
      state.lastLoadedText = "";
    } catch (e) {
      console.error("❌ Ошибка сохранения результатов:", e);
      setStatus(`Ошибка: ${e.message}`);
    } finally {
      btn.disabled = false;
      btn.classList.remove("generating");
      if (btnText) {
        btnText.textContent = originalText;
      }
    }
  }

  function renderUnifiedChart(data) {
    const container = $("#unifiedChart");
    if (!container) return;
    
    container.innerHTML = "";
    
    // Используем данные для графика процента активности
    const chartData = data.percentage_chart_data || [];
    if (chartData.length === 0) return;
    
    const width = container.offsetWidth || 300;
    const height = 180;
    // Отступы по краям для графика (без боковых отступов, уменьшен нижний для легенды)
    const padding = { top: 20, right: 0, bottom: 30, left: 0 };
    const graphWidth = width - padding.left - padding.right;
    const graphHeight = height - padding.top - padding.bottom;
    
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("width", width);
    svg.setAttribute("height", height);
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    
    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    g.setAttribute("transform", `translate(${padding.left}, ${padding.top})`);
    
    // Масштабирование данных с учетом отступов
    const maxValue = 100;
    const xScale = (index) => (index / Math.max(chartData.length - 1, 1)) * graphWidth;
    const yScale = (value) => graphHeight - (Math.max(0, Math.min(100, value || 0)) / maxValue) * graphHeight;
    
    // Функция для создания плавной кривой (кубические кривые Безье)
    function createSmoothPath(points, scaleX, scaleY) {
      if (points.length === 0) return "";
      if (points.length === 1) return `M ${scaleX(0)} ${scaleY(points[0])}`;
      
      let path = `M ${scaleX(0)} ${scaleY(points[0])}`;
      
      for (let i = 1; i < points.length; i++) {
        const x0 = scaleX(i - 1);
        const y0 = scaleY(points[i - 1]);
        const x1 = scaleX(i);
        const y1 = scaleY(points[i]);
        
        // Контрольные точки для плавности
        const cp1x = x0 + (x1 - x0) / 3;
        const cp1y = y0;
        const cp2x = x1 - (x1 - x0) / 3;
        const cp2y = y1;
        
        path += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${x1} ${y1}`;
      }
      
      return path;
    }
    
    // Подготовка данных для плавных линий
    const currentValues = chartData.map(p => p.current || 0);
    const averageValues = chartData.map(p => p.average || 0);
    
    // Рисуем линии с плавными кривыми
    const currentPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
    const averagePath = document.createElementNS("http://www.w3.org/2000/svg", "path");
    
    currentPath.setAttribute("d", createSmoothPath(currentValues, (i) => xScale(i), (v) => yScale(v)));
    currentPath.setAttribute("class", "unified-chart-line current");
    averagePath.setAttribute("d", createSmoothPath(averageValues, (i) => xScale(i), (v) => yScale(v)));
    averagePath.setAttribute("class", "unified-chart-line average");
    
    g.appendChild(averagePath);
    g.appendChild(currentPath);
    
    // Рисуем точки на текущем времени (последняя точка)
    if (chartData.length > 0) {
      const lastIndex = chartData.length - 1;
      const lastX = xScale(lastIndex);
      const lastCurrent = yScale(chartData[lastIndex].current || 0);
      const lastAverage = yScale(chartData[lastIndex].average || 0);
      
      // Вертикальная линия текущего времени
      const timeLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
      timeLine.setAttribute("x1", lastX);
      timeLine.setAttribute("y1", 0);
      timeLine.setAttribute("x2", lastX);
      timeLine.setAttribute("y2", graphHeight);
      timeLine.setAttribute("class", "unified-chart-time-line");
      g.appendChild(timeLine);
      
      // Точки
      const currentDot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      currentDot.setAttribute("cx", lastX);
      currentDot.setAttribute("cy", lastCurrent);
      currentDot.setAttribute("class", "unified-chart-dot current");
      g.appendChild(currentDot);
      
      const averageDot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      averageDot.setAttribute("cx", lastX);
      averageDot.setAttribute("cy", lastAverage);
      averageDot.setAttribute("class", "unified-chart-dot average");
      g.appendChild(averageDot);
    }
    
    // Легенда для линий графика
    const legendGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
    legendGroup.setAttribute("transform", `translate(0, ${graphHeight + 15})`);
    
    // Синяя линия - текущие значения
    const legendCurrent = document.createElementNS("http://www.w3.org/2000/svg", "g");
    legendCurrent.setAttribute("transform", "translate(0, 0)");
    
    const legendCurrentLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
    legendCurrentLine.setAttribute("x1", "0");
    legendCurrentLine.setAttribute("y1", "0");
    legendCurrentLine.setAttribute("x2", "20");
    legendCurrentLine.setAttribute("y2", "0");
    legendCurrentLine.setAttribute("class", "unified-chart-line current");
    legendCurrent.appendChild(legendCurrentLine);
    
    const legendCurrentText = document.createElementNS("http://www.w3.org/2000/svg", "text");
    legendCurrentText.setAttribute("x", "28");
    legendCurrentText.setAttribute("y", "4");
    legendCurrentText.setAttribute("class", "unified-chart-legend");
    legendCurrentText.textContent = "Сейчас";
    legendCurrent.appendChild(legendCurrentText);
    
    // Серая линия - средние значения
    const legendAverage = document.createElementNS("http://www.w3.org/2000/svg", "g");
    legendAverage.setAttribute("transform", "translate(80, 0)");
    
    const legendAverageLine = document.createElementNS("http://www.w3.org/2000/svg", "line");
    legendAverageLine.setAttribute("x1", "0");
    legendAverageLine.setAttribute("y1", "0");
    legendAverageLine.setAttribute("x2", "20");
    legendAverageLine.setAttribute("y2", "0");
    legendAverageLine.setAttribute("class", "unified-chart-line average");
    legendAverage.appendChild(legendAverageLine);
    
    const legendAverageText = document.createElementNS("http://www.w3.org/2000/svg", "text");
    legendAverageText.setAttribute("x", "28");
    legendAverageText.setAttribute("y", "4");
    legendAverageText.setAttribute("class", "unified-chart-legend");
    legendAverageText.textContent = "В среднем";
    legendAverage.appendChild(legendAverageText);
    
    legendGroup.appendChild(legendCurrent);
    legendGroup.appendChild(legendAverage);
    g.appendChild(legendGroup);
    
    svg.appendChild(g);
    container.appendChild(svg);
  }

  // Рендерим статистику по дням недели
  function renderWeekdaysStats(data) {
    const container = $("#weekdaysChart");
    if (!container) {
      console.warn("⚠️ Контейнер weekdaysChart не найден");
      return;
    }
    
    container.innerHTML = "";
    
    const weekdayDistribution = data.weekday_distribution || [0, 0, 0, 0, 0, 0, 0];
    const weekdayNames = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
    const maxCount = Math.max(...weekdayDistribution, 1); // Минимум 1 для избежания деления на 0
    
    weekdayDistribution.forEach((count, index) => {
      const item = document.createElement("div");
      item.className = "weekday-bar-item";
      
      const label = document.createElement("div");
      label.className = "weekday-label";
      label.textContent = weekdayNames[index];
      
      const wrapper = document.createElement("div");
      wrapper.className = "weekday-bar-wrapper";
      
      const bar = document.createElement("div");
      bar.className = "weekday-bar";
      
      const fill = document.createElement("div");
      fill.className = "weekday-bar-fill";
      const percentage = (count / maxCount) * 100;
      fill.style.width = `${percentage}%`;
      
      bar.appendChild(fill);
      
      const countEl = document.createElement("div");
      countEl.className = "weekday-count";
      countEl.textContent = count;
      
      wrapper.appendChild(bar);
      wrapper.appendChild(countEl);
      
      item.appendChild(label);
      item.appendChild(wrapper);
      
      container.appendChild(item);
    });
  }

  // Рендерим сравнение с предыдущим периодом
  function renderPeriodComparison(data, days) {
    const container = $("#periodComparison");
    if (!container) {
      console.warn("⚠️ Контейнер periodComparison не найден");
      return;
    }
    
    container.innerHTML = "";
    
    const metricsContainer = document.createElement("div");
    metricsContainer.className = "comparison-metrics";
    
    // Тренировок в неделю
    const avgPerWeek = data.avg_per_week || 0;
    const avgPrevPerWeek = data.avg_prev_per_week || 0;
    const avgDiff = avgPerWeek - avgPrevPerWeek;
    const avgChange = avgPrevPerWeek > 0 ? ((avgDiff / avgPrevPerWeek) * 100).toFixed(1) : 0;
    
    const avgItem = document.createElement("div");
    avgItem.className = "comparison-metric-item";
    avgItem.innerHTML = `
      <div class="comparison-metric-label">Тренировок в неделю</div>
      <div class="comparison-metric-values">
        <span class="comparison-metric-current">${avgPerWeek.toFixed(1)}</span>
        ${avgPrevPerWeek > 0 ? `<span class="comparison-metric-prev">было ${avgPrevPerWeek.toFixed(1)}</span>` : ''}
        ${avgDiff !== 0 ? `<span class="comparison-metric-change ${avgDiff > 0 ? 'positive' : 'negative'}">${avgDiff > 0 ? '+' : ''}${avgChange}%</span>` : ''}
      </div>
    `;
    metricsContainer.appendChild(avgItem);
    
    // Процент активности
    const percentage = data.workout_percentage || 0;
    const avgPercentage = data.avg_percentage || 0;
    const percentageDiff = percentage - avgPercentage;
    const percentageChange = avgPercentage > 0 ? ((percentageDiff / avgPercentage) * 100).toFixed(1) : 0;
    
    const percentageItem = document.createElement("div");
    percentageItem.className = "comparison-metric-item";
    percentageItem.innerHTML = `
      <div class="comparison-metric-label">Процент активности</div>
      <div class="comparison-metric-values">
        <span class="comparison-metric-current">${percentage.toFixed(1)}%</span>
        ${avgPercentage > 0 ? `<span class="comparison-metric-prev">было ${avgPercentage.toFixed(1)}%</span>` : ''}
        ${percentageDiff !== 0 ? `<span class="comparison-metric-change ${percentageDiff > 0 ? 'positive' : 'negative'}">${percentageDiff > 0 ? '+' : ''}${percentageChange}%</span>` : ''}
      </div>
    `;
    metricsContainer.appendChild(percentageItem);
    
    container.appendChild(metricsContainer);
  }

  // === УВЕДОМЛЕНИЯ ===
  async function apiGetNotifications(){
    const uid = getUserId() || "0"; // Fallback на "0"
    try {
      const r = await fetch(NOTIFICATIONS_API, {
        headers: { "X-User-Id": uid }
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return await r.json();
    } catch (e) {
      console.error("Notifications API error:", e);
      return null;
    }
  }

  async function apiSetNotificationFrequency(frequency){
    const uid = getUserId() || "0"; // Fallback на "0"
    try {
      const r = await fetch(NOTIFICATIONS_API, {
        method: "POST",
        headers: {
          "X-User-Id": uid,
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ frequency })
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return await r.json();
    } catch (e) {
      console.error("Set notification frequency error:", e);
      return null;
    }
  }

  function renderNotificationOptions(settings) {
    console.log("🎨 Рендеринг опций уведомлений:", settings);
    const container = $("#frequencyOptions");
    if (!container) {
      console.error("❌ Контейнер frequencyOptions не найден!");
      return;
    }
    
    const options = settings?.options || [
      { value: "3_per_day", label: "3 раза в день" },
      { value: "1_per_day", label: "1 раз в день" },
      { value: "1_per_week", label: "1 раз в неделю" },
      { value: "disabled", label: "Отключено" }
    ];
    
    const currentFrequency = settings?.frequency || "1_per_day";
    
    container.innerHTML = options.map(opt => {
      const isActive = opt.value === currentFrequency;
      return `
        <div class="frequency-option ${isActive ? 'active' : ''}" data-frequency="${opt.value}">
          <div class="frequency-option-content">
            <div class="frequency-option-icon">
              ${isActive ? '✓' : ''}
            </div>
            <div class="frequency-option-label">${opt.label}</div>
          </div>
        </div>
      `;
    }).join('');
    hasRenderedWorkoutPlanOnce = true;
    
    console.log("✅ Опции уведомлений отрендерены, количество:", container.querySelectorAll('.frequency-option').length);
    
    // Добавляем обработчики кликов
    container.querySelectorAll('.frequency-option').forEach(option => {
      option.addEventListener('click', async () => {
        const frequency = option.dataset.frequency;
        console.log("🖱️ Клик по опции частоты:", frequency);
        const result = await apiSetNotificationFrequency(frequency);
        if (result) {
          showNotificationStatus('Настройки сохранены');
          loadNotifications(); // Перезагружаем для обновления UI
        } else {
          showNotificationStatus('Ошибка сохранения', true);
        }
      });
    });
  }

  function showNotificationStatus(message, isError = false) {
    const status = $("#notificationsStatus");
    if (!status) return;
    
    const textEl = status.querySelector('.status-text');
    const iconEl = status.querySelector('.status-icon');
    
    if (textEl) textEl.textContent = message;
    if (iconEl) iconEl.textContent = isError ? '✗' : '✓';
    
    status.style.display = 'flex';
    status.classList.toggle('error', isError);
    
    setTimeout(() => {
      status.style.opacity = '0';
      setTimeout(() => {
        status.style.display = 'none';
        status.style.opacity = '1';
      }, 300);
    }, 2000);
  }

  async function loadNotifications() {
    console.log("📥 Загрузка уведомлений...");
    try {
      const settings = await apiGetNotifications();
      console.log("✅ Настройки уведомлений получены:", settings);
      if (settings) {
        renderNotificationOptions(settings);
      } else {
        console.log("⚠️ Настройки пусты, используем значения по умолчанию");
        // Fallback - показываем опции по умолчанию
        renderNotificationOptions({
          frequency: "1_per_day",
          options: [
            { value: "3_per_day", label: "3 раза в день" },
            { value: "1_per_day", label: "1 раз в день" },
            { value: "1_per_week", label: "1 раз в неделю" },
            { value: "disabled", label: "Отключено" }
          ]
        });
      }
    } catch (e) {
      console.error("❌ Ошибка загрузки уведомлений:", e);
      // Всегда показываем опции, даже при ошибке
      renderNotificationOptions({
        frequency: "1_per_day",
        options: [
          { value: "3_per_day", label: "3 раза в день" },
          { value: "1_per_day", label: "1 раз в день" },
          { value: "1_per_week", label: "1 раз в неделю" },
          { value: "disabled", label: "Отключено" }
        ]
      });
    }
  }

  // === ПЛАН УПРАЖНЕНИЙ НА СЕГОДНЯ ===
  // Кеш для избежания дублирующихся запросов
  let workoutPlanCache = null;
  let workoutPlanCacheTime = null;
  let lastRenderedPlanHash = null; // Хеш последнего отрендеренного плана для предотвращения ненужных обновлений
  let hasRenderedWorkoutPlanOnce = false;
  const CACHE_TTL = 3000; // 3 секунды кеш (уменьшено для более актуальных данных)
  
  function extractRepsValue(set) {
    if (!set) return "";
    let reps = set.reps || "";
    
    // Если reps нет, но есть info - парсим из info
    if (!reps && set.info) {
      const info = set.info;
      // Убираем вес
      reps = info.replace(/\d+\s*кг/gi, "").trim();
      // Убираем "подход", "подхода", "подходов"
      reps = reps.replace(/\d+\s*подход[а-я]*/gi, "").trim();
      // Убираем дефисы и лишние пробелы
      reps = reps.replace(/^[:\-]\s*/, "").trim();
    }
    
    return reps ? reps.trim() : "";
  }
  
  function formatRepsDisplay(repsValue) {
    const reps = (repsValue || "").toString().trim();
    if (!reps) return "";
    if (/повтор/i.test(reps)) return reps;
    if (/до\s*отказа/i.test(reps)) return reps;
    if (/^\d+\s*-\s*\d+$/.test(reps)) {
      return reps.replace(/\s+/g, "") + " повторений";
    }
    return `${reps} повторений`;
  }
  
  function getSetRepsValue(set) {
    const performed = (set?.performed_reps || "").toString().trim();
    if (performed) return performed;
    return extractRepsValue(set);
  }
  
  // Функция для создания простого хеша данных плана
  function hashWorkoutPlan(data) {
    if (!data || !data.exercises) return null;
    return JSON.stringify(data.exercises.map(ex => ({
      name: ex.name,
      sets: ex.sets ? ex.sets.map(s => ({ completed: s.completed, skipped: s.skipped, performed_reps: s.performed_reps || "" })) : []
    })));
  }

  async function apiGetWorkoutPlan(force = false){
    const uid = getUserId() || "0";
    
    // Проверяем кеш
    if (!force && workoutPlanCache && workoutPlanCacheTime) {
      const cacheAge = Date.now() - workoutPlanCacheTime;
      if (cacheAge < CACHE_TTL) {
        console.log("✅ Используем кешированные данные плана");
        return workoutPlanCache;
      }
    }
    
    try {
      // Создаем AbortController для таймаута (совместимость с браузерами)
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);
      
      const r = await fetch(withApiBase(WORKOUT_PLAN_API), {
        headers: { "X-User-Id": uid },
        cache: 'no-cache', // Принудительно не использовать браузерный кеш
        signal: controller.signal
      });
      
      clearTimeout(timeoutId);
      if (!r.ok) {
        const errorText = await r.text();
        console.error(`❌ Workout plan API error: HTTP ${r.status}`, errorText);
        throw new Error(`HTTP ${r.status}: ${errorText}`);
      }
      const data = await r.json();
      
      // Валидация данных
      if (!data || typeof data !== 'object') {
        throw new Error("Неверный формат данных от сервера");
      }
      
      // Нормализуем структуру данных
      if (!data.exercises) {
        data.exercises = [];
      }
      if (!Array.isArray(data.exercises)) {
        data.exercises = [];
      }
      
      // Валидируем каждое упражнение
      data.exercises = data.exercises.filter(ex => {
        if (!ex || typeof ex !== 'object') return false;
        if (!ex.name || typeof ex.name !== 'string') return false;
        if (ex.sets && !Array.isArray(ex.sets)) {
          ex.sets = [];
        }
        return true;
      });
      
      // Сохраняем в кеш
      workoutPlanCache = data;
      workoutPlanCacheTime = Date.now();
      
      return data;
    } catch (e) {
      console.error("❌ Workout plan API error:", e);
      // Возвращаем кеш даже при ошибке, если он есть
      if (workoutPlanCache) {
        console.log("⚠️ Используем старые кешированные данные из-за ошибки");
        return workoutPlanCache;
      }
      return offlineGetWorkoutPlan(uid);
    }
  }

  async function apiUpdateSetState(exerciseName, setNumber, completed, skipped, reps){
    const uid = getUserId() || "0"; // Fallback на "0" если нет uid
    try {
      const payload = {
        exercise_name: exerciseName,
        set_number: setNumber,
        completed: completed,
        skipped: skipped
      };
      if (reps !== undefined) {
        payload.reps = reps;
      }
      const r = await fetch(withApiBase("/api/workout-plan/set-state"), {
        method: "POST",
        headers: {
          "X-User-Id": uid,
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return await r.json();
    } catch (e) {
      console.error("Update set state error:", e);
      const plan = offlineGetWorkoutPlan(uid);
      if (plan && Array.isArray(plan.exercises)) {
        const ex = plan.exercises.find(item => item && item.name === exerciseName);
        if (ex && Array.isArray(ex.sets)) {
          const target = ex.sets.find(s => s.number === setNumber);
          if (target) {
            if (completed !== null && completed !== undefined) target.completed = completed;
            if (skipped !== null && skipped !== undefined) target.skipped = skipped;
            if (reps !== undefined) target.performed_reps = reps;
            offlineSetWorkoutPlan(uid, plan);
            return { ok: true, offline: true };
          }
        }
      }
      return null;
    }
  }

  // Обновление прогресса выполнения упражнений
  function updateWorkoutProgress(data) {
    if (!data || !data.exercises) return;
    
    const progressEl = $("#workoutPlanProgress");
    const progressFill = $("#workoutProgressFill");
    const progressText = $("#workoutProgressText");
    
    if (!progressEl || !progressFill || !progressText) return;
    
    let totalSets = 0;
    let completedSets = 0;
    
    data.exercises.forEach(exercise => {
      if (exercise.sets && exercise.sets.length > 0) {
        exercise.sets.forEach(set => {
          totalSets++;
          if (set.completed) {
            completedSets++;
          }
        });
      }
    });
    
    if (totalSets > 0) {
      const percentage = (completedSets / totalSets) * 100;
      progressFill.style.width = percentage + '%';
      progressText.textContent = `${completedSets}/${totalSets}`;
      progressEl.style.display = 'flex';
      
      // Добавляем анимацию при достижении 100%
      if (percentage === 100) {
        progressEl.classList.add('completed');
        // Haptic feedback
        if (window.Telegram?.WebApp?.HapticFeedback) {
          try {
            window.Telegram.WebApp.HapticFeedback.notificationOccurred("success");
          } catch(e) {}
        }
      } else {
        progressEl.classList.remove('completed');
      }
    } else {
      progressEl.style.display = 'none';
    }
  }
  
  // Обновление достижений дня
  async function updateDailyAchievements(data) {
    try {
      const card = $("#dailyAchievementsCard");
      if (!card) return;
      
      if (!data || !data.exercises || !Array.isArray(data.exercises) || data.exercises.length === 0) {
        card.style.display = "none";
        return;
      }
      
      // Подсчитываем выполненные упражнения и подходы
      let completedExercises = 0;
      let completedSets = 0;
      
      data.exercises.forEach(exercise => {
        if (!exercise) return;
        
        // Упражнение считается выполненным, если все его подходы выполнены
        let exerciseCompleted = false;
        if (exercise.sets && Array.isArray(exercise.sets) && exercise.sets.length > 0) {
          const allSetsCompleted = exercise.sets.every(set => set && set.completed);
          exerciseCompleted = allSetsCompleted;
          
          // Подсчитываем выполненные подходы
          exercise.sets.forEach(set => {
            if (set && set.completed) {
              completedSets++;
            }
          });
        } else if (exercise.completed) {
          // Если нет sets, но есть флаг completed
          exerciseCompleted = true;
        }
        
        if (exerciseCompleted) {
          completedExercises++;
        }
      });
      
      // Обновляем счетчики
      const exercisesCountEl = $("#dailyExercisesCount");
      const setsCountEl = $("#dailySetsCount");
      if (exercisesCountEl) exercisesCountEl.textContent = completedExercises;
      if (setsCountEl) setsCountEl.textContent = completedSets;
      
      // Получаем текущую серию из статистики
      try {
        const stats = await apiGetStats(30);
        if (stats && stats.streak) {
          const streakCountEl = $("#dailyStreakCount");
          if (streakCountEl) streakCountEl.textContent = stats.streak.current || 0;
        }
      } catch (e) {
        console.log("Не удалось загрузить серию для достижений дня:", e);
        const streakCountEl = $("#dailyStreakCount");
        if (streakCountEl) streakCountEl.textContent = "0";
      }
      
      // Показываем карточку только если есть достижения
      if (completedExercises > 0 || completedSets > 0) {
        card.style.display = "block";
      } else {
        card.style.display = "none";
      }
    } catch (e) {
      console.error("Ошибка обновления достижений дня:", e);
    }
  }
  
  // Загрузка мотивационной цитаты
  function loadMotivationalQuote() {
    try {
      const quotes = [
        { text: "Единственный способ начать — это перестать говорить и начать делать.", author: "Уолт Дисней" },
        { text: "Успех — это способность идти от неудачи к неудаче, не теряя энтузиазма.", author: "Уинстон Черчилль" },
        { text: "Будущее принадлежит тем, кто верит в красоту своих мечтаний.", author: "Элеонора Рузвельт" },
        { text: "Не важно, как медленно ты идешь, до тех пор, пока ты не останавливаешься.", author: "Конфуций" },
        { text: "Твоя единственная конкуренция — это тот человек, которым ты был вчера.", author: "Неизвестный" },
        { text: "Боль — это временно. Сдаться — это навсегда.", author: "Лэнс Армстронг" },
        { text: "Сила не приходит от физических способностей. Она приходит от несгибаемой воли.", author: "Махатма Ганди" },
        { text: "Сложные времена создают сильных людей. Сильные люди создают хорошие времена.", author: "Неизвестный" },
        { text: "Твое тело может все. Это твой разум нужно убедить.", author: "Неизвестный" },
        { text: "Победители — это те, кто встает после каждого падения.", author: "Неизвестный" },
        { text: "Потенциал каждого человека безграничен. Все дело в том, чтобы его раскрыть.", author: "Неизвестный" },
        { text: "Не жди идеального момента. Начни прямо сейчас.", author: "Неизвестный" },
        { text: "Разница между возможным и невозможным заключается в воле человека.", author: "Томми Ласорда" },
        { text: "Тренировка — это не пытка. Это инвестиция в себя.", author: "Неизвестный" },
        { text: "Каждый эксперт был когда-то новичком. Каждый профессионал начинал как любитель.", author: "Хелен Хейс" }
      ];
      
      if (!quotes || quotes.length === 0) return;
      
      const randomIndex = Math.floor(Math.random() * quotes.length);
      const randomQuote = quotes[randomIndex];
      
      if (!randomQuote) return;
      
      const quoteEl = $("#motivationalQuote");
      const authorEl = $("#motivationalAuthor");
      
      if (quoteEl && randomQuote.text) {
        quoteEl.textContent = randomQuote.text;
      }
      if (authorEl && randomQuote.author) {
        authorEl.textContent = `— ${randomQuote.author}`;
      }
    } catch (e) {
      console.error("Ошибка загрузки мотивационной цитаты:", e);
    }
  }
  
  // Загрузка мотивационной цитаты для статистики
  function loadMotivationalQuoteStat() {
    const quotes = [
      { text: "Продолжай идти! Каждый день приближает тебя к цели.", author: "" },
      { text: "Твоя последовательность — ключ к успеху.", author: "" },
      { text: "Каждая тренировка делает тебя сильнее.", author: "" },
      { text: "Вперед! Ты на правильном пути!", author: "" },
      { text: "Великие дела рождаются из маленьких ежедневных усилий.", author: "" },
      { text: "Твоя дисциплина сегодня — твоя свобода завтра.", author: "" }
    ];
    
    const randomQuote = quotes[Math.floor(Math.random() * quotes.length)];
    const quoteEl = $("#motivationalQuoteStat");
    const quoteTextEl = $("#motivationalQuoteStatText");
    const quoteAuthorEl = $("#motivationalQuoteStatAuthor");
    
    if (quoteEl && quoteTextEl) {
      quoteTextEl.textContent = randomQuote.text;
      if (quoteAuthorEl) quoteAuthorEl.textContent = randomQuote.author;
      quoteEl.style.display = "block";
    }
  }
  
  // Обновление прогресса из DOM (после изменения состояния)
  function updateWorkoutProgressFromDOM() {
    const container = $("#workoutPlanExercises");
    if (!container || container.style.display === 'none') return;
    
    const allSets = container.querySelectorAll('.workout-set');
    const completedSets = container.querySelectorAll('.workout-set.completed');
    
    const progressEl = $("#workoutPlanProgress");
    const progressFill = $("#workoutProgressFill");
    const progressText = $("#workoutProgressText");
    
    if (!progressEl || !progressFill || !progressText || allSets.length === 0) return;
    
    const totalSets = allSets.length;
    const completed = completedSets.length;
    const percentage = (completed / totalSets) * 100;
    
    progressFill.style.width = percentage + '%';
    progressText.textContent = `${completed}/${totalSets}`;
    progressEl.style.display = 'flex';
    
    if (percentage === 100) {
      progressEl.classList.add('completed');
      if (window.Telegram?.WebApp?.HapticFeedback) {
        try {
          window.Telegram.WebApp.HapticFeedback.notificationOccurred("success");
        } catch(e) {}
      }
    } else {
      progressEl.classList.remove('completed');
    }
  }

  function renderWorkoutPlan(data) {
    const container = $("#workoutPlanExercises");
    const loading = $("#workoutPlanLoading");
    const empty = $("#workoutPlanEmpty");
    
    if (!container) return;
    
    loading.style.display = "none";
    
    // Проверяем наличие упражнений (независимо от has_plan флага)
    if (!data || !data.exercises || data.exercises.length === 0) {
      container.style.display = "none";
      empty.style.display = "flex";
      lastRenderedPlanHash = null;
      return;
    }
    
    // Проверяем, изменились ли данные (для предотвращения ненужных перерисовок)
    const currentHash = hashWorkoutPlan(data);
    if (currentHash === lastRenderedPlanHash && container.innerHTML.trim() !== "") {
      // Данные не изменились, обновляем только состояния чекбоксов без полной перерисовки
      updateWorkoutPlanStates(data);
      return;
    }
    
    empty.style.display = "none";
    container.style.display = "block";
    
    // Сохраняем хеш после рендеринга
    lastRenderedPlanHash = currentHash;
    
    // Подсчитываем прогресс выполнения упражнений
    updateWorkoutProgress(data);
    
    // Обновляем достижения дня
    updateDailyAchievements(data);
    
    const prefersReducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const isSmallScreen = window.matchMedia && window.matchMedia('(max-width: 640px)').matches;
    const shouldAnimateEntries = !hasRenderedWorkoutPlanOnce && !prefersReducedMotion && !isSmallScreen;

    // Добавляем плавное появление упражнений
    container.style.opacity = '0';
    container.classList.toggle('no-entry-anim', !shouldAnimateEntries);
    container.innerHTML = data.exercises.map((exercise, exIdx) => {
      if (!exercise || !exercise.name) return '';
      
      // Определяем, выполнено ли упражнение (все подходы выполнены)
      const hasSets = exercise.sets && Array.isArray(exercise.sets) && exercise.sets.length > 0;
      const allCompleted = exercise.completed || (hasSets && exercise.sets.every(set => set && set.completed));
      
      const entryAnimation = shouldAnimateEntries
        ? ` style="animation: fadeInUp 0.4s cubic-bezier(0.4, 0, 0.2, 1) ${exIdx * 0.05}s both;"`
        : '';
      return `
        <div class="workout-exercise ${allCompleted ? 'completed' : ''}" data-exercise="${exIdx}"${entryAnimation}>
            <div class="workout-exercise-header">
            <div class="workout-exercise-checkbox" data-exercise-name="${exercise.name}">
              ${allCompleted ? '✓' : ''}
            </div>
            <div class="workout-exercise-title-block">
              <div class="workout-exercise-name">${exercise.name}</div>
              <div class="workout-exercise-weights">
                <span class="workout-exercise-weight-item">
                  <span class="workout-exercise-weight-label">Рабочий вес:</span>
                  <span class="workout-exercise-weight-value">${exercise.working_weight || 0}</span>
                </span>
                <span class="workout-exercise-weight-item">
                  <span class="workout-exercise-weight-label">Максимальный вес:</span>
                  <span class="workout-exercise-weight-value">${exercise.max_weight || 0}</span>
                </span>
              </div>
            </div>
          </div>
          ${hasSets ? `
            <div class="workout-exercise-sets">
              ${exercise.sets.map((set, setIdx) => {
                const setId = `set-${exIdx}-${setIdx}`;
                const isCompleted = set.completed;
                const isSkipped = set.skipped;
                
                // Извлекаем вес
                let weightKg = set.weight_kg || null;
                
                // Если вес не задан, пробуем извлечь из info
                if (!weightKg && set.info) {
                  const info = set.info;
                  const weightMatch = info.match(/(\d+)\s*кг/i);
                  if (weightMatch) {
                    weightKg = weightMatch[1];
                  }
                }
                
                const planRepsValue = extractRepsValue(set);
                const performedRepsValue = (set.performed_reps || '').toString().trim();
                const displayRepsValue = performedRepsValue || planRepsValue;
                const repsText = formatRepsDisplay(displayRepsValue);
                
                const isLast = setIdx === exercise.sets.length - 1;
                
                return `
                  <div class="workout-set-wrapper ${isCompleted ? 'completed' : ''} ${isSkipped ? 'skipped' : ''}">
                    <div class="workout-set ${isCompleted ? 'completed' : ''} ${isSkipped ? 'skipped' : ''}" 
                         data-exercise="${exercise.name}" 
                         data-set="${set.number}"
                         id="${setId}">
                      <div class="workout-set-checkbox">
                        ${isCompleted ? '✓' : isSkipped ? '✗' : ''}
                      </div>
                      <div class="workout-set-info">
                        ${repsText ? `
                          <span class="workout-set-reps" tabindex="0" role="button" aria-label="Редактировать повторения"
                                data-plan-reps="${planRepsValue}" data-performed-reps="${performedRepsValue}">
                            ${repsText}
                          </span>
                          <input class="workout-set-reps-input" type="text" inputmode="text" autocomplete="off" spellcheck="false"
                                 aria-label="Фактические повторения" value="${performedRepsValue}" placeholder="${planRepsValue}">
                        ` : ''}
                        ${weightKg ? `<span class="workout-set-weight">${weightKg} кг</span>` : ''}
                        ${!repsText && !weightKg ? '<span class="workout-set-placeholder">Выполнить</span>' : ''}
                      </div>
                    </div>
                  </div>
                `;
              }).join('')}
            </div>
          ` : ''}
        </div>
      `;
    }).join('');
    
    requestAnimationFrame(() => {
      container.style.opacity = '1';
    });
    
    // Добавляем обработчики для упражнений
    container.querySelectorAll('.workout-exercise-header').forEach(header => {
      header.addEventListener('click', async (e) => {
        e.stopPropagation();
        e.preventDefault();
        const exerciseEl = header.closest('.workout-exercise');
        if (!exerciseEl) return;
        const checkbox = header.querySelector('.workout-exercise-checkbox');
        if (!checkbox) return;
        const exerciseName = checkbox.dataset.exerciseName;
        if (!exerciseName) return;
        const sets = exerciseEl.querySelectorAll('.workout-set');
        
        // Определяем, все ли подходы выполнены
        let allCompleted = true;
        sets.forEach(setEl => {
          if (!setEl.classList.contains('completed')) {
            allCompleted = false;
          }
        });
        
        // Если все выполнены - снимаем отметки, иначе - отмечаем все как выполненные
        const newState = !allCompleted;
        
        for (const setEl of sets) {
          const setNumber = parseInt(setEl.dataset.set);
          await apiUpdateSetState(exerciseName, setNumber, newState, false);
          
          const wrapperEl = setEl.closest('.workout-set-wrapper');
          const setCheckbox = setEl.querySelector('.workout-set-checkbox');
          
          // Обновляем синхронно для корректной проверки состояния
          if (newState) {
            setEl.classList.add('completed');
            setEl.classList.remove('skipped');
            if (wrapperEl) {
              wrapperEl.classList.add('completed');
              wrapperEl.classList.remove('skipped');
            }
            if (setCheckbox) {
              setCheckbox.textContent = '✓';
              setCheckbox.classList.add('checkmark-pop');
              setTimeout(() => setCheckbox.classList.remove('checkmark-pop'), 600);
            }
          } else {
            setEl.classList.remove('completed');
            setEl.classList.remove('skipped');
            if (wrapperEl) {
              wrapperEl.classList.remove('completed');
              wrapperEl.classList.remove('skipped');
            }
            if (setCheckbox) setCheckbox.textContent = '';
          }
        }
        
        // Проверяем, все ли подходы выполнены после изменения
        const allSetsAfter = exerciseEl.querySelectorAll('.workout-set');
        let allCompletedAfter = true;
        let hasSets = allSetsAfter.length > 0;
        
        allSetsAfter.forEach(s => {
          if (!s.classList.contains('completed')) {
            allCompletedAfter = false;
          }
        });
        
        // Обновляем состояние упражнения с задержкой для плавной анимации
        requestAnimationFrame(() => {
          const exerciseCheckbox = header.querySelector('.workout-exercise-checkbox');
          if (allCompletedAfter && hasSets) {
            exerciseEl.classList.add('completed');
            if (exerciseCheckbox) exerciseCheckbox.textContent = '✓';
          } else {
            exerciseEl.classList.remove('completed');
            if (exerciseCheckbox) exerciseCheckbox.textContent = '';
          }
          
          // Обновляем прогресс
          setTimeout(() => updateWorkoutProgressFromDOM(), 100);
        });
      });
    });
    
    // Добавляем обработчики для подходов
    container.querySelectorAll('.workout-set').forEach(setEl => {
      setEl.addEventListener('click', async (e) => {
        e.stopPropagation(); // Предотвращаем срабатывание на упражнении
        e.preventDefault();
        
        const exerciseName = setEl.dataset.exercise;
        if (!exerciseName) return;
        const setNumber = parseInt(setEl.dataset.set);
        if (isNaN(setNumber)) return;
        const setCheckbox = setEl.querySelector('.workout-set-checkbox');
        const exerciseEl = setEl.closest('.workout-exercise');
        if (!exerciseEl) return;
        const exerciseHeader = exerciseEl.querySelector('.workout-exercise-header');
        if (!exerciseHeader) return;
        const exerciseCheckbox = exerciseHeader.querySelector('.workout-exercise-checkbox');
        
        const isCompleted = setEl.classList.contains('completed');
        const isSkipped = setEl.classList.contains('skipped');
        
        let newCompleted = false;
        let newSkipped = false;
        
        // Логика переключения: нет -> выполнено -> пропущено -> нет
        if (!isCompleted && !isSkipped) {
          newCompleted = true;
          newSkipped = false;
        } else if (isCompleted && !isSkipped) {
          newCompleted = false;
          newSkipped = true;
        } else {
          newCompleted = false;
          newSkipped = false;
        }
        
        // Haptic feedback
        if (window.Telegram?.WebApp?.HapticFeedback) {
          try {
            if (newCompleted) {
              window.Telegram.WebApp.HapticFeedback.impactOccurred("medium");
            } else if (newSkipped) {
              window.Telegram.WebApp.HapticFeedback.impactOccurred("light");
            }
          } catch (e) {}
        }
        
        // Обновляем состояние
        try {
          await apiUpdateSetState(exerciseName, setNumber, newCompleted, newSkipped);
        } catch (e) {
          console.error("Ошибка обновления состояния подхода:", e);
          return;
        }
        
        // Обновляем UI с плавной анимацией
        const wrapperEl = setEl.closest('.workout-set-wrapper');
        if (!setCheckbox) return;
        
        // Добавляем анимацию успеха
        if (newCompleted) {
          setCheckbox.classList.add('checkmark-pop');
          setTimeout(() => setCheckbox.classList.remove('checkmark-pop'), 600);
        }
        
        requestAnimationFrame(() => {
          setEl.classList.toggle('completed', newCompleted);
          setEl.classList.toggle('skipped', newSkipped);
          if (wrapperEl) {
            wrapperEl.classList.toggle('completed', newCompleted);
            wrapperEl.classList.toggle('skipped', newSkipped);
          }
          setCheckbox.textContent = newCompleted ? '✓' : newSkipped ? '✗' : '';
          
          // Обновляем прогресс
          setTimeout(() => {
            updateWorkoutProgressFromDOM();
            // Обновляем достижения дня
            const planData = workoutPlanCache;
            if (planData) updateDailyAchievements(planData);
          }, 100);
        });
        
        // Проверяем, все ли подходы выполнены
        const allSets = exerciseEl.querySelectorAll('.workout-set');
        let allCompleted = true;
        let hasSets = allSets.length > 0;
        
        allSets.forEach(s => {
          if (!s.classList.contains('completed')) {
            allCompleted = false;
          }
        });
        
        // Обновляем состояние упражнения с задержкой для плавной анимации
        requestAnimationFrame(() => {
          if (exerciseCheckbox) {
            if (allCompleted && hasSets) {
              exerciseEl.classList.add('completed');
              exerciseCheckbox.textContent = '✓';
            } else {
              exerciseEl.classList.remove('completed');
              exerciseCheckbox.textContent = '';
            }
          }
        });
      });
    });
    
    // Редактирование повторений внутри подхода
    const openRepsEditor = (repsEl) => {
      const infoEl = repsEl.closest('.workout-set-info');
      const inputEl = infoEl?.querySelector('.workout-set-reps-input');
      if (!infoEl || !inputEl) return;
      if (infoEl.classList.contains('is-editing')) return;
      const currentValue = repsEl.dataset.performedReps || '';
      inputEl.value = currentValue;
      inputEl.dataset.originalValue = currentValue;
      inputEl.placeholder = repsEl.dataset.planReps || '';
      infoEl.classList.add('is-editing');
      inputEl.focus();
      inputEl.select();
    };
    
    const closeRepsEditor = (infoEl) => {
      if (!infoEl) return;
      infoEl.classList.remove('is-editing');
    };
    
    const saveRepsEditor = async (repsEl, inputEl) => {
      const infoEl = repsEl.closest('.workout-set-info');
      const setEl = repsEl.closest('.workout-set');
      if (!setEl) return;
      
      const originalValue = (inputEl.dataset.originalValue || '').trim();
      const newValue = inputEl.value.trim();
      if (newValue === originalValue) {
        closeRepsEditor(infoEl);
        return;
      }
      
      const exerciseName = setEl.dataset.exercise;
      const setNumber = parseInt(setEl.dataset.set);
      if (!exerciseName || Number.isNaN(setNumber)) {
        closeRepsEditor(infoEl);
        return;
      }
      
      const result = await apiUpdateSetState(exerciseName, setNumber, null, null, newValue);
      if (!result) {
        inputEl.value = originalValue;
        closeRepsEditor(infoEl);
        return;
      }
      
      repsEl.dataset.performedReps = newValue;
      inputEl.dataset.originalValue = newValue;
      
      const planRepsValue = repsEl.dataset.planReps || '';
      const displayRepsValue = newValue || planRepsValue;
      const displayText = formatRepsDisplay(displayRepsValue);
      if (displayText) {
        repsEl.textContent = displayText;
      }
      
      if (workoutPlanCache?.exercises) {
        workoutPlanCache.exercises.forEach(ex => {
          if (ex.name === exerciseName && Array.isArray(ex.sets)) {
            const targetSet = ex.sets.find(s => s.number === setNumber);
            if (targetSet) {
              targetSet.performed_reps = newValue;
            }
          }
        });
      }
      
      closeRepsEditor(infoEl);
    };
    
    container.querySelectorAll('.workout-set-reps').forEach(repsEl => {
      repsEl.addEventListener('click', (e) => {
        e.stopPropagation();
        e.preventDefault();
        openRepsEditor(repsEl);
      });
      
      repsEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          openRepsEditor(repsEl);
        }
      });
    });
    
    container.querySelectorAll('.workout-set-reps-input').forEach(inputEl => {
      inputEl.addEventListener('click', (e) => {
        e.stopPropagation();
      });
      
      inputEl.addEventListener('keydown', async (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          const repsEl = inputEl.closest('.workout-set-info')?.querySelector('.workout-set-reps');
          if (repsEl) await saveRepsEditor(repsEl, inputEl);
        } else if (e.key === 'Escape') {
          e.preventDefault();
          inputEl.dataset.cancelled = "1";
          inputEl.value = inputEl.dataset.originalValue || '';
          closeRepsEditor(inputEl.closest('.workout-set-info'));
        }
      });
      
      inputEl.addEventListener('blur', async () => {
        if (inputEl.dataset.cancelled === "1") {
          inputEl.dataset.cancelled = "";
          return;
        }
        const repsEl = inputEl.closest('.workout-set-info')?.querySelector('.workout-set-reps');
        if (repsEl) await saveRepsEditor(repsEl, inputEl);
      });
    });
  }
  
  // Функция для обновления только состояний чекбоксов без полной перерисовки
  function updateWorkoutPlanStates(data) {
    if (!data || !data.exercises) return;
    
    data.exercises.forEach((exercise, exIdx) => {
      const exerciseEl = document.querySelector(`.workout-exercise[data-exercise="${exIdx}"]`);
      if (!exerciseEl) return;
      
      const exerciseCheckbox = exerciseEl.querySelector('.workout-exercise-checkbox');
      if (exerciseCheckbox) {
        exerciseCheckbox.textContent = exercise.completed ? '✓' : '';
        exerciseEl.classList.toggle('completed', exercise.completed);
      }
      
      if (exercise.sets) {
        exercise.sets.forEach((set, setIdx) => {
          const setId = `set-${exIdx}-${setIdx}`;
          const setEl = document.getElementById(setId);
          if (!setEl) return;
          
          const setWrapper = setEl.closest('.workout-set-wrapper');
          const setCheckbox = setEl.querySelector('.workout-set-checkbox');
          
          if (setCheckbox) {
            setCheckbox.textContent = set.completed ? '✓' : set.skipped ? '✗' : '';
          }
          
          if (setWrapper) {
            setWrapper.classList.toggle('completed', set.completed);
            setWrapper.classList.toggle('skipped', set.skipped);
            setEl.classList.toggle('completed', set.completed);
            setEl.classList.toggle('skipped', set.skipped);
          }
        });
      }
    });
  }

  async function loadWorkoutPlan(force = false) {
    const loading = $("#workoutPlanLoading");
    const empty = $("#workoutPlanEmpty");
    const exercises = $("#workoutPlanExercises");
    
    if (!loading || !empty || !exercises) {
      console.warn("⚠️ Элементы workout plan не найдены");
      return;
    }
    
    // Сохраняем позицию прокрутки перед обновлением (только для фоновых обновлений)
    const scrollPosition = force ? null : window.pageYOffset || document.documentElement.scrollTop;
    const workoutPlanSection = $("#workoutPlanSection");
    const sectionRect = workoutPlanSection ? workoutPlanSection.getBoundingClientRect() : null;
    const sectionTop = workoutPlanSection && sectionRect ? sectionRect.top + scrollPosition : null;
    const wasSectionVisible = !!sectionRect && sectionRect.bottom > 0 && sectionRect.top < window.innerHeight;
    
    // Показываем загрузку только если нет кеша
    if (force || !workoutPlanCache) {
      loading.style.display = "flex";
    }
    empty.style.display = "none";
    exercises.style.display = "none";
    
    try {
      const data = await apiGetWorkoutPlan(force);
      
      loading.style.display = "none";
      
      if (data && data.exercises && Array.isArray(data.exercises) && data.exercises.length > 0) {
        exercises.style.display = "block";
        empty.style.display = "none";
        renderWorkoutPlan(data);
        // Обновляем достижения дня после загрузки плана
        updateDailyAchievements(data);
      } else {
        exercises.style.display = "none";
        empty.style.display = "flex";
        // Обновляем достижения даже если плана нет (может быть, есть выполненные упражнения)
        if (data) {
          updateDailyAchievements(data);
        }
      }
      
      // Восстанавливаем позицию прокрутки после обновления (только для фоновых обновлений)
      if (!force && scrollPosition !== null && wasSectionVisible && workoutPlanSection) {
        // Используем requestAnimationFrame для плавного восстановления позиции
        requestAnimationFrame(() => {
          // Вычисляем новую позицию относительно секции workout plan
          if (sectionTop !== null) {
            const newRect = workoutPlanSection.getBoundingClientRect();
            const newSectionTop = newRect.top + window.pageYOffset;
            const offset = sectionTop - newSectionTop;
            if (Math.abs(offset) > 1) {
              window.scrollTo({
                top: scrollPosition + offset,
                behavior: 'instant' // Мгновенно, без анимации
              });
            }
          } else {
            // Fallback: просто восстанавливаем позицию
            window.scrollTo({
              top: scrollPosition,
              behavior: 'instant'
            });
          }
        });
      }
    } catch (e) {
      console.error("❌ Ошибка загрузки плана:", e);
      if (loading) loading.style.display = "none";
      if (exercises) exercises.style.display = "none";
      if (empty) empty.style.display = "flex";
      
      // Показываем информативное сообщение об ошибке
      const errorMsg = e.message || "Не удалось загрузить план тренировок";
      if (empty) {
        const emptyText = empty.querySelector('.workout-plan-empty-text');
        if (emptyText) {
          if (errorMsg.includes("NetworkError") || errorMsg.includes("Failed to fetch")) {
            emptyText.textContent = "Нет подключения к интернету";
          } else if (errorMsg.includes("500") || errorMsg.includes("502") || errorMsg.includes("503")) {
            emptyText.textContent = "Сервер временно недоступен";
          } else {
            emptyText.textContent = "Ошибка загрузки плана";
          }
        }
      }
      
      // Восстанавливаем позицию даже при ошибке
      if (!force && scrollPosition !== null && wasSectionVisible) {
        requestAnimationFrame(() => {
          window.scrollTo({
            top: scrollPosition,
            behavior: 'instant'
          });
        });
      }
    }
  }


  // Функции для новых настроек
  async function loadProfile() {
    console.log("📥 Загрузка профиля...");
    try {
      const profile = await apiGet("/api/profile");
      console.log("✅ Профиль получен:", profile);
      const heightEl = $("#profileHeight");
      const weightEl = $("#profileWeight");
      const ageEl = $("#profileAge");
      const sexEl = $("#profileSex");
      const goalEl = $("#profileGoal");
      const experienceEl = $("#profileExperience");
      const injuriesEl = $("#profileInjuries");
      const equipmentEl = $("#profileEquipment");
      
      console.log("🔍 Элементы профиля:", {
        height: !!heightEl,
        weight: !!weightEl,
        age: !!ageEl,
        sex: !!sexEl,
        goal: !!goalEl,
        experience: !!experienceEl,
        injuries: !!injuriesEl,
        equipment: !!equipmentEl
      });
      
      if (profile) {
        if (heightEl && profile.height_cm) heightEl.value = profile.height_cm;
        if (weightEl && profile.weight_kg) weightEl.value = profile.weight_kg;
        if (ageEl && profile.age) ageEl.value = profile.age;
        if (sexEl && profile.sex) sexEl.value = profile.sex;
        if (goalEl && profile.goal) goalEl.value = profile.goal;
        if (experienceEl && profile.experience) experienceEl.value = profile.experience;
        if (injuriesEl && profile.injuries) injuriesEl.value = profile.injuries;
        if (equipmentEl && profile.equipment) equipmentEl.value = profile.equipment;
        console.log("✅ Профиль загружен в форму");
      } else {
        console.log("⚠️ Профиль пуст");
      }
    } catch (e) {
      console.error("❌ Ошибка загрузки профиля:", e);
    }
  }
  
  async function saveProfile() {
    console.log("💾 Сохранение профиля...");
    const btn = $("#profileSaveBtn");
    if (!btn) {
      console.error("❌ Кнопка сохранения профиля не найдена!");
      return;
    }
    
    const height = parseInt($("#profileHeight")?.value) || null;
    const weight = parseFloat($("#profileWeight")?.value) || null;
    const age = parseInt($("#profileAge")?.value) || null;
    const sex = $("#profileSex")?.value || null;
    const goal = $("#profileGoal")?.value || null;
    const experience = $("#profileExperience")?.value || null;
    const injuries = $("#profileInjuries")?.value?.trim() || null;
    const equipment = $("#profileEquipment")?.value?.trim() || null;
    
    const profileData = {
      height_cm: height,
      weight_kg: weight,
      age: age,
      sex: sex,
      goal: goal,
      experience: experience,
      injuries: injuries,
      equipment: equipment
    };
    
    console.log("📤 Отправка данных профиля:", profileData);
    
    try {
      btn.disabled = true;
      btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2"/><path d="M12 6V12L16 14" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg> Сохранение...';
      
      const result = await apiPost("/api/profile", profileData);
      console.log("✅ Профиль сохранен:", result);
      
      btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M20 6L9 17L4 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg> Сохранено!';
      
      // Haptic feedback при успешном сохранении
      if (window.Telegram?.WebApp?.HapticFeedback) {
        try {
          window.Telegram.WebApp.HapticFeedback.notificationOccurred("success");
        } catch(e) {}
      }
      
      // Автоматически пересчитываем БЖУ после сохранения профиля
      if (height && weight && age) {
        setTimeout(() => {
          calculateBJU();
        }, 500);
      }
      
      // Показываем статус успеха
      showProfileStatus("Профиль успешно сохранен!", false);
      
      setTimeout(() => {
        btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M19 12H5M12 5L5 12L12 19" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg> Сохранить профиль';
        btn.disabled = false;
      }, 2000);
    } catch (e) {
      console.error("❌ Ошибка сохранения профиля:", e);
      btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M12 2L2 7L12 12L22 7L12 2Z" stroke="currentColor" stroke-width="2"/><path d="M2 17L12 22L22 17" stroke="currentColor" stroke-width="2"/><path d="M2 12L12 17L22 12" stroke="currentColor" stroke-width="2"/></svg> Ошибка';
      
      // Показываем статус ошибки
      const statusEl = $("#profileStatus");
      if (statusEl) {
        const textEl = statusEl.querySelector(".status-text");
        if (textEl) textEl.textContent = "Ошибка сохранения профиля";
        statusEl.classList.add("error");
        statusEl.style.display = "flex";
        setTimeout(() => {
          statusEl.style.display = "none";
          statusEl.classList.remove("error");
        }, 3000);
      }
      
      setTimeout(() => {
        btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M19 12H5M12 5L5 12L12 19" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg> Сохранить профиль';
        btn.disabled = false;
      }, 2000);
    }
  }
  
  async function loadReminders() {
    console.log("📥 Загрузка напоминаний...");
    try {
      const settings = await apiGet("/api/reminders/settings");
      console.log("✅ Настройки напоминаний получены:", settings);
      
      const toggle = $("#reminderToggle");
      if (!toggle) {
        console.warn("⚠️ Переключатель напоминаний не найден");
        return;
      }
      
      // Если настройки пусты, используем значения по умолчанию (выключено)
      if (!settings || Object.keys(settings).length === 0 || settings.enabled === undefined) {
        console.log("ℹ️ Настройки напоминаний пусты, используем значения по умолчанию (выключено)");
        toggle.classList.remove("active");
        return;
      }
      
      // Устанавливаем состояние переключателя
      if (settings?.enabled) {
        toggle.classList.add("active");
        console.log("✅ Напоминания включены");
      } else {
        toggle.classList.remove("active");
        console.log("✅ Напоминания выключены");
      }
    } catch (e) {
      console.error("❌ Ошибка загрузки напоминаний:", e);
      // Устанавливаем по умолчанию выключенным при ошибке
      const toggle = $("#reminderToggle");
      if (toggle) {
        toggle.classList.remove("active");
      }
    }
  }
  
  async function toggleReminders() {
    console.log("🔄 Переключение напоминаний...");
    const toggle = $("#reminderToggle");
    if (!toggle) {
      console.error("❌ Переключатель напоминаний не найден!");
      return;
    }
    
    const isActive = toggle.classList.contains("active");
    const newState = !isActive;
    
    console.log("📊 Текущее состояние:", isActive, "-> Новое состояние:", newState);
    
    try {
      // Оптимистичное обновление UI
      if (newState) {
        toggle.classList.add("active");
      } else {
        toggle.classList.remove("active");
      }
      
      const result = await apiPost("/api/reminders/settings", { enabled: newState });
      console.log("✅ Напоминания обновлены:", result);
      
      // Показываем статус успеха
      const statusEl = $("#remindersStatus");
      if (statusEl) {
        const textEl = statusEl.querySelector(".status-text");
        if (textEl) textEl.textContent = newState ? "Напоминания включены" : "Напоминания выключены";
        statusEl.classList.remove("error");
        statusEl.style.display = "flex";
        setTimeout(() => {
          statusEl.style.display = "none";
        }, 2000);
      }
    } catch (e) {
      console.error("❌ Ошибка переключения напоминаний:", e);
      // Откатываем изменение при ошибке
      if (newState) {
        toggle.classList.remove("active");
      } else {
        toggle.classList.add("active");
      }
      
      // Показываем ошибку
      const statusEl = $("#remindersStatus");
      if (statusEl) {
        const textEl = statusEl.querySelector(".status-text");
        if (textEl) textEl.textContent = "Ошибка сохранения";
        statusEl.classList.add("error");
        statusEl.style.display = "flex";
        setTimeout(() => {
          statusEl.style.display = "none";
          statusEl.classList.remove("error");
        }, 2000);
      }
    }
  }
  
  async function exportData() {
    console.log("📥 Экспорт данных...");
    const btn = $("#exportDataBtn");
    if (!btn) {
      console.error("❌ Кнопка экспорта данных не найдена!");
      return;
    }
    
    try {
      btn.disabled = true;
      btn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" style="animation: spin 1s linear infinite;"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" stroke-dasharray="31.416" stroke-dashoffset="31.416"><animate attributeName="stroke-dashoffset" values="31.416;0" dur="1s" repeatCount="indefinite"/></circle></svg> Экспорт...';
      
      const data = await apiGet("/api/export/data");
      console.log("✅ Данные получены:", data);
      
      // Создаем JSON файл
      const jsonStr = JSON.stringify(data, null, 2);
      const blob = new Blob([jsonStr], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `workout-data-${new Date().toISOString().split('T')[0]}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      
      btn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M5 13L9 17L19 7" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg> Экспортировано!';
      btn.style.background = "linear-gradient(135deg, rgba(74,222,128,0.95) 0%, rgba(74,222,128,0.75) 100%)";
      
      setTimeout(() => {
        btn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M19 12V19H5V12H3V19C3 20.1 3.9 21 5 21H19C20.1 21 21 20.1 21 19V12H19ZM13 12.67L15.59 10.09L17 11.5L12 16.5L7 11.5L8.41 10.09L11 12.67V3H13V12.67Z" fill="currentColor"/></svg> Экспортировать данные';
        btn.style.background = "";
        btn.disabled = false;
      }, 2000);
    } catch (e) {
      console.error("❌ Ошибка экспорта данных:", e);
      btn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M12 2C6.48 2 2 6.48 2 12C2 17.52 6.48 22 12 22C17.52 22 22 17.52 22 12C22 6.48 17.52 2 12 2ZM13 17H11V15H13V17ZM13 13H11V7H13V13Z" fill="currentColor"/></svg> Ошибка экспорта';
      btn.style.background = "linear-gradient(135deg, rgba(248,113,113,0.95) 0%, rgba(248,113,113,0.75) 100%)";
      setTimeout(() => {
        btn.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M19 12V19H5V12H3V19C3 20.1 3.9 21 5 21H19C20.1 21 21 20.1 21 19V12H19ZM13 12.67L15.59 10.09L17 11.5L12 16.5L7 11.5L8.41 10.09L11 12.67V3H13V12.67Z" fill="currentColor"/></svg> Экспортировать данные';
        btn.style.background = "";
        btn.disabled = false;
      }, 2000);
    }
  }
  
  // Функция для настройки обработчиков событий настроек
  function setupSettingsHandlers() {
    console.log("🔧 Настройка обработчиков событий для настроек...");
    
    const profileSaveBtn = $("#profileSaveBtn");
    if (profileSaveBtn) {
      console.log("✅ Кнопка сохранения профиля найдена");
      // Удаляем все старые обработчики
      const newBtn = profileSaveBtn.cloneNode(true);
      profileSaveBtn.parentNode.replaceChild(newBtn, profileSaveBtn);
      newBtn.addEventListener("click", (e) => {
        console.log("🖱️ Клик по кнопке сохранения профиля");
        e.preventDefault();
        saveProfile();
      });
      console.log("✅ Обработчик кнопки сохранения профиля добавлен");
    } else {
      console.error("❌ Кнопка сохранения профиля не найдена! ID: profileSaveBtn");
    }
    
    const reminderToggle = $("#reminderToggle");
    if (reminderToggle) {
      console.log("✅ Переключатель напоминаний найден");
      const newToggle = reminderToggle.cloneNode(true);
      reminderToggle.parentNode.replaceChild(newToggle, reminderToggle);
      newToggle.addEventListener("click", (e) => {
        console.log("🖱️ Клик по переключателю напоминаний");
        e.preventDefault();
        toggleReminders();
      });
      console.log("✅ Обработчик переключателя напоминаний добавлен");
    } else {
      console.error("❌ Переключатель напоминаний не найден! ID: reminderToggle");
    }
    
    const exportDataBtn = $("#exportDataBtn");
    if (exportDataBtn) {
      console.log("✅ Кнопка экспорта данных найдена");
      const newExportBtn = exportDataBtn.cloneNode(true);
      exportDataBtn.parentNode.replaceChild(newExportBtn, exportDataBtn);
      newExportBtn.addEventListener("click", (e) => {
        console.log("🖱️ Клик по кнопке экспорта данных");
        e.preventDefault();
        exportData();
      });
      console.log("✅ Обработчик кнопки экспорта данных добавлен");
    } else {
      console.warn("⚠️ Кнопка экспорта данных не найдена! ID: exportDataBtn");
    }
    
    // Обработчики для недельной цели
    const weeklyGoalMinus = $("#weeklyGoalMinus");
    const weeklyGoalPlus = $("#weeklyGoalPlus");
    const weeklyGoalInput = $("#weeklyGoalInput");
    const saveGoalsBtn = $("#saveGoalsBtn");
    
    if (weeklyGoalMinus) {
      weeklyGoalMinus.addEventListener("click", (e) => {
        e.preventDefault();
        if (weeklyGoalInput) {
          const current = parseInt(weeklyGoalInput.value) || 3;
          const newValue = Math.max(1, current - 1);
          weeklyGoalInput.value = newValue;
          const goalValueEl = $("#weeklyGoalValue");
          if (goalValueEl) goalValueEl.textContent = newValue;
        }
      });
    }
    
    if (weeklyGoalPlus) {
      weeklyGoalPlus.addEventListener("click", (e) => {
        e.preventDefault();
        if (weeklyGoalInput) {
          const current = parseInt(weeklyGoalInput.value) || 3;
          const newValue = Math.min(14, current + 1);
          weeklyGoalInput.value = newValue;
          const goalValueEl = $("#weeklyGoalValue");
          if (goalValueEl) goalValueEl.textContent = newValue;
        }
      });
    }
    
    if (weeklyGoalInput) {
      weeklyGoalInput.addEventListener("input", (e) => {
        const value = parseInt(e.target.value) || 3;
        const clamped = Math.max(1, Math.min(14, value));
        if (clamped !== value) {
          e.target.value = clamped;
        }
        const goalValueEl = $("#weeklyGoalValue");
        if (goalValueEl) goalValueEl.textContent = clamped;
      });
    }
    
    if (saveGoalsBtn) {
      saveGoalsBtn.addEventListener("click", (e) => {
        e.preventDefault();
        saveWeeklyGoal();
      });
    }
  }
  
  // Инициализация с защитой от ошибок
  try {
    init();
  } catch(e) {
    console.error("Ошибка при инициализации:", e);
    // Показываем страницу даже при ошибке
    try {
      showPage("today");
    } catch(e2) {
      console.error("Критическая ошибка:", e2);
    }
  }
  
  // Загружаем данные только для активной страницы после инициализации
  // Избегаем множественных одновременных запросов
  // Используем requestAnimationFrame для плавной загрузки
  requestAnimationFrame(() => {
    try {
      console.log("🚀 Инициализация завершена, текущая страница:", state.currentPage);
      if (state.currentPage === "today") {
        loadWorkoutPlan();
      } else if (state.currentPage === "settings") {
        console.log("⚙️ Загрузка настроек при инициализации...");
        Promise.all([
          loadNotifications(),
        loadProfile(),
        loadReminders()
      ]).then(() => {
        console.log("✅ Все настройки загружены при инициализации");
      }).catch(e => {
        console.error("❌ Ошибка загрузки настроек при инициализации:", e);
      });
    }
    // Статистика загружается только при переходе на страницу "stats"
    } catch(e) {
      console.error("Ошибка при загрузке данных:", e);
    }
  });
  
  // Калькулятор БЖУ
  function calculateBJU() {
    try {
      // Получаем данные сначала из полей калькулятора, если их нет - из профиля
      const calcHeightEl = $("#calcHeight");
      const calcWeightEl = $("#calcWeight");
      const calcAgeEl = $("#calcAge");
      const calcSexEl = $("#calcSex");
      
      const profileHeightEl = $("#profileHeight");
      const profileWeightEl = $("#profileWeight");
      const profileAgeEl = $("#profileAge");
      const profileSexEl = $("#profileSex");
      
      // Приоритет: поля калькулятора > поля профиля
      const height = parseFloat(calcHeightEl?.value || profileHeightEl?.value) || 0;
      const weight = parseFloat(calcWeightEl?.value || profileWeightEl?.value) || 0;
      const age = parseInt(calcAgeEl?.value || profileAgeEl?.value) || 0;
      const sex = (calcSexEl?.value || profileSexEl?.value || 'male');
      const activity = parseFloat($("#bjuActivity")?.value) || 1.375;
      const goal = $("#bjuGoal")?.value || 'maintain';
      
      // Проверяем наличие необходимых данных
      if (!height || !weight || !age || height <= 0 || weight <= 0 || age <= 0) {
        alert("Заполни параметры: рост, вес и возраст для расчета БЖУ");
        // Фокусируемся на первом пустом поле
        if (!height && calcHeightEl) calcHeightEl.focus();
        else if (!weight && calcWeightEl) calcWeightEl.focus();
        else if (!age && calcAgeEl) calcAgeEl.focus();
        return;
      }
    
    // Рассчитываем BMR по формуле Миффлина-Сан Жеора
    let bmr;
    if (sex === 'male') {
      bmr = 10 * weight + 6.25 * height - 5 * age + 5;
    } else {
      bmr = 10 * weight + 6.25 * height - 5 * age - 161;
    }
    
    // Рассчитываем TDEE (общий расход энергии)
    const tdee = bmr * activity;
    
    // Рассчитываем целевые калории в зависимости от цели
    let targetCalories = tdee;
    if (goal === 'lose') {
      targetCalories = tdee - 500; // Дефицит 500 ккал для сброса веса
    } else if (goal === 'gain') {
      targetCalories = tdee + 500; // Профицит 500 ккал для набора веса
    }
    
    // Рассчитываем БЖУ с учетом цели и активности
    // Белки: 1.6-2.2 г на кг веса (для активных людей и набора веса - больше)
    let proteinMultiplier = 2.0; // Базовое значение
    if (goal === 'gain') {
      proteinMultiplier = 2.2; // Больше белков при наборе массы
    } else if (goal === 'lose') {
      proteinMultiplier = 2.0; // Высокий белок при сбросе для сохранения мышц
    }
    if (activity >= 1.725) {
      proteinMultiplier += 0.1; // Больше белков при высокой активности
    }
    
    const proteinGrams = Math.round(weight * proteinMultiplier);
    const proteinCalories = proteinGrams * 4; // 1г белка = 4 ккал
    
    // Жиры: 0.8-1.2 г на кг веса (оптимально ~1г, это ~25-30% от калорий)
    // При сбросе веса немного уменьшаем жиры, при наборе - нормально
    let fatMultiplier = 1.0;
    if (goal === 'lose') {
      fatMultiplier = 0.9; // Немного меньше жиров при сбросе
    } else if (goal === 'gain') {
      fatMultiplier = 1.1; // Немного больше жиров при наборе
    }
    
    const fatGrams = Math.round(weight * fatMultiplier);
    const fatCalories = fatGrams * 9; // 1г жира = 9 ккал
    
    // Углеводы: остаток калорий (основной источник энергии)
    const carbsCalories = Math.max(0, targetCalories - proteinCalories - fatCalories);
    const carbsGrams = Math.round(carbsCalories / 4); // 1г углеводов = 4 ккал
    
    // Проценты от общей калорийности
    const proteinPercent = Math.round((proteinCalories / targetCalories) * 100);
    const fatPercent = Math.round((fatCalories / targetCalories) * 100);
    const carbsPercent = Math.round((carbsCalories / targetCalories) * 100);
    
    // Отображаем результаты
    const caloriesEl = $("#bjuCalories");
    const bmrEl = $("#bjuBMR");
    const tdeeEl = $("#bjuTDEE");
    const proteinEl = $("#bjuProtein");
    const proteinPercentEl = $("#bjuProteinPercent");
    const fatEl = $("#bjuFat");
    const fatPercentEl = $("#bjuFatPercent");
    const carbsEl = $("#bjuCarbs");
    const carbsPercentEl = $("#bjuCarbsPercent");
    
    if (caloriesEl) caloriesEl.textContent = Math.round(targetCalories);
    const caloriesCard = $("#bjuCaloriesCard");
    const caloriesHint = $("#bjuCaloriesHint");
    if (caloriesCard && caloriesHint) {
      caloriesCard.classList.remove("is-empty");
      caloriesHint.style.display = "none";
    }
    if (bmrEl) bmrEl.textContent = Math.round(bmr) + " ккал";
    if (tdeeEl) tdeeEl.textContent = Math.round(tdee) + " ккал";
    
    if (proteinEl) proteinEl.textContent = proteinGrams;
    if (proteinPercentEl) proteinPercentEl.textContent = proteinPercent + "%";
    
    if (fatEl) fatEl.textContent = fatGrams;
    if (fatPercentEl) fatPercentEl.textContent = fatPercent + "%";
    
    if (carbsEl) carbsEl.textContent = carbsGrams;
    if (carbsPercentEl) carbsPercentEl.textContent = carbsPercent + "%";
    
    // Показываем результаты с анимацией
    const resultsEl = $("#bjuResults");
    if (resultsEl) {
      resultsEl.style.display = "block";
      resultsEl.style.opacity = "0";
      requestAnimationFrame(() => {
        resultsEl.style.transition = "opacity 0.4s ease";
        resultsEl.style.opacity = "1";
      });
      
      // Прокручиваем к результатам
      setTimeout(() => {
        resultsEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }, 100);
    }
    
      // Haptic feedback
      if (window.Telegram?.WebApp?.HapticFeedback) {
        try {
          window.Telegram.WebApp.HapticFeedback.impactOccurred("medium");
        } catch(e) {}
      }
    } catch (e) {
      console.error("Ошибка расчета БЖУ:", e);
      alert("Произошла ошибка при расчете БЖУ. Проверьте введенные данные.");
    }
  }
  
  // === НЕДЕЛЬНАЯ ЦЕЛЬ ТРЕНИРОВОК ===
  async function updateWeeklyGoalProgress() {
    try {
      // Пробуем загрузить цели, если API недоступен - используем localStorage или значение по умолчанию
      let weeklyGoal = 3;
      try {
        const goals = await apiGet("/api/goals");
        weeklyGoal = goals?.weekly_workouts || 3;
        // Сохраняем в localStorage для резервного использования
        if (weeklyGoal) localStorage.setItem("weekly_workout_goal", weeklyGoal.toString());
      } catch (e) {
        // Тихо обрабатываем ошибку - используем localStorage как fallback
        // Не логируем ошибку, так как это нормальное поведение при отсутствии API
        const stored = localStorage.getItem("weekly_workout_goal");
        if (stored) {
          weeklyGoal = parseInt(stored) || 3;
        }
      }
      
      const goalValueEl = $("#weeklyGoalValue");
      const goalInputEl = $("#weeklyGoalInput");
      
      if (goalValueEl) goalValueEl.textContent = weeklyGoal;
      if (goalInputEl) goalInputEl.value = weeklyGoal;
      
      // Получаем статистику для расчета прогресса
      try {
        const stats = await apiGetStats(7);
        if (stats && stats.chart_data) {
          const now = new Date();
          const weekStart = new Date(now);
          weekStart.setDate(now.getDate() - now.getDay() + 1); // Понедельник
          weekStart.setHours(0, 0, 0, 0);
          
          let weekWorkouts = 0;
          stats.chart_data.forEach(day => {
            try {
              const dayDate = new Date(day.date);
              if (dayDate >= weekStart && day.workouts > 0) {
                weekWorkouts++;
              }
            } catch (e) {}
          });
          
          const progressEl = $("#weeklyGoalProgress");
          const progressFillEl = $("#weeklyGoalProgressFill");
          const progressTextEl = $("#weeklyGoalProgressText");
          
          if (progressEl && progressFillEl && progressTextEl) {
            const percentage = Math.min(100, (weekWorkouts / weeklyGoal) * 100);
            progressFillEl.style.width = percentage + '%';
            progressTextEl.textContent = `${weekWorkouts}/${weeklyGoal}`;
            progressEl.style.display = 'flex';
            
            if (percentage >= 100) {
              progressFillEl.classList.add('goal-reached');
            } else {
              progressFillEl.classList.remove('goal-reached');
            }
          }
        }
      } catch (e) {
        console.log("Не удалось загрузить статистику для недельной цели:", e);
      }
    } catch (e) {
      console.error("Ошибка обновления недельной цели:", e);
    }
  }
  
  async function saveWeeklyGoal() {
    try {
      const goalInputEl = $("#weeklyGoalInput");
      if (!goalInputEl) return;
      
      const goal = parseInt(goalInputEl.value);
      if (isNaN(goal) || goal < 1 || goal > 14) {
        alert("Цель должна быть от 1 до 14 тренировок в неделю");
        // Восстанавливаем предыдущее значение
        const stored = localStorage.getItem("weekly_workout_goal");
        if (stored) {
          const prevGoal = parseInt(stored) || 3;
          goalInputEl.value = prevGoal;
          const goalValueEl = $("#weeklyGoalValue");
          if (goalValueEl) goalValueEl.textContent = prevGoal;
        }
        return;
      }
      
      // Пробуем сохранить через API, если недоступен - сохраняем в localStorage
      try {
        await apiPost("/api/goals", { weekly_workouts: goal });
      } catch (e) {
        console.log("API goals недоступен, сохраняем в localStorage:", e);
        localStorage.setItem("weekly_workout_goal", goal.toString());
      }
      
      // Обновляем отображение
      const goalValueEl = $("#weeklyGoalValue");
      if (goalValueEl) goalValueEl.textContent = goal;
      
      // Сохраняем в localStorage для резервного использования
      localStorage.setItem("weekly_workout_goal", goal.toString());
      
      // Обновляем прогресс
      await updateWeeklyGoalProgress();
      
      // Haptic feedback
      if (window.Telegram?.WebApp?.HapticFeedback) {
        try {
          window.Telegram.WebApp.HapticFeedback.notificationOccurred("success");
        } catch(e) {}
      }
    } catch (e) {
      console.error("Ошибка сохранения недельной цели:", e);
      alert("Не удалось сохранить цель");
    }
  }
  
  function syncSexTabs(value) {
    const tabs = document.querySelectorAll(".bju-tab");
    if (!tabs.length) return;
    tabs.forEach((tab) => {
      const isActive = tab.dataset.value === value;
      tab.classList.toggle("active", isActive);
      tab.setAttribute("aria-selected", isActive ? "true" : "false");
    });
    const input = $("#calcSex");
    if (input) input.value = value;
  }

  function syncWeightControls(value) {
    const normalized = value === "" || value === null ? "" : String(value);
    const range = $("#calcWeightRange");
    const input = $("#calcWeight");
    if (range && range.value !== normalized) range.value = normalized;
    if (input && input.value !== normalized) input.value = normalized;
  }

  function syncHeightControls(value) {
    const normalized = value === "" || value === null ? "" : String(value);
    const range = $("#calcHeightRange");
    const input = $("#calcHeight");
    if (range && range.value !== normalized) range.value = normalized;
    if (input && input.value !== normalized) input.value = normalized;
  }

  function getStepPrecision(step) {
    const stepString = String(step);
    const decimalIndex = stepString.indexOf(".");
    return decimalIndex === -1 ? 0 : stepString.length - decimalIndex - 1;
  }

  // Функция для настройки обработчиков калькулятора
  function setupCalculatorHandlers() {
    console.log("🧮 Настройка обработчиков событий для калькулятора...");
    
    // Обработчик кнопки расчета БЖУ
    const bjuCalculateBtn = $("#bjuCalculateBtn");
    if (bjuCalculateBtn) {
      console.log("✅ Кнопка расчета БЖУ найдена");
      const newBjuBtn = bjuCalculateBtn.cloneNode(true);
      bjuCalculateBtn.parentNode.replaceChild(newBjuBtn, bjuCalculateBtn);
      newBjuBtn.addEventListener("click", (e) => {
        console.log("🖱️ Клик по кнопке расчета БЖУ");
        e.preventDefault();
        calculateBJU();
      });
      console.log("✅ Обработчик кнопки расчета БЖУ добавлен");
    } else {
      console.warn("⚠️ Кнопка расчета БЖУ не найдена! ID: bjuCalculateBtn");
    }

    const sexTabs = document.querySelectorAll(".bju-tab");
    if (sexTabs.length) {
      sexTabs.forEach((tab) => {
        tab.addEventListener("click", () => {
          syncSexTabs(tab.dataset.value);
        });
      });
    }

    const weightRange = $("#calcWeightRange");
    const weightInput = $("#calcWeight");
    if (weightRange) {
      weightRange.addEventListener("input", () => {
        syncWeightControls(weightRange.value);
      });
    }
    if (weightInput) {
      weightInput.addEventListener("input", () => {
        syncWeightControls(weightInput.value);
      });
    }

    const heightRange = $("#calcHeightRange");
    const heightInput = $("#calcHeight");
    if (heightRange) {
      heightRange.addEventListener("input", () => {
        syncHeightControls(heightRange.value);
      });
    }
    if (heightInput) {
      heightInput.addEventListener("input", () => {
        syncHeightControls(heightInput.value);
      });
    }

    const stepperButtons = document.querySelectorAll(".bju-stepper");
    if (stepperButtons.length) {
      stepperButtons.forEach((button) => {
        button.addEventListener("click", (event) => {
          event.preventDefault();
          const targetId = button.dataset.target;
          const delta = parseFloat(button.dataset.step || "0");
          const input = targetId ? document.getElementById(targetId) : null;
          if (!input || !Number.isFinite(delta)) return;

          const min = input.min !== "" ? parseFloat(input.min) : -Infinity;
          const max = input.max !== "" ? parseFloat(input.max) : Infinity;
          const step = input.step !== "" ? parseFloat(input.step) : 1;
          const precision = getStepPrecision(step);

          let base = parseFloat(input.value);
          if (!Number.isFinite(base)) {
            const placeholder = parseFloat(input.placeholder);
            if (Number.isFinite(placeholder)) base = placeholder;
            else if (Number.isFinite(min)) base = min;
            else base = 0;
          }

          let next = clamp(base + delta, min, max);
          next = precision > 0 ? Number(next.toFixed(precision)) : Math.round(next);
          input.value = String(next);

          if (targetId === "calcHeight") syncHeightControls(input.value);
          else if (targetId === "calcWeight") syncWeightControls(input.value);
        });
      });
    }

    if (weightInput?.value || weightRange?.value) {
      syncWeightControls(weightInput?.value || weightRange?.value);
    }
    if (heightInput?.value || heightRange?.value) {
      syncHeightControls(heightInput?.value || heightRange?.value);
    }
    const calcSexEl = $("#calcSex");
    if (calcSexEl?.value) {
      syncSexTabs(calcSexEl.value);
    }
  }
  
  // Функция для настройки обработчика кнопки "Начать записывать тренировки"
  function setupEmptyActionHandler() {
    const emptyActionBtn = $("#emptyActionBtn");
    if (emptyActionBtn) {
      // Удаляем старый обработчик если есть
      const newBtn = emptyActionBtn.cloneNode(true);
      emptyActionBtn.parentNode.replaceChild(newBtn, emptyActionBtn);
      
      // Обработчик клика
      const handleClick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        
        // Haptic feedback
        if (window.Telegram?.WebApp?.HapticFeedback) {
          try {
            window.Telegram.WebApp.HapticFeedback.impactOccurred("medium");
          } catch(e) {}
        }
        
        // Переключаемся на страницу "План"
        console.log("📝 Переключение на страницу 'План' для записи тренировок");
        showPage("plan");
      };
      
      // Обработчик клавиатуры для доступности
      const handleKeyPress = (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          handleClick(e);
        }
      };
      
      newBtn.addEventListener("click", handleClick);
      newBtn.addEventListener("keydown", handleKeyPress);
      
      console.log("✅ Обработчик кнопки 'Начать записывать тренировки' добавлен");
    }
  }
  
  // ПОЛНОЕ УНИЧТОЖЕНИЕ БЛОКА БЫСТРЫХ ШАБЛОНОВ - УДАЛЯЕМ НАВСЕГДА
  function destroyQuickTemplatesForever() {
    const quickTemplates = document.querySelectorAll('.quick-templates, #quickTemplates, [class*="quick-template"], [id*="quickTemplate"], [class*="template"]');
    quickTemplates.forEach(el => {
      try {
        el.remove();
      } catch(e) {
        if (el.parentNode) el.parentNode.removeChild(el);
      }
      el.style.cssText = 'display: none !important; visibility: hidden !important; opacity: 0 !important; height: 0 !important; width: 0 !important; position: absolute !important; left: -99999px !important; top: -99999px !important; pointer-events: none !important; z-index: -99999 !important;';
      el.setAttribute('style', 'display: none !important;');
    });
  }
  // Уничтожаем блок быстрых шаблонов при загрузке
  if (document.body) {
    destroyQuickTemplatesForever();
    const obs = new MutationObserver(destroyQuickTemplatesForever);
    obs.observe(document.body, {childList: true, subtree: true, attributes: true});
    // Настраиваем обработчик кнопки empty-action
    setupEmptyActionHandler();
  } else {
    // Если body еще не загружен, ждем DOMContentLoaded
    document.addEventListener('DOMContentLoaded', () => {
      destroyQuickTemplatesForever();
      if (document.body) {
        const obs = new MutationObserver(destroyQuickTemplatesForever);
        obs.observe(document.body, {childList: true, subtree: true, attributes: true});
      }
      // Настраиваем обработчик кнопки empty-action
      setupEmptyActionHandler();
    });
  }
  // Переопределение showPage удалено - теперь destroyQuickTemplatesForever() вызывается внутри showPage
  
})();
