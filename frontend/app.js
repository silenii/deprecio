const API = '/api/v1';

function $(id) { return document.getElementById(id); }

function money(value) {
  if (value == null) return 'Нет данных';
  return `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(value)} ₽`;
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[char]));
}

async function api(path, options = {}) {
  const response = await fetch(API + path, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.message || 'API недоступен');
  }
  return response.json();
}

function setMessage(text, error = false) {
  $('search-message').textContent = text;
  $('search-message').className = error ? 'message error' : 'message';
}

function replaceUrl(params) {
  const query = new URLSearchParams(params);
  history.pushState({}, '', query.toString() ? `/?${query}` : '/');
}

function selectedModelIds() {
  return [...document.querySelectorAll('.compare-check:checked')].map((input) => input.value);
}

function renderSearchCard(device) {
  return `<article class="result-card-wrap"><button class="result-card" data-id="${escapeHtml(device.model_id)}" aria-label="Открыть устройство ${escapeHtml(device.name)}"><p>${escapeHtml(device.brand)} · ${escapeHtml(device.lineage?.tier)}</p><h3>${escapeHtml(device.name)}</h3><p>${escapeHtml(device.chipset)}</p></button><label class="check-label"><input class="compare-check" type="checkbox" value="${escapeHtml(device.model_id)}" aria-label="Выбрать ${escapeHtml(device.name)} для сравнения"> Сравнить</label></article>`;
}

function bindSearchCards() {
  document.querySelectorAll('.result-card').forEach((card) => card.addEventListener('click', () => showDevice(card.dataset.id)));
  document.querySelectorAll('.compare-check').forEach((input) => input.addEventListener('change', updateCompareButton));
}

function updateCompareButton() {
  const count = selectedModelIds().length;
  $('compare-selected').disabled = count < 2 || count > 5;
  $('compare-selected').textContent = count > 5 ? 'Выбрано больше 5' : `Сравнить выбранные${count ? ` (${count})` : ''}`;
}

async function search(query, updateUrl = true) {
  if (updateUrl) replaceUrl({ q: query });
  $('results').innerHTML = '';
  setMessage('Загрузка...');
  $('result-count').textContent = '';
  try {
    const devices = await api(`/devices/search?query=${encodeURIComponent(query)}`);
    $('result-count').textContent = `${devices.length} найдено`;
    if (!devices.length) return setMessage('Ничего не найдено. Проверьте название модели.');
    setMessage('');
    $('results').innerHTML = devices.map(renderSearchCard).join('');
    bindSearchCards();
    updateCompareButton();
  } catch (error) { setMessage(error.message, true); }
}

async function compareModels(ids = selectedModelIds(), updateUrl = true) {
  const modelIds = ids.slice(0, 5);
  if (modelIds.length < 2) {
    $('compare-result').innerHTML = '<p class="message error">Выберите минимум две модели.</p>';
    return;
  }
  if (updateUrl) replaceUrl({ compare: modelIds.join(',') });
  $('compare-result').innerHTML = '<p class="message">Загрузка...</p>';
  try {
    const data = await api(`/analytics/compare?${modelIds.map((id) => `model_ids=${encodeURIComponent(id)}`).join('&')}`);
    $('compare-result').innerHTML = `<table class="comparison"><thead><tr><th>Модель</th><th>Цена</th><th>RV</th><th>Объявлений</th></tr></thead><tbody>${data.devices.map((device) => `<tr><td>${escapeHtml(device.name)}</td><td>${money(device.current_price_rub)}</td><td>${device.residual_value_percent == null ? '—' : `${device.residual_value_percent.toFixed(1)}%`}</td><td>${device.market_stats?.listings_count || 0}</td></tr>`).join('')}</tbody></table>`;
  } catch (error) { $('compare-result').innerHTML = `<p class="message error">${escapeHtml(error.message)}</p>`; }
}

function reportUrl(modelId, format) { return `${API}/reports/${encodeURIComponent(modelId)}?format=${encodeURIComponent(format)}`; }

function renderReportControls(modelId) {
  return `<div class="report-controls"><label for="report-format">Формат отчёта</label><select id="report-format" aria-label="Формат отчёта"><option>json</option><option>csv</option><option>md</option><option>html</option></select><a class="secondary report-link" href="${reportUrl(modelId, 'json')}" download aria-label="Скачать отчёт устройства">Скачать отчёт</a></div>`;
}

