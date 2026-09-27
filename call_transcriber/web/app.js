'use strict';
const $ = (id) => document.getElementById(id);
const token = location.hash.slice(1) || sessionStorage.getItem('call-token') || '';
if (token) sessionStorage.setItem('call-token', token);
history.replaceState(null, '', location.pathname);
let pickerPath = '';
let parentPath = '';
let previousState = '';
let busy = false;
let offset = 0;
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
  ['folder', 'start', 'browse', 'preview'].forEach(id => { $(id).disabled = active; });
  $('cancel').hidden = !active;
}
function showPlan(plan) {
  if (!plan) return;
  $('resource-title').textContent = plan.no_work ? 'Все записи уже расшифрованы' : plan.parallel ? `Автоматически: до ${plan.parallel} записей одновременно` : 'Недостаточно свободных ресурсов';
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
function showJobs(jobs, target = 'jobs') {
  const fragment = document.createDocumentFragment();
  for (const job of jobs) {
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
  if (target === 'jobs') $('count').textContent = jobs.length ? `${jobs.length} аудио` : '';
}
function showState(state) {
  const active = ['preparing', 'running', 'waiting'].includes(state.phase);
  controls(active);
  $('status').textContent = state.message;
  showPlan(state.plan);
  showJobs(state.jobs);
  const completed = state.completed ?? state.jobs.filter(j => ['done', 'skipped'].includes(j.status)).length;
  total = state.total ?? state.jobs.length;
  const failed = state.failed ?? state.jobs.filter(j => j.status === 'error').length;
  $('summary').textContent = `${completed} / ${total} готово` + (failed ? ` · ошибок: ${failed}` : '');
  $('total-progress').hidden = !state.jobs.length;
  const progress = state.jobs.reduce((sum, j) => sum + (['done', 'skipped', 'error'].includes(j.status) ? 100 : j.percent), 0);
  $('total-progress').value = state.progress ?? (state.jobs.length ? progress / state.jobs.length : 0);
  $('count').textContent = `${total} записей`;
  $('pages').hidden = total <= 100;
  $('previous-page').disabled = offset === 0;
  $('next-page').disabled = offset + 100 >= total;
  $('page-label').textContent = `${offset + 1}–${Math.min(offset + 100, total)} из ${total}`;
  showDesignState(state);
  if (state.phase === 'error') error(state.message);
}
async function browse(path) {
  $('picker-error').textContent = '';
  try {
    const result = await api('folders?path=' + encodeURIComponent(path));
    pickerPath = result.path; parentPath = result.parent;
    $('picker-path').textContent = pickerPath;
    const buttons = result.directories.map(dir => {
      const button = document.createElement('button'); button.type = 'button'; button.textContent = dir.name;
      button.addEventListener('click', () => browse(dir.path)); return button;
    });
    if (!buttons.length) { const empty = document.createElement('p'); empty.textContent = 'Вложенных папок нет.'; buttons.push(empty); }
    $('directories').replaceChildren(...buttons);
    $('parent-folder').disabled = pickerPath === parentPath;
    if (!$('picker').open) $('picker').showModal();
  } catch (e) { if ($('picker').open) $('picker-error').textContent = e.message; else error(e.message); }
}
$('browse').addEventListener('click', () => browse($('folder').value));
$('parent-folder').addEventListener('click', () => browse(parentPath));
$('close-picker').addEventListener('click', () => $('picker').close());
$('close-result').addEventListener('click', () => $('result').close());
$('result').addEventListener('close', () => { $('result-text').textContent = ''; });
$('select-folder').addEventListener('click', () => { $('folder').value = pickerPath; updateOutput(); $('picker').close(); error(); });
$('preview').addEventListener('click', async () => {
  controls(true); $('cancel').hidden = true; error();
  try {
    const result = await api('preview', {folder: $('folder').value});
    // Preview rows are not yet owned by a running job; no result links before Start.
    showJobs(result.jobs.map(j => j.status === 'skipped' ? {...j, status: 'preview', stage: 'TXT уже есть'} : j));
    $('queue-details').hidden = false; $('queue-details').open = true;
    showPlan(result.plan); $('summary').textContent = `${result.total} найдено`;
    $('status').textContent = result.jobs.length ? `К обработке: ${result.pending}. Готовые TXT будут пропущены.` : 'Записи не найдены. Выберите другую папку.';
    $('total-progress').hidden = true; $('pages').hidden = true;
    if (result.total > 100) $('status').textContent += ' Предпросмотр: первые 100 записей.';
  } catch (e) { error(e.message); }
  finally { controls(false); }
});
$('folder-form').addEventListener('submit', async event => {
  event.preventDefault(); error(); controls(true); offset = 0;
  try { showState(await api('start', {folder: $('folder').value})); }
  catch (e) { error(e.message); controls(false); }
});
$('cancel').addEventListener('click', async () => {
  $('cancel').disabled = true;
  try { showState(await api('cancel', {})); } catch (e) { error(e.message); }
  finally { $('cancel').disabled = false; }
});
$('previous-page').addEventListener('click', () => { offset = Math.max(0, offset - 100); previousState = ''; });
$('next-page').addEventListener('click', () => { if (offset + 100 < total) offset += 100; previousState = ''; });
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
  $('queue-details').hidden = !total;
  const recent = state.recent || [];
  $('recent-section').hidden = !recent.length;
  $('recent').replaceChildren(...recent.map(job => {
    const row = document.createElement('div'); row.className = 'recent-row';
    const button = document.createElement('button'); button.type = 'button'; button.textContent = job.relative + '.txt';
    button.addEventListener('click', () => showResult(job.id)); row.append(button); return row;
  }));
  if (state.events?.length) $('events').replaceChildren(...state.events.map(event => {
    const row = document.createElement('div'); row.className = 'event';
    const time = document.createElement('time'); time.textContent = event.time;
    const message = document.createElement('span'); message.textContent = event.text; row.append(time, message); return row;
  }));
}

async function poll() {
  try {
    const state = await api('state?offset=' + offset);
    const serialized = JSON.stringify(state);
    if (state.phase !== 'idle' && serialized !== previousState) { showState(state); previousState = serialized; }
  } catch (e) { error('Связь с локальным приложением потеряна. Проверьте, что оно запущено. ' + e.message); }
  setTimeout(poll, 1000);
}
(async () => {
  try {
    const info = await api('info'); $('folder').value = info.folder; updateOutput();
    $('resource-title').textContent = `${info.resources.available_gb} ГБ свободно из ${info.resources.total_gb} ГБ · ${info.resources.cores} ядер CPU`;
    poll();
  } catch (e) { error(e.message); $('resource-title').textContent = 'Откройте ссылку из терминала'; }
})();
