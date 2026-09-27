"""System directory selection without uploading audio to the browser."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys


def choose_folder():
    if sys.platform == 'darwin':
        command = ['osascript', '-e', 'try', '-e', 'POSIX path of (choose folder with prompt "Выберите папку со звонками")', '-e', 'on error number -128', '-e', 'return ""', '-e', 'end try']
    elif shutil.which('zenity'):
        command = ['zenity', '--file-selection', '--directory', '--title=Выберите папку со звонками']
    elif shutil.which('kdialog'):
        command = ['kdialog', '--getexistingdirectory', str(Path.home()), '--title', 'Выберите папку со звонками']
    else:
        command = [sys.executable, '-c', 'import tkinter as t; from tkinter.filedialog import askdirectory; r=t.Tk(); r.withdraw(); print(askdirectory(title="Выберите папку со звонками")); r.destroy()']
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired:
        raise ValueError("Время выбора папки истекло. Нажмите «Выбрать папку» ещё раз.") from None
    if result.returncode and result.returncode != 1:
        raise ValueError('Не удалось открыть системное окно выбора папки: ' + result.stderr.strip()[-500:])
    if result.returncode == 1 and result.stderr.strip():
        raise ValueError('Установите zenity или tkinter для системного выбора папки. ' + result.stderr.strip()[-200:])
    value = result.stdout.strip()
    return str(Path(value).resolve(strict=True)) if value else None


def mounted_folder(nonce, root='/calls'):
    if not isinstance(nonce, str) or not re.fullmatch('[a-f0-9]{32}', nonce):
        raise ValueError('Неверный идентификатор выбора папки.')
    marker = '.call-transcriber-selection-' + nonce
    for directory, children, files in os.walk(root, followlinks=False):
        children[:] = [name for name in children if not (Path(directory) / name).is_symlink()]
        candidate = Path(directory) / marker
        if marker in files and not candidate.is_symlink() and candidate.stat().st_size == 32:
            if candidate.read_text() == nonce:
                return str(Path(directory).resolve())
    raise ValueError('Выберите папку внутри каталога, подключённого к контейнеру как /calls.')
