"""Recursive queue, adaptive process admission, and cancellation."""
from collections import deque
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import uuid

import psutil
from .resources import plan, reserve_bytes, snapshot, worker_memory, validate_parallel
from .runtime import GIB, ensure_models, ffmpeg

EXTENSIONS = {'.mp3', '.wav', '.m4a', '.flac', '.ogg', '.opus', '.aac', '.aiff', '.aif', '.wma', '.mp4'}


def discover(folder, progress=None):
    if not isinstance(folder, (str, Path)) or not str(folder).strip():
        raise ValueError("Сначала выберите папку со звонками.")
    target = Path(folder).expanduser().resolve(strict=True)
    root = target if target.is_dir() else target.parent
    sources, errors = [], []
    scanned = 0
    last_report = 0
    def report(stage, checked=0, total=None, force=False):
        nonlocal last_report
        now = time.monotonic()
        if progress and (force or now - last_report >= .1):
            progress(dict(stage=stage, found=len(sources), scanned=scanned, checked=checked, total=total))
            last_report = now
    report('searching', force=True)
    if target.is_file():
        if target.suffix.lower() not in EXTENSIONS:
            raise ValueError('Неподдерживаемый аудиоформат.')
        sources = [target]
    else:
        def onerror(error):
            errors.append(str(error))
        for directory, children, names in os.walk(root, followlinks=False, onerror=onerror):
            children[:] = sorted(name for name in children if name.lower() not in {'transcription', '.git', '.venv', 'node_modules'}
                                 and not (Path(directory) / name).is_symlink())
            for name in sorted(names):
                scanned += 1
                report("searching")
                source = Path(directory) / name
                if source.suffix.lower() in EXTENSIONS and not source.is_symlink():
                    sources.append(source)
    if errors:
        raise PermissionError('Не удалось прочитать все подпапки: ' + '; '.join(errors))
    jobs = []
    report("checking", total=len(sources), force=True)
    for source in sources:
        output = source.parent / 'transcription' / (source.name + '.txt')
        if output.parent.is_symlink():
            raise ValueError(f'Папка transcription не должна быть символической ссылкой: {output.parent}')
        jobs.append(dict(id=len(jobs), source=str(source), relative=str(source.relative_to(root)),
                         output=str(output), status='skipped' if output.exists() else 'pending',
                         stage='Уже есть TXT' if output.exists() else 'В очереди', percent=0, error='', warnings=[]))
        report("checking", checked=len(jobs), total=len(sources))
    report("checking", checked=len(jobs), total=len(sources), force=True)
    return jobs


def discard(path):
    # A flaky volume must not abort the whole queue over a hidden temp file.
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


