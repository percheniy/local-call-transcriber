'use strict';
const $ = (id) => document.getElementById(id);
const token = location.hash.slice(1) || sessionStorage.getItem('call-token') || '';
if (token) sessionStorage.setItem('call-token', token);
history.replaceState(null, '', location.pathname);
let previousState = '';
let busy = false;
let pickerMode = "native";
let total = 0;

async function api(path, data) {
  const response = await fetch('/api/' + path, {
    method: data === undefined ? 'GET' : 'POST',
    headers: {Authorization: 'Bearer ' + token, 'Content-Type': 'application/json'},
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || 'Не удалось выполнить запрос.');
  return payload;
}
function error(message = '') {
  $('error').textContent = message;
  $('error').hidden = !message;
}
function controls(active) {
  busy = active;
  ['folder', 'start', 'browse', 'preview', 'parallel-mode'].forEach(id => { $(id).disabled = active; });
  $('cancel').hidden = !active;
}
function showPlan(plan) {
  if (!plan) return;
  $('resource-title').textContent = plan.no_work ? 'Все записи уже расшифрованы' : plan.parallel ? `${plan.mode === "auto" ? "Автоматически" : "Выбрано " + plan.mode}: до ${plan.parallel} записей одновременно` : 'Недостаточно свободных ресурсов';
  $('resource-detail').textContent = plan.reason + (plan.measured_peak_gb ? ` Измеренный пик первой записи: ${plan.measured_peak_gb} ГБ.` : ' После первой записи оценка уточнится по фактическому расходу памяти.');
}
async function showResult(id) {
  try {
    const result = await api('result?id=' + id);
    $('result-path').textContent = result.path;
    $('result-text').textContent = result.text;
    $('result').showModal();
  } catch (e) { error(e.message); }
}
function showJobs(jobs, target) {
  const fragment = document.createDocumentFragment();
  for (const job of jobs.slice(0, 10)) {
    const row = document.createElement('div');
    row.className = 'job'; row.dataset.state = job.status;
    const info = document.createElement('div');
    const name = document.createElement('div'); name.className = 'job-name'; name.textContent = job.relative;
    info.append(name);
    if (job.error || job.warnings?.length) {
      const note = document.createElement('div'); note.className = 'job-note'; note.textContent = job.error || job.warnings.join(' '); info.append(note);
    }
    const status = document.createElement('div'); status.className = 'job-status';
    if (['done', 'skipped'].includes(job.status)) {
      const button = document.createElement('button'); button.type = 'button'; button.className = 'secondary';
      button.textContent = job.status === 'skipped' ? 'TXT уже есть' : 'Открыть TXT';
      button.addEventListener('click', () => showResult(job.id)); status.append(button);
    } else {
      status.textContent = job.stage;
      if (job.status === 'running') {
        const progress = document.createElement('progress'); progress.max = 100; progress.value = job.percent;
        progress.setAttribute('aria-label', 'Прогресс: ' + job.relative); status.append(progress);
      }
    }
    row.append(info, status); fragment.append(row);
  }
  $(target).replaceChildren(fragment);
}
function showState(state) {
  const active = ['preparing', 'running', 'waiting'].includes(state.phase);
  controls(active);
  $('status').textContent = state.message;
  showPlan(state.plan);
  const completed = state.completed ?? state.jobs.filter(j => ['done', 'skipped'].includes(j.status)).length;
  total = state.total ?? state.jobs.length;
  const failed = state.failed ?? state.jobs.filter(j => j.status === 'error').length;
  $('total-progress').hidden = !state.jobs.length;
  const progress = state.jobs.reduce((sum, j) => sum + (['done', 'skipped', 'error'].includes(j.status) ? 100 : j.percent), 0);
  $('total-progress').value = state.progress ?? (state.jobs.length ? progress / state.jobs.length : 0);
  $('count').textContent = `${total} записей`;
  showDesignState(state);
  if (state.phase === 'error') error(state.message);
}
$('browse').addEventListener('click', async () => {
  error(); $('browse').disabled = true;
  try {
    let result;
    if (pickerMode === 'mounted') {
      if (!window.showDirectoryPicker) throw new Error('Для системного выбора папки используйте Chrome или Edge.');
      const handle = await window.showDirectoryPicker({mode: 'readwrite'});
      const nonce = crypto.randomUUID().replaceAll('-', '');
      const marker = '.call-transcriber-selection-' + nonce;
      try {
        const file = await handle.getFileHandle(marker, {create: true});
        const writer = await file.createWritable(); await writer.write(nonce); await writer.close();
        result = await api('pick-mounted', {nonce});
      } finally { await handle.removeEntry(marker).catch(() => {}); }
    } else result = await api('pick-folder', {});
    if (result.folder) { $('folder').value = result.folder; updateOutput(); }
  } catch (e) { if (e.name !== 'AbortError') error(e.message); }
  finally { $('browse').disabled = busy; }
});
$('close-result').addEventListener('click', () => $('result').close());
$('result').addEventListener('close', () => { $('result-text').textContent = ''; });
function options() {
  const value = $('parallel-mode').value;
  return {folder: $('folder').value, parallel: value === 'auto' ? value : Number(value)};
}
$('preview').addEventListener('click', async () => {
  controls(true); $('cancel').hidden = true; error();
  try {
    const result = await api('preview', options());
    showPlan(result.plan); $('count').textContent = `${result.total} найдено`;
    $('status').textContent = result.total ? `К обработке: ${result.pending}. Готовые TXT будут пропущены.` : 'Записи не найдены. Выберите другую папку.';
  } catch (e) { error(e.message); }
  finally { controls(false); }
});
$('folder-form').addEventListener('submit', async event => {
  event.preventDefault(); error(); controls(true);
  try { showState(await api('start', options())); }
  catch (e) { error(e.message); controls(false); }
});
$('cancel').addEventListener('click', async () => {
  $('cancel').disabled = true;
  try { showState(await api('cancel', {})); } catch (e) { error(e.message); }
  finally { $('cancel').disabled = false; }
});
function updateOutput() {
  $('output-folder').value = $('folder').value ? $('folder').value.replace(/[\\\/]$/, '') + '/transcription' : '';
}
$('folder').addEventListener('input', updateOutput);
function showDesignState(state) {
  const labels = {idle: 'Ожидает папку', preparing: 'Подготовка…', running: 'Идёт расшифровка', waiting: 'Ожидает память', done: 'Готово', cancelled: 'Остановлено', error: 'Нужна проверка'};
  $('status-badge').dataset.state = state.phase;
  $('badge-text').textContent = labels[state.phase] || state.phase;
  $('metrics').hidden = !total;
  $('total-count').textContent = total.toLocaleString('ru-RU');
  $('done-count').textContent = state.completed || 0;
  $('queued-count').textContent = state.pending || 0;
  $('errors-text').textContent = state.failed ? `${state.failed} с ошибкой` : 'без ошибок';
  $('percent-text').textContent = `${(state.progress || 0).toFixed(1)}%`;
  $('audio-hours').textContent = state.duration ? `${(state.duration / 60).toFixed(1)} мин аудио` : 'длительность уточняется';
  $('eta').textContent = state.phase === 'done' ? '0' : state.eta ? `~${Math.ceil(state.eta / 60)} мин` : '—';
  $('active-count').textContent = `${state.active}/5`;
  [...$('slots').children].forEach((slot, i) => slot.classList.toggle('on', i < state.active));
  const activeJobs = state.active_jobs || state.jobs.filter(j => j.status === 'running');
  showJobs(activeJobs, 'active-jobs');
  $('empty').hidden = activeJobs.length > 0;
  $('empty').textContent = state.phase === 'done' ? (state.failed ? 'Очередь завершена. Проверьте ошибки ниже.' : 'Все звонки расшифрованы') : state.phase === 'preparing' ? 'Проверяем записи и модели…' : 'Нет активных задач';
  const recent = state.recent || [];
  $('recent-section').hidden = !recent.length;
  showJobs(recent.slice(0, 10 - activeJobs.length), 'recent');
  if (state.events?.length) $('events').replaceChildren(...state.events.slice(0, 10).map(event => {
    const row = document.createElement('div'); row.className = 'event';
    const time = document.createElement('time'); time.textContent = event.time;
    const message = document.createElement('span'); message.textContent = event.text; row.append(time, message); return row;
  }));
}

async function poll() {
  try {
    const state = await api('state');
    const serialized = JSON.stringify(state);
    if (state.phase !== 'idle' && serialized !== previousState) { showState(state); previousState = serialized; }
  } catch (e) { error('Связь с локальным приложением потеряна. Проверьте, что оно запущено. ' + e.message); }
  setTimeout(poll, 1000);
}
(async () => {
  try {
    const info = await api('info'); pickerMode = info.picker; $('folder').value = info.folder; updateOutput();
    $('resource-title').textContent = `${info.resources.available_gb} ГБ свободно из ${info.resources.total_gb} ГБ · ${info.resources.cores} ядер CPU`;
    poll();
  } catch (e) { error(e.message); $('resource-title').textContent = 'Откройте ссылку из терминала'; }
})();
