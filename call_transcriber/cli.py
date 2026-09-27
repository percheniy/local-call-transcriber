"""Folder queue for terminal users."""
import argparse
import time
from .batch import Batch


def main():
    parser = argparse.ArgumentParser(description='Рекурсивная обработка папки MP3/WAV, автоматически 1–5 задач.')
    parser.add_argument('folder')
    args = parser.parse_args()
    batch = Batch()
    batch.start(args.folder)
    previous = None
    try:
        while batch.thread.is_alive():
            state = batch.view()
            text = state['message'] + '\n' + '\n'.join(f"  {j['relative']}: {j['stage']}" for j in state['jobs'])
            if text != previous:
                print(text, flush=True)
                previous = text
            time.sleep(1)
    except KeyboardInterrupt:
        batch.cancel()
        batch.thread.join()
    state = batch.view()
    print(state['message'])
    for job in state['jobs']:
        if job['error']:
            print(job['relative'] + ': ' + job['error'])
    raise SystemExit(1 if state['phase'] != 'done' or any(j['status'] == 'error' for j in state['jobs']) else 0)