def audio_duration(path):
    result = subprocess.run([ffmpeg(), '-nostdin', '-hide_banner', '-i', str(path)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, errors='replace', timeout=30)
    match = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', result.stderr)
    if not match:
        raise ValueError('Не удалось прочитать длительность аудио. Проверьте, что файл не повреждён.')
    return int(match[1]) * 3600 + int(match[2]) * 60 + float(match[3])


class Batch:
    def __init__(self):
        self.lock = threading.RLock()
        self.cancelled = threading.Event()
        self.thread = None
        self.state = dict(phase='idle', message='Выберите папку с записями.', folder='', jobs=[], plan=None, active=0)
        self.active = {}

    def view(self, offset=None, limit=100):
        with self.lock:
            if offset is None:
                return deepcopy(self.state)
            jobs = self.state['jobs']
            page = {key: value for key, value in self.state.items() if key != 'jobs'}
            page['jobs'] = jobs[offset:offset + limit]
            page['total'] = len(jobs)
            page['completed'] = sum(j['status'] in {'done', 'skipped'} for j in jobs)
            page['failed'] = sum(j['status'] == 'error' for j in jobs)
            page['pending'] = sum(j['status'] == 'pending' for j in jobs)
            page['active_jobs'] = [j for j in jobs if j['status'] == 'running'][:5]
            completed = [j for j in jobs if j['status'] == 'done']
            recent = [j for j in jobs if j['status'] in {'done', 'error', 'cancelled'}]
            page['recent'] = sorted(recent, key=lambda j: j.get('finished_at', 0), reverse=True)[:10 - len(page['active_jobs'])]
            page['duration'] = sum(j.get('duration', 0) for j in jobs)
            page['eta'] = (sum(j.get('result', {}).get('elapsed', 0) for j in completed) / max(1, len(completed))
                           * (page['pending'] + self.state['active']) / max(1, (self.state.get('plan') or {}).get('parallel', 1)))
            page['progress'] = sum(100 if j['status'] in {'done', 'skipped', 'error'} else j['percent'] for j in jobs) / max(1, len(jobs))
            return deepcopy(page)

    def result_path(self, identity):
        with self.lock:
            job = self.state['jobs'][identity]
            if job['status'] not in {'done', 'skipped'}:
                raise ValueError('Результат ещё не готов.')
            return job['output']

    def update(self, **values):
        with self.lock:
            if values.get('message') and values['message'] != self.state['message']:
                self.state['events'] = [dict(time=time.strftime('%H:%M:%S'), text=values['message'])] + self.state.get('events', [])[:9]
            self.state.update(values)

    def start(self, folder, parallel="auto"):
        validate_parallel(parallel)
        with self.lock:
            if self.thread and self.thread.is_alive():
                raise ValueError('Обработка уже запущена. Дождитесь завершения или нажмите «Остановить».')
            jobs = discover(folder)
            if not jobs:
                raise ValueError('Аудиофайлы не найдены. Выберите папку с MP3 или WAV.')
            self.cancelled.clear()
            self.state = dict(phase='preparing', message='Проверка ресурсов и записей…',
                              folder=str(Path(folder).expanduser().resolve()), jobs=jobs, plan=None, active=0, mode=parallel)
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()

    def cancel(self):
        self.cancelled.set()
        self.update(message='Остановка. Готовые TXT сохраняются…')

    def _read(self, job, process, tail):
        for line in process.stdout:
            if line.startswith('CALL_EVENT '):
                try:
                    event = json.loads(line[len('CALL_EVENT '):])
                    with self.lock:
                        if event['event'] == 'progress':
                            job.update(stage=event['stage'], percent=event['percent'])
                        elif event['event'] == 'done':
                            job.update(result=event, percent=100, warnings=event['warnings'])
                        elif event['event'] == 'error':
                            job['error'] = event['message']
                except (KeyError, ValueError):
                    tail.append(line.strip())
            else:
                tail.append(line.strip())
        process.stdout.close()

    def _launch(self, job, models, workspace, threads):
        env = dict(os.environ, OMP_NUM_THREADS=str(threads), MKL_NUM_THREADS=str(threads), OPENBLAS_NUM_THREADS='1')
        # Keep the source checkout importable when CLI callers run elsewhere.
        package_root = str(Path(__file__).resolve().parent.parent)
        env['PYTHONPATH'] = package_root + os.pathsep + env.get('PYTHONPATH', '')
        command = [sys.executable, '-m', 'call_transcriber.worker', job['source'], job['output'], str(models),
                   workspace, '--threads', str(threads)]
        partial = str(Path(job['output']).parent / ('.transcription-' + uuid.uuid4().hex + '.part'))
        command += ['--partial', partial]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding='utf-8', errors='replace', env=env, start_new_session=True)
        tail = deque(maxlen=12)
        reader = threading.Thread(target=self._read, args=(job, process, tail), daemon=True)
        with self.lock:
            job.update(status='running', stage='Загрузка моделей', percent=0)
        reader.start()
        self.active[job['id']] = dict(process=process, reader=reader, job=job, peak=0, tail=tail, partial=partial)

    def _stop_active(self):
        for entry in self.active.values():
            process = entry['process']
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        for entry in self.active.values():
            process = entry['process']
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=5)
            # A decoder child may outlive its worker; reap the entire owned process group.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            entry['reader'].join(timeout=2)
            discard(entry['partial'])
            with self.lock:
                entry['job'].update(status='cancelled', stage='Остановлено')
        self.active.clear()

    def _run(self):
        try:
            self._execute()
        except Exception as error:
            # Always leave a terminal phase, or the UI stays locked on a dead queue.
            try:
                self._stop_active()
            finally:
                with self.lock:
                    for job in self.state['jobs']:
                        if job['status'] == 'pending':
                            job.update(status='cancelled', stage='Не запущено')
                        elif job['status'] == 'running':
                            job.update(status='cancelled', stage='Остановлено')
                self.update(phase='cancelled' if self.cancelled.is_set() else 'error', active=0, message=str(error))

    def _execute(self):
        pending = [job for job in self.state['jobs'] if job['status'] == 'pending']
        if not pending:
            self.update(phase='done', message='Все расшифровки уже есть. Существующие TXT сохранены.')
            return
        resources = snapshot()
        initial = plan(resources, len(pending), parallel=self.state.get("mode", "auto"))
        self.update(plan=initial)
        if initial['parallel'] == 0:
            raise RuntimeError('Недостаточно свободной памяти для одной записи. Закройте тяжёлые приложения и повторите. ' + initial['reason'])
        def model_progress(message):
            if self.cancelled.is_set():
                raise InterruptedError('Остановлено. Загрузку можно повторить.')
            self.update(message=message)
        models = ensure_models(model_progress)
        for job in pending:
            if self.cancelled.is_set():
                break
            try:
                job['duration'] = audio_duration(job['source'])
                estimate = int(job['duration'] * 32000 * 2) + 100 * 1024 ** 2
                if shutil.disk_usage(Path(job['source']).parent).free < estimate:
                    raise ValueError('Недостаточно свободного места рядом с записью.')
            except Exception as error:
                with self.lock:
                    job.update(status='error', stage='Ошибка файла', error=str(error))
        pending = deque(job for job in pending if job['status'] == 'pending')
        peak = 0
        calibrated = False
        limit = 1
        threads = initial['threads']
        with tempfile.TemporaryDirectory(prefix='call-queue-') as workspace:
            while pending or self.active:
                if self.cancelled.is_set():
                    self._stop_active()
                    for job in pending:
                        job.update(status='cancelled', stage='Не запущено')
                    self.update(phase='cancelled', active=0, message='Остановлено. Готовые TXT сохранены; можно запустить папку повторно.')
                    return
                for identity, entry in list(self.active.items()):
                    process = entry['process']
                    try:
                        measured = psutil.Process(process.pid)
                        rss = measured.memory_info().rss
                        for child in measured.children(recursive=True):
                            try:
                                rss += child.memory_info().rss
                            except psutil.Error:
                                pass
                        entry['peak'] = max(entry['peak'], rss)
                        entry['rss'] = rss
                    except psutil.Error:
                        pass
                    code = process.poll()
                    if code is not None:
                        entry['reader'].join(timeout=3)
                        discard(entry['partial'])
                        job = entry['job']
                        peak = max(peak, entry['peak'])
                        with self.lock:
                            success = code == 0 and 'result' in job and Path(job['output']).is_file()
                            job.update(status='done' if success else 'error', stage='Готово' if success else 'Ошибка', peak_rss=entry['peak'], finished_at=time.time())
                            self.state['events'] = [dict(time=time.strftime('%H:%M:%S'), text=job['relative'] + (': готово' if success else ': ошибка'))] + self.state.get('events', [])[:9]
                            if not success and not job['error']:
                                job['error'] = '\n'.join(entry['tail'])[-1500:] or f'Процесс завершился с кодом {code}'
                        del self.active[identity]
                        if success and not calibrated:
                            calibrated = True
                            longest = max((j['duration'] for j in pending), default=0)
                            selected = plan(snapshot(), len(pending) or 1, peak, longest, self.state.get("mode", "auto"))
                            limit = max(1, selected['parallel'])
                            threads = selected['threads']
                            selected['measured_peak_gb'] = round(peak / GIB, 2)
                            self.update(plan=selected)
                current = snapshot(0)
                current.available -= sum(max(0, worker_memory(peak, entry['job'].get('duration', 0)) - entry.get('rss', 0))
                                         for entry in self.active.values())
                # Stop admission under pressure; do not kill healthy work or discard completed results.
                while pending and len(self.active) < limit:
                    next_job = pending[0]
                    needed = worker_memory(peak, next_job.get('duration', 0))
                    if current.available - reserve_bytes(current) < needed:
                        break
                    if shutil.disk_usage(workspace).free < next_job.get('duration', 0) * 64000 + GIB:
                        raise RuntimeError('Недостаточно места для временного WAV. Освободите место и повторите.')
                    self._launch(pending.popleft(), models, workspace, threads)
                    # Reserve the full footprint immediately, before the new process actually allocates it.
                    current.available -= needed
                message = ('Первая запись: измеряем расход памяти…' if not calibrated else
                           f'Обработка: до {limit} записей одновременно. Память проверяется перед каждым запуском.')
                waiting = bool(pending) and not self.active
                if waiting:
                    message = 'Ожидаем свободную память. Очередь сохранена; закройте тяжёлые приложения или нажмите «Остановить».'
                self.update(phase='waiting' if waiting else 'running', active=len(self.active), message=message)
                time.sleep(.4)
        failed = sum(j['status'] == 'error' for j in self.state['jobs'])
        self.update(phase='done', active=0, message=f'Обработка завершена. Ошибок: {failed}.' if failed else 'Готово. TXT сохранены в папках transcription рядом с записями.')
