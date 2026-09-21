/* ==========================================================================
   Scolect API connector
   Wires every panel (Dashboard, Applications, Alerts & Limits, Usage
   Analytics, Focus Mode, AI Predictions, Settings) to the Flask backend,
   including populating every Chart.js chart with live data instead of the
   static mock series baked into the page.
   Safe to remove: if any fetch fails, the original mock content stays put.
========================================================================== */
(function () {
  const $ = (id) => document.getElementById(id);

  async function getJSON(url, options) {
    const res = await fetch(url, options);
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.error || `${url} -> ${res.status}`);
    }
    return res.json();
  }

  function fmtHM(totalMinutes) {
    const h = Math.floor(totalMinutes / 60);
    const m = Math.round(totalMinutes % 60);
    return h ? `${h}h ${String(m).padStart(2, '0')}m` : `${m}m`;
  }

  function updateChangeBadge(id, value, lowerIsBetter = false) {
    const badge = $(id);
    if (!badge) return;
    const change = Number(value || 0);
    const sign = change >= 0 ? '+' : '';
    badge.textContent = `${sign}${change}% vs yesterday`;
    const positive = lowerIsBetter ? change <= 0 : change >= 0;
    badge.className = `text-[11px] font-semibold px-2 py-1 rounded-full ${
      positive ? 'bg-mint-500/10 text-mint-500' : 'bg-coral-500/10 text-coral-500'
    }`;
  }

  /* ============================================================
     DASHBOARD
  ============================================================ */
  async function loadDashboard() {
    const data = await getJSON('/api/dashboard/today');

    if ($('stat-total-time')) $('stat-total-time').textContent = data.total_screen_time.display;
    if ($('stat-productive-time')) $('stat-productive-time').textContent = data.productive_time.display;
    if ($('stat-score')) $('stat-score').textContent = data.productivity_score;
    if ($('stat-focus-time')) $('stat-focus-time').textContent = data.focus_sessions_today.display;
    updateChangeBadge('stat-total-change', data.total_screen_time.pct_change_vs_yesterday, true);
    updateChangeBadge('stat-productive-change', data.productive_time.pct_change_vs_yesterday);
    if ($('stat-score-label')) {
      const score = Number(data.productivity_score || 0);
      $('stat-score-label').textContent = score >= 70 ? 'Excellent' : score >= 50 ? 'Good' : 'Needs attention';
    }
    if ($('stat-focus-count')) {
      $('stat-focus-count').textContent = `${data.focus_sessions_today.count} sessions`;
    }

    const mostUsed = $('most-used-list');
    if (mostUsed && data.most_used_applications.length) {
      const max = Math.max(...data.most_used_applications.map((a) => a.minutes), 1);
      mostUsed.innerHTML = data.most_used_applications
        .map(
          (a) => `
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 rounded-lg flex items-center justify-center text-[15px]" style="background:${a.color}22">●</div>
          <div class="flex-1 min-w-0">
            <div class="flex justify-between text-[12.5px] font-semibold text-slate-700 dark:text-slate-200">
              <span class="truncate">${a.name}</span><span class="font-mono text-slate-400">${a.display}</span>
            </div>
            <div class="h-1.5 bg-slate-100 dark:bg-white/5 rounded-full mt-1.5 overflow-hidden">
              <div class="h-full rounded-full" style="width:${Math.round((a.minutes / max) * 100)}%; background:${a.color}"></div>
            </div>
          </div>
        </div>`
        )
        .join('');
    }

    if (window.weeklyTrendChart && data.weekly_trend.length) {
      window.weeklyTrendChart.data.labels = data.weekly_trend.map((d) => d.label);
      window.weeklyTrendChart.data.datasets[0].data = data.weekly_trend.map((d) => d.productive_hours);
      window.weeklyTrendChart.data.datasets[1].data = data.weekly_trend.map((d) => d.leisure_hours);
      window.weeklyTrendChart.update();
    }

    if (window.categoryDonutChart && data.category_breakdown.length) {
      const palette = ['#4a6cf7', '#ef4444', '#1fb894', '#f59e0b', '#f65e4a', '#818cf8', '#22c55e'];
      window.categoryDonutChart.data.labels = data.category_breakdown.map((c) => c.category);
      window.categoryDonutChart.data.datasets[0].data = data.category_breakdown.map((c) => c.minutes);
      window.categoryDonutChart.data.datasets[0].backgroundColor = data.category_breakdown.map(
        (_, i) => palette[i % palette.length]
      );
      window.categoryDonutChart.update();
    }

    if (window.appBarsChart && data.app_usage_bars.length) {
      window.appBarsChart.data.labels = data.app_usage_bars.map((a) => a.name);
      window.appBarsChart.data.datasets[0].data = data.app_usage_bars.map((a) => Math.round(a.minutes));
      window.appBarsChart.data.datasets[0].backgroundColor = data.app_usage_bars.map((a) => a.color);
      window.appBarsChart.update();
    }
  }

  /* ============================================================
     APPLICATIONS
  ============================================================ */
  let appsFilterTimeout = null;

  function currentAppsFilters() {
    const params = new URLSearchParams();
    const q = $('apps-search-input') ? $('apps-search-input').value.trim() : '';
    const category = $('apps-category-filter') ? $('apps-category-filter').value : '';
    const status = $('apps-status-filter') ? $('apps-status-filter').value : '';
    if (q) params.set('q', q);
    if (category) params.set('category', category);
    if (status) params.set('status', status);
    return params.toString();
  }

  async function loadApplications() {
    const qs = currentAppsFilters();
    const apps = await getJSON(`/api/applications${qs ? '?' + qs : ''}`);
    const body = $('apps-table-body');
    if (!body) return;

    if (!apps.length) {
      body.innerHTML = `<tr><td colspan="7" class="py-8 text-center text-slate-400 text-[13px]">No applications match these filters.</td></tr>`;
      return;
    }

    body.innerHTML = apps
      .map(
        (a) => `
      <tr class="app-row border-b border-slate-50 dark:border-white/5 last:border-0">
        <td class="py-3.5 px-5">
          <div class="flex items-center gap-3">
            <div class="w-8 h-8 rounded-lg" style="background:${a.color}22"></div>
            <span class="font-semibold text-slate-700 dark:text-slate-200">${a.name}</span>
          </div>
        </td>
        <td class="py-3.5 px-5"><span class="text-[11.5px] font-semibold px-2 py-1 rounded-full" style="background:${a.color}18;color:${a.color}">${a.category}</span></td>
        <td class="py-3.5 px-5 font-mono text-slate-600 dark:text-slate-300">${a.today_display}</td>
        <td class="py-3.5 px-5 font-mono text-slate-400">${a.weekly_avg_display}</td>
        <td class="py-3.5 px-5 text-slate-500 dark:text-slate-400">${a.limit_display}</td>
        <td class="py-3.5 px-5">${miniToggle(a.id, 'is_productive', a.is_productive)}</td>
        <td class="py-3.5 px-5">${miniToggle(a.id, 'is_visible', a.is_visible)}</td>
      </tr>`
      )
      .join('');

    body.querySelectorAll('.api-toggle').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const checked = btn.dataset.checked === 'true';
        const field = btn.dataset.field;
        const appId = btn.dataset.id;
        await getJSON(`/api/applications/${appId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ [field]: !checked }),
        });
        loadApplications();
        loadDashboard().catch(() => {});
      });
    });
  }

  function miniToggle(id, field, checked) {
    return `<button data-id="${id}" data-field="${field}" data-checked="${checked}"
      class="api-toggle w-9 h-5 rounded-full ${checked ? 'bg-brand-600' : 'bg-slate-200 dark:bg-white/10'} relative">
      <span class="absolute top-0.5 ${checked ? 'translate-x-[18px]' : 'translate-x-0.5'} w-4 h-4 rounded-full bg-white shadow"></span>
    </button>`;
  }

  function wireApplicationFilters() {
    ['apps-category-filter', 'apps-status-filter'].forEach((id) => {
      if ($(id)) $(id).addEventListener('change', () => loadApplications().catch(console.warn));
    });
    if ($('apps-search-input')) {
      $('apps-search-input').addEventListener('input', () => {
        clearTimeout(appsFilterTimeout);
        appsFilterTimeout = setTimeout(() => loadApplications().catch(console.warn), 300);
      });
    }
  }

  /* ============================================================
     ALERTS & LIMITS
  ============================================================ */
  function apiToggleRow(label, sub, field, checked) {
    return `
    <div class="flex items-center justify-between">
      <div>
        <p class="text-[13px] font-semibold text-slate-700 dark:text-slate-200">${label}</p>
        ${sub ? `<p class="text-[11.5px] text-slate-400">${sub}</p>` : ''}
      </div>
      <button data-field="${field}" data-checked="${checked}"
        class="notif-toggle w-11 h-6 rounded-full ${checked ? 'bg-brand-600' : 'bg-slate-200 dark:bg-white/10'} relative">
        <span class="absolute top-0.5 ${checked ? 'translate-x-[22px]' : 'translate-x-0.5'} w-5 h-5 rounded-full bg-white shadow"></span>
      </button>
    </div>`;
  }

  async function loadAlerts() {
    const data = await getJSON('/api/alerts');

    if ($('alert-used-display')) $('alert-used-display').textContent = data.used_today_display;
    if ($('alert-limit-display')) $('alert-limit-display').textContent = data.global_limit_display;
    if ($('alert-pct-badge')) $('alert-pct-badge').textContent = `${data.pct_used}% used`;
    if ($('alert-progress-bar')) $('alert-progress-bar').style.width = `${Math.min(data.pct_used, 100)}%`;
    if ($('alert-limit-slider')) $('alert-limit-slider').value = Math.round(data.global_limit_minutes / 60);

    const notifEl = $('notif-toggles');
    if (notifEl) {
      notifEl.innerHTML =
        apiToggleRow('Pop-up Alerts', 'Show in-app when limit is near', 'notif_popup', data.notifications.popup) +
        apiToggleRow('System Notifications', 'OS-level notifications', 'notif_system', data.notifications.system) +
        apiToggleRow('Sound Alerts', 'Play a sound when limit is hit', 'notif_sound', data.notifications.sound);

      notifEl.querySelectorAll('.notif-toggle').forEach((btn) => {
        btn.addEventListener('click', async () => {
          const checked = btn.dataset.checked === 'true';
          await getJSON('/api/alerts/notifications', {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ [btn.dataset.field]: !checked }),
          });
          loadAlerts();
        });
      });
    }

    const limitsEl = $('app-limits-list');
    if (limitsEl) {
      if (!data.per_app_limits.length) {
        limitsEl.innerHTML = `<p class="px-5 py-6 text-center text-[13px] text-slate-400">No per-app limits set yet.</p>`;
      } else {
        const statusColor = { 'On track': 'mint-500', 'At risk': 'amber-500', Exceeded: 'coral-500' };
        limitsEl.innerHTML = data.per_app_limits
          .map(
            (l) => `
          <div class="flex items-center justify-between px-5 py-4">
            <div class="flex items-center gap-3">
              <div class="w-9 h-9 rounded-lg" style="background:${l.color}22"></div>
              <div>
                <p class="text-[13.5px] font-semibold text-slate-700 dark:text-slate-200">${l.name}</p>
                <p class="text-[11.5px] text-slate-400">Limit: ${l.limit_display} · Used today: ${l.used_display}</p>
              </div>
            </div>
            <div class="flex items-center gap-3">
              <span class="text-[11px] font-semibold px-2.5 py-1 rounded-full bg-${statusColor[l.status] || 'slate-400'}/10 text-${statusColor[l.status] || 'slate-400'}">${l.status}</span>
              <button data-app-id="${l.application_id}" class="clear-limit-btn text-slate-400 hover:text-coral-500" title="Remove limit">
                <svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg>
              </button>
            </div>
          </div>`
          )
          .join('');

        limitsEl.querySelectorAll('.clear-limit-btn').forEach((btn) => {
          btn.addEventListener('click', async () => {
            await getJSON(`/api/alerts/app-limit/${btn.dataset.appId}`, {
              method: 'PATCH',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ minutes: null }),
            });
            loadAlerts();
          });
        });
      }
    }
  }

  function wireAlertControls() {
    if ($('alert-limit-slider')) {
      $('alert-limit-slider').addEventListener('change', async (e) => {
        await getJSON('/api/alerts/global', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ minutes: Number(e.target.value) * 60 }),
        });
        loadAlerts();
      });
    }
    if ($('add-limit-btn')) {
      $('add-limit-btn').addEventListener('click', async () => {
        const apps = await getJSON('/api/applications');
        const names = apps.map((a) => a.name).join(', ');
        const name = prompt(`Set a limit for which app?\n(${names})`);
        const app = apps.find((a) => a.name.toLowerCase() === (name || '').toLowerCase());
        if (!app) return;
        const minutes = prompt(`Daily limit for ${app.name}, in minutes:`, '60');
        if (!minutes || isNaN(Number(minutes))) return;
        await getJSON(`/api/alerts/app-limit/${app.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ minutes: Number(minutes) }),
        });
        loadAlerts();
      });
    }
  }

  /* ============================================================
     USAGE ANALYTICS
  ============================================================ */
  let analyticsRangeDays = 7;

  async function loadAnalytics(days = analyticsRangeDays) {
    const [trends, timeOfDay, wow, insights] = await Promise.all([
      getJSON(`/api/analytics/daily-trends?days=${days}`),
      getJSON(`/api/analytics/time-of-day?days=${days}`),
      getJSON(`/api/analytics/week-over-week?weeks=4`),
      getJSON(`/api/analytics/insights`),
    ]);

    if (window.dailyTrendsChart) {
      window.dailyTrendsChart.data.labels = trends.map((t) => t.label);
      window.dailyTrendsChart.data.datasets[0].data = trends.map((t) => t.total_hours);
      window.dailyTrendsChart.data.datasets[1].data = trends.map((t) => t.productive_hours);
      window.dailyTrendsChart.update();
    }

    if (window.timeOfDayChart) {
      window.timeOfDayChart.data.labels = timeOfDay.map((t) => t.bucket);
      window.timeOfDayChart.data.datasets[0].data = timeOfDay.map((t) => t.hours);
      window.timeOfDayChart.update();
    }

    if (window.wowChart) {
      window.wowChart.data.labels = wow.map((w) => w.label);
      window.wowChart.data.datasets[0].data = wow.map((w) => w.hours);
      window.wowChart.update();
    }

    const insightsEl = $('insights-list');
    if (insightsEl) {
      insightsEl.innerHTML = insights
        .map(
          (i) => `
        <div class="flex items-start gap-3 p-3.5 rounded-xl bg-slate-50 dark:bg-white/[.03]">
          <span class="text-[18px] leading-none">${i.icon}</span>
          <p class="text-[13px] text-slate-600 dark:text-slate-300 leading-relaxed">${i.text}</p>
        </div>`
        )
        .join('');
    }

    if ($('analytics-export-btn')) $('analytics-export-btn').href = `/api/analytics/export?days=${days}`;
  }

  function wireAnalyticsRangeButtons() {
    document.querySelectorAll('.analytics-range-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.analytics-range-btn').forEach((b) => {
          b.classList.remove('bg-brand-600', 'text-white');
          b.classList.add('bg-white', 'dark:bg-white/5', 'border', 'border-slate-200', 'dark:border-white/10', 'text-slate-500');
        });
        btn.classList.add('bg-brand-600', 'text-white');
        btn.classList.remove('bg-white', 'dark:bg-white/5', 'border', 'border-slate-200', 'dark:border-white/10', 'text-slate-500');
        analyticsRangeDays = Number(btn.dataset.days);
        loadAnalytics(analyticsRangeDays).catch(console.warn);
      });
    });
  }

  /* ============================================================
     FOCUS MODE
  ============================================================ */
  const focusState = { presetMinutes: 60, presetType: 'Deep Work', remainingSeconds: 60 * 60, intervalId: null, sessionId: null, running: false };
  const RING_CIRCUMFERENCE = 628;

  function renderTimer() {
    const m = Math.floor(focusState.remainingSeconds / 60);
    const s = focusState.remainingSeconds % 60;
    if ($('timer-display')) $('timer-display').textContent = `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    if ($('timer-session-label')) $('timer-session-label').textContent = `${focusState.presetType} session`;
    if ($('timer-ring')) {
      const total = focusState.presetMinutes * 60;
      const fraction = total ? focusState.remainingSeconds / total : 0;
      $('timer-ring').style.strokeDashoffset = String(RING_CIRCUMFERENCE * fraction);
    }
  }

  async function tick() {
    focusState.remainingSeconds -= 1;
    if (focusState.remainingSeconds <= 0) {
      clearInterval(focusState.intervalId);
      focusState.running = false;
      if (focusState.sessionId) {
        await getJSON(`/api/focus/sessions/${focusState.sessionId}/complete`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ actual_minutes: focusState.presetMinutes }),
        }).catch(() => {});
      }
      focusState.sessionId = null;
      focusState.remainingSeconds = focusState.presetMinutes * 60;
      renderTimer();
      loadFocus().catch(() => {});
      loadDashboard().catch(() => {});
      return;
    }
    renderTimer();
  }

  async function startTimer() {
    if (focusState.running) return;
    if (!focusState.sessionId) {
      const session = await getJSON('/api/focus/sessions/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_type: focusState.presetType, planned_minutes: focusState.presetMinutes }),
      });
      focusState.sessionId = session.id;
    }
    focusState.running = true;
    focusState.intervalId = setInterval(tick, 1000);
  }

  function pauseTimer() {
    focusState.running = false;
    clearInterval(focusState.intervalId);
  }

  async function resetTimer() {
    pauseTimer();
    if (focusState.sessionId) {
      await getJSON(`/api/focus/sessions/${focusState.sessionId}/complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ actual_minutes: Math.round((focusState.presetMinutes * 60 - focusState.remainingSeconds) / 60) }),
      }).catch(() => {});
    }
    focusState.sessionId = null;
    focusState.remainingSeconds = focusState.presetMinutes * 60;
    renderTimer();
    loadFocus().catch(() => {});
  }

  function wireFocusTimer() {
    document.querySelectorAll('.preset-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        if (focusState.running || focusState.sessionId) return; // don't swap mid-session
        focusState.presetMinutes = Number(btn.dataset.mins);
        focusState.presetType = btn.textContent.trim();
        focusState.remainingSeconds = focusState.presetMinutes * 60;
        renderTimer();
      });
    });
    if ($('timer-play-btn')) $('timer-play-btn').addEventListener('click', () => startTimer().catch(console.warn));
    if ($('timer-pause-btn')) $('timer-pause-btn').addEventListener('click', pauseTimer);
    if ($('timer-reset-btn')) $('timer-reset-btn').addEventListener('click', () => resetTimer().catch(console.warn));
    renderTimer();
  }

  async function loadFocus() {
    const [sessions, trend] = await Promise.all([
      getJSON(`/api/focus/sessions?date=${new Date().toISOString().slice(0, 10)}`),
      getJSON('/api/focus/trend?days=7'),
    ]);

    if (window.focusTrendChart) {
      window.focusTrendChart.data.labels = trend.map((t) => t.label);
      window.focusTrendChart.data.datasets[0].data = trend.map((t) => t.sessions);
      window.focusTrendChart.update();
    }

    const historyEl = $('focus-history');
    if (historyEl) {
      if (!sessions.length) {
        historyEl.innerHTML = `<p class="text-[13px] text-slate-400 text-center py-4">No focus sessions yet today — start one on the left.</p>`;
      } else {
        historyEl.innerHTML = sessions
          .map((s) => {
            const start = s.start_time ? new Date(s.start_time).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }) : '';
            const dur = s.completed ? `${s.actual_minutes} min` : `${s.actual_minutes || 0} / ${s.planned_minutes} min`;
            return `
            <div class="flex items-center justify-between py-2">
              <div class="flex items-center gap-3">
                <div class="w-2 h-2 rounded-full ${s.completed ? 'bg-mint-500' : 'bg-amber-500'}"></div>
                <div>
                  <p class="text-[13px] font-semibold text-slate-700 dark:text-slate-200">${s.session_type}</p>
                  <p class="text-[11.5px] text-slate-400">${start}</p>
                </div>
              </div>
              <span class="font-mono text-[12.5px] text-slate-500 dark:text-slate-400">${dur}</span>
            </div>`;
          })
          .join('');
      }
    }
  }

  /* ============================================================
     AI PREDICTIONS
  ============================================================ */
  async function loadPredictions() {
    let data;
    try {
      data = await getJSON('/api/predictions/forecast?days=7');
    } catch (e) {
      await getJSON('/api/predictions/train', { method: 'POST' });
      data = await getJSON('/api/predictions/forecast?days=7');
    }

    const tomorrow = data.forecast[0];
    if (!tomorrow) return;

    if ($('pred-total-time')) $('pred-total-time').textContent = fmtHM(tomorrow.predicted_total_minutes);
    if ($('pred-score')) $('pred-score').textContent = tomorrow.predicted_productivity_score;

    const scoreDiff = tomorrow.predicted_productivity_score - data.today_productivity_score;
    if ($('pred-score-sub')) {
      $('pred-score-sub').textContent = `${scoreDiff >= 0 ? '↑' : '↓'} ${Math.abs(scoreDiff)}pts vs today`;
      $('pred-score-sub').className = `text-[11.5px] font-semibold mt-1 ${scoreDiff >= 0 ? 'text-mint-500' : 'text-coral-500'}`;
    }

    const totalDiffPct = data.today_total_minutes
      ? Math.round(((tomorrow.predicted_total_minutes - data.today_total_minutes) / data.today_total_minutes) * 100)
      : 0;
    if ($('pred-total-sub')) {
      $('pred-total-sub').textContent = `${totalDiffPct >= 0 ? '↑' : '↓'} ${Math.abs(totalDiffPct)}% vs today`;
    }

    const topRisk = data.breach_risk && data.breach_risk[0];
    if ($('pred-risk-level')) $('pred-risk-level').textContent = topRisk ? topRisk.risk : 'Low';
    if ($('pred-risk-sub')) {
      $('pred-risk-sub').textContent = topRisk
        ? `${topRisk.application} projected at ${Math.round(topRisk.projected_minutes)}m vs ${topRisk.limit_minutes}m limit`
        : 'No app limits currently at risk';
    }

    const recEl = $('ai-recommendations');
    if (recEl && data.recommendations) {
      recEl.innerHTML = data.recommendations
        .map(
          (r) => `
        <div class="flex items-start gap-3 p-3.5 rounded-xl bg-slate-50 dark:bg-white/[.03]">
          <span class="text-[16px] leading-none">${r.icon}</span>
          <p class="text-[12.5px] text-slate-600 dark:text-slate-300 leading-relaxed">${r.text}</p>
        </div>`
        )
        .join('');
    }

    if (window.forecastChart) {
      const labels = ['Today', ...data.forecast.map((f) => f.label.split(' ')[0])];
      const actual = [Math.round((data.today_total_minutes / 60) * 100) / 100, ...data.forecast.map(() => null)];
      const predicted = [
        Math.round((data.today_total_minutes / 60) * 100) / 100,
        ...data.forecast.map((f) => f.predicted_total_hours),
      ];
      window.forecastChart.data.labels = labels;
      window.forecastChart.data.datasets[0].data = actual;
      window.forecastChart.data.datasets[1].data = predicted;
      window.forecastChart.update();
    }
  }

  /* ============================================================
     SETTINGS
  ============================================================ */
  async function loadSettings() {
    const s = await getJSON('/api/settings');

    applyThemeMode(s.theme_mode);
    updateThemeButtonStates(s.theme_mode);

    if ($('language-select')) {
      const languages = ['English (United States)', 'Français', 'Deutsch', 'Español', 'हिंदी', '日本語'];
      $('language-select').innerHTML = languages.map((l) => `<option ${l === s.language ? 'selected' : ''}>${l}</option>`).join('');
    }

    const startupEl = $('startup-toggles');
    if (startupEl) {
      startupEl.innerHTML =
        apiSettingsToggleRow('Launch at Startup', 'Start Scolect when your computer boots', 'launch_at_startup', s.launch_at_startup) +
        apiSettingsToggleRow('Launch Minimized', 'Open directly to system tray', 'launch_minimized', s.launch_minimized) +
        apiSettingsToggleRow('Minimize to Tray', 'Keep running in background when closed', 'minimize_to_tray', s.minimize_to_tray) +
        apiSettingsToggleRow('Idle Detection', 'Pause tracking after 5 min inactivity', 'idle_detection', s.idle_detection);

      startupEl.querySelectorAll('.settings-toggle').forEach((btn) => {
        btn.addEventListener('click', async () => {
          const checked = btn.dataset.checked === 'true';
          await getJSON('/api/settings', {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ [btn.dataset.field]: !checked }),
          });
          loadSettings();
        });
      });
    }
  }

  function apiSettingsToggleRow(label, sub, field, checked) {
    return `
    <div class="flex items-center justify-between">
      <div>
        <p class="text-[13px] font-semibold text-slate-700 dark:text-slate-200">${label}</p>
        <p class="text-[11.5px] text-slate-400">${sub}</p>
      </div>
      <button data-field="${field}" data-checked="${checked}"
        class="settings-toggle w-11 h-6 rounded-full ${checked ? 'bg-brand-600' : 'bg-slate-200 dark:bg-white/10'} relative">
        <span class="absolute top-0.5 ${checked ? 'translate-x-[22px]' : 'translate-x-0.5'} w-5 h-5 rounded-full bg-white shadow"></span>
      </button>
    </div>`;
  }

  function wireSettingsControls() {
    // Theme mode buttons are wired once in wireTheme() — not duplicated here,
    // so clicking them doesn't fire two PATCH requests.
    if ($('language-select')) {
      $('language-select').addEventListener('change', async (e) => {
        await getJSON('/api/settings', {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ language: e.target.value }),
        });
      });
    }

    if ($('activitywatch-sync-btn')) {
      $('activitywatch-sync-btn').addEventListener('click', async () => {
        const button = $('activitywatch-sync-btn');
        const status = $('activitywatch-sync-status');
        button.disabled = true;
        button.textContent = 'Syncing...';
        status.textContent = 'Connecting to ActivityWatch at localhost:5600...';
        try {
          const result = await getJSON('/api/activity/sync', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ base_url: 'http://localhost:5600' }),
          });
          status.textContent = result.browser_watcher
            ? `Imported ${result.added} events: ${result.window_events} apps and ${result.web_events} websites.`
            : `Imported ${result.added} app events. No aw-watcher-web bucket was found yet.`;
          await loadDashboard();
          await loadApplications();
          await loadAlerts();
          await loadAnalytics();
          await loadPredictions();
          await loadActivityReview();
        } catch (error) {
          status.textContent = 'ActivityWatch was not available. Start it locally and try again.';
        } finally {
          button.disabled = false;
          button.textContent = 'Sync ActivityWatch';
        }
      });
    }
  }

  async function loadActivityReview() {
    const list = $('activity-review-list');
    const count = $('activity-review-count');
    if (!list || !count) return;
    const events = await getJSON('/api/activity/review');
    count.textContent = `${events.length} to review`;
    if (!events.length) {
      list.innerHTML = '<p class="text-[12px] text-slate-400">Nothing needs review right now.</p>';
      return;
    }
    const categories = ['Development', 'Study', 'Work', 'Communication', 'Entertainment', 'Design', 'Browsing', 'Personal', 'Other'];
    list.innerHTML = events.map((event) => `
      <div class="rounded-xl bg-slate-50 p-3 dark:bg-white/[.03]" data-review-id="${event.id}">
        <div class="flex items-center justify-between gap-3">
          <div class="min-w-0">
            <p class="truncate text-[12.5px] font-semibold text-slate-700 dark:text-slate-200">${event.application_name}</p>
            <p class="text-[11px] text-slate-400">${event.duration_minutes} min across ${event.event_count} events · detected as ${event.detected_category}</p>
          </div>
          <button class="review-save-btn rounded-lg bg-brand-600 px-2.5 py-1.5 text-[11px] font-semibold text-white" data-review-save="${event.id}">Save</button>
        </div>
        <div class="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-3">
          <select data-review-category="${event.id}" class="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-[11px] dark:border-white/10 dark:bg-slate-900">
            ${categories.map((category) => `<option value="${category}" ${category === event.detected_category ? 'selected' : ''}>${category}</option>`).join('')}
          </select>
          <input data-review-purpose="${event.id}" class="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-[11px] dark:border-white/10 dark:bg-slate-900" placeholder="Purpose, e.g. coding" />
          <label class="flex items-center gap-2 rounded-lg border border-slate-200 px-2 py-1.5 text-[11px] text-slate-500 dark:border-white/10 dark:text-slate-400">
            <input type="checkbox" data-review-audio="${event.id}" class="accent-brand-600" ${event.is_background_audio ? 'checked' : ''} />
            Background audio only
          </label>
        </div>
      </div>`).join('');

    list.querySelectorAll('[data-review-save]').forEach((button) => {
      button.addEventListener('click', async () => {
        const id = button.dataset.reviewSave;
        await getJSON(`/api/activity/events/${id}/classify`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            category: list.querySelector(`[data-review-category="${id}"]`).value,
            purpose: list.querySelector(`[data-review-purpose="${id}"]`).value,
            is_background_audio: list.querySelector(`[data-review-audio="${id}"]`).checked,
          }),
        });
        await loadActivityReview();
        await loadDashboard();
        await loadAnalytics();
      });
    });
  }

  /* ============================================================
     THEME (single source of truth — syncs topbar toggle, Settings
     panel buttons, and the backend so it actually persists and
     actually applies dark mode, instead of being purely cosmetic)
  ============================================================ */
  function applyThemeMode(mode) {
    const root = document.documentElement;
    const dark =
      mode === 'dark' ||
      (mode === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
    root.classList.toggle('dark', dark);
    if ($('icon-sun')) $('icon-sun').classList.toggle('hidden', !dark);
    if ($('icon-moon')) $('icon-moon').classList.toggle('hidden', dark);
  }

  async function saveThemeMode(mode) {
    applyThemeMode(mode); // apply immediately, don't wait on the network
    try {
      await getJSON('/api/settings', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ theme_mode: mode }),
      });
    } catch (e) {
      console.warn('Could not save theme preference:', e.message);
    }
    updateThemeButtonStates(mode);
  }

  function updateThemeButtonStates(mode) {
    document.querySelectorAll('.theme-mode-btn').forEach((btn) => {
      const active = btn.dataset.mode === mode;
      btn.classList.toggle('border-2', active);
      btn.classList.toggle('border-brand-500', active);
      btn.classList.toggle('bg-brand-50', active);
      btn.classList.toggle('dark:bg-brand-500/10', active);
      btn.classList.toggle('text-brand-700', active);
      btn.classList.toggle('dark:text-brand-300', active);
      btn.classList.toggle('border', !active);
      btn.classList.toggle('border-slate-200', !active);
      btn.classList.toggle('dark:border-white/10', !active);
      btn.classList.toggle('text-slate-500', !active);
    });
  }

  function wireTheme() {
    if ($('theme-toggle')) {
      $('theme-toggle').addEventListener('click', () => {
        const isDark = document.documentElement.classList.contains('dark');
        saveThemeMode(isDark ? 'light' : 'dark');
      });
    }
    document.querySelectorAll('.theme-mode-btn').forEach((btn) => {
      btn.addEventListener('click', () => saveThemeMode(btn.dataset.mode));
    });
  }

  /* ============================================================
     GLOBAL TOPBAR SEARCH
     Jumps to Applications and runs the search there — the topbar
     box was previously decorative with no listener at all.
  ============================================================ */
  function wireGlobalSearch() {
    const input = $('global-search-input');
    if (!input) return;
    input.addEventListener('keydown', (e) => {
      if (e.key !== 'Enter') return;
      const query = input.value.trim();
      if (!query) return;

      document.querySelector('#sidebar-nav [data-target="applications"]').click();
      if ($('apps-search-input')) {
        $('apps-search-input').value = query;
        loadApplications().catch(console.warn);
      }
    });
  }

  /* ============================================================
     BOOT
  ============================================================ */
  document.addEventListener('DOMContentLoaded', () => {
    wireTheme();
    wireGlobalSearch();

    loadDashboard().catch((e) => console.warn('Dashboard live-data unavailable:', e.message));

    wireApplicationFilters();
    loadApplications().catch((e) => console.warn('Applications live-data unavailable:', e.message));

    wireAlertControls();
    loadAlerts().catch((e) => console.warn('Alerts live-data unavailable:', e.message));

    wireAnalyticsRangeButtons();
    loadAnalytics().catch((e) => console.warn('Analytics live-data unavailable:', e.message));

    wireFocusTimer();
    loadFocus().catch((e) => console.warn('Focus live-data unavailable:', e.message));

    loadPredictions().catch((e) => console.warn('Predictions live-data unavailable:', e.message));

    wireSettingsControls();
    loadSettings().catch((e) => console.warn('Settings live-data unavailable:', e.message));
    loadActivityReview().catch((e) => console.warn('Activity review unavailable:', e.message));
  });
})();