function renderDevice(device, forecast, history) {
  const stats = device.market_stats || {};
  const points = (history.chart || []).map((point) => point.price_rub).filter(Number.isFinite);
  const max = Math.max(...points, 1);
  const min = Math.min(...points, max);
  const poly = points.map((value, index) => `${index * (100 / Math.max(points.length - 1, 1))},${170 - ((value - min) / Math.max(max - min, 1)) * 150}`).join(' ');
  $('device-title').textContent = device.name;
  $('device-content').innerHTML = `<div class="device-header"><div><h3>${escapeHtml(device.name)}</h3><span class="muted">${escapeHtml(device.brand)} · ${escapeHtml(device.tier)} · ${escapeHtml(device.characteristics?.chipset)}</span></div><span class="muted">${escapeHtml(device.model_id)}</span></div><div class="metrics"><div class="metric"><small>Текущая цена</small><strong>${money(device.current_price_rub)}</strong></div><div class="metric"><small>Остаточная стоимость</small><strong>${device.residual_value_percent == null ? 'Нет данных' : `${device.residual_value_percent.toFixed(1)}%`}</strong></div><div class="metric"><small>Объявлений</small><strong>${stats.listings_count || 0}</strong></div><div class="metric"><small>MSRP</small><strong>${money(device.msrp_rub)}</strong></div></div><div class="panel-grid"><div class="panel"><h3>История цен</h3>${points.length ? `<svg class="chart" viewBox="0 0 100 180" preserveAspectRatio="none" role="img" aria-label="График истории цен"><line x1="0" y1="170" x2="100" y2="170"/><polyline points="${poly}"/></svg><p class="muted">Изменение: ${history.price_change_percent == null ? 'нет данных' : `${history.price_change_percent}%`}</p>` : '<p class="muted">История цен пока отсутствует.</p>'}</div><div class="panel"><h3>Прогноз</h3>${forecast ? `<p>${escapeHtml(forecast.summary_verdict)}</p><p class="muted">Темп снижения: ${(forecast.monthly_decay_rate * 100).toFixed(1)}% в месяц. Оптимальный момент: ${forecast.sweet_spot_month} мес.</p>` : '<p class="muted">Недостаточно market data для прогноза.</p>'}</div></div>${renderReportControls(device.model_id)}`;
  $('report-format').addEventListener('change', (event) => { $('device-content').querySelector('.report-link').href = reportUrl(device.model_id, event.target.value); });
}

async function showDevice(id, updateUrl = true) {
  if (updateUrl) replaceUrl({ device: id });
  $('device-section').hidden = false;
  $('device-content').innerHTML = '<div class="message">Загрузка аналитики...</div>';
  $('device-error').hidden = true;
  try {
    const data = await api(`/analytics/compare?model_ids=${encodeURIComponent(id)}&model_ids=${encodeURIComponent(id)}`);
    const device = data.devices[0];
    const forecast = device.current_price_rub == null ? null : await api(`/forecast/${encodeURIComponent(id)}?current_price_rub=${device.current_price_rub}&months_horizon=6`);
    const history = await api(`/devices/${encodeURIComponent(id)}/price-history?limit=12`);
    renderDevice(device, forecast, history);
    $('device-section').scrollIntoView({ behavior: 'smooth' });
  } catch (error) {
    $('device-error').textContent = error.message;
    $('device-error').hidden = false;
    $('device-content').innerHTML = '';
  }
}

function recommendationPayload() {
  const form = new FormData($('recommendation-form'));
  const payload = { limit: 20 };
  ['budget_min_rub', 'budget_max_rub'].forEach((field) => { if (form.get(field)) payload[field] = Number(form.get(field)); });
  ['tier', 'brand'].forEach((field) => { if (form.get(field)) payload[field] = form.get(field); });
  return payload;
}

async function recommend(updateUrl = true) {
  const payload = recommendationPayload();
  if (updateUrl) replaceUrl({ recommendations: '1', ...payload });
  $('recommendation-result').innerHTML = '<p class="message">Загрузка...</p>';
  try {
    const data = await api('/recommendations', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    const rows = data.results.map((item) => `<tr><td>${escapeHtml(item.device.name)}</td><td>${money(item.price_rub)}</td><td>${item.device.residual_value_percent == null ? '—' : `${item.device.residual_value_percent.toFixed(1)}%`}</td><td>${item.score.toFixed(2)}</td></tr>`).join('');
    $('recommendation-result').innerHTML = `<table class="comparison"><thead><tr><th>Имя</th><th>Цена</th><th>RV</th><th>Score</th></tr></thead><tbody>${rows}</tbody></table>${rows ? '' : '<p class="message">Подходящих устройств не найдено.</p>'}`;
  } catch (error) { $('recommendation-result').innerHTML = `<p class="message error">${escapeHtml(error.message)}</p>`; }
}

async function init() {
  try { await api('/devices/search?query=xiaomi'); $('api-status').textContent = 'API: онлайн'; $('api-status').classList.add('online'); }
  catch { $('api-status').textContent = 'API: ошибка'; }
  const params = new URLSearchParams(location.search);
  if (params.get('device')) await showDevice(params.get('device'), false);
  else if (params.get('q')) { $('search-input').value = params.get('q'); await search(params.get('q'), false); }
  if (params.get('compare')) await compareModels(params.get('compare').split(','), false);
  if (params.get('recommendations')) {
    ['budget_min_rub', 'budget_max_rub', 'tier', 'brand'].forEach((field) => { if (params.has(field)) $(field).value = params.get(field); });
    await recommend(false);
  }
}

$('search-form').addEventListener('submit', (event) => { event.preventDefault(); search($('search-input').value.trim()); });
$('recommendation-form').addEventListener('submit', (event) => { event.preventDefault(); recommend(); });
$('compare-selected').addEventListener('click', () => compareModels());
$('share-button').addEventListener('click', async () => { await navigator.clipboard?.writeText(location.href); $('share-button').textContent = 'Ссылка скопирована'; });
window.addEventListener('popstate', init);
init();