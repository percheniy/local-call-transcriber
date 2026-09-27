"""Runtime assets and bundled FFmpeg discovery."""
import hashlib
import os
from pathlib import Path
import shutil
import urllib.request

from filelock import FileLock
from platformdirs import user_cache_dir

GIB = 1024 ** 3
MODEL_FILES = {
    "sortformer.nemo": (
        "https://huggingface.co/nvidia/diar_streaming_sortformer_4spk-v2.1/resolve/cd03eee90fbec18297ac31b8c21546e596b7f71c/diar_streaming_sortformer_4spk-v2.1.nemo",
        "8abd32832159c6ac1148c926b7276f35ba34582c444e559dce1f1253fea42ef8"),
    "v3_e2e_rnnt.ckpt": (
        "https://cdn.chatwm.opensmodel.sberdevices.ru/GigaAM/v3_e2e_rnnt.ckpt",
        "f60c62fe45902d967000770a12f260de7c5ac4d4b8e5e852f1df8c548e3958b5"),
    "v3_e2e_rnnt_tokenizer.model": (
        "https://cdn.chatwm.opensmodel.sberdevices.ru/GigaAM/v3_e2e_rnnt_tokenizer.model",
        "828c12c991019eef952a960661f25a92d6ad279591e2ea466b4aeddf1d20a18a"),
}


def model_directory():
    override = os.environ.get("CALL_TRANSCRIBER_MODELS")
    if override:
        return Path(override).expanduser().resolve()
    local = Path(__file__).resolve().parent.parent / "models"
    if local.is_dir():
        return local
    return Path(user_cache_dir("local-call-transcriber")) / "models"


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def ensure_models(progress=lambda message: None):
    directory = model_directory()
    directory.mkdir(parents=True, exist_ok=True)
    with FileLock(str(directory / ".download.lock"), timeout=3600):
        for name, (url, expected) in MODEL_FILES.items():
            target = directory / name
            if target.exists():
                progress(f"Проверка модели: {name}")
                if digest(target) != expected:
                    raise RuntimeError(f"Нарушена контрольная сумма {target}. Переместите повреждённый файл и повторите запуск.")
                continue
            if shutil.disk_usage(directory).free < 2 * GIB:
                raise RuntimeError("Для загрузки моделей нужно не менее 2 ГБ свободного места.")
            partial = directory / (name + ".part")
            try:
                with urllib.request.urlopen(url, timeout=60) as response, partial.open("wb") as handle:
                    total = int(response.headers.get("Content-Length", 0))
                    downloaded = 0
                    for chunk in iter(lambda: response.read(1024 * 1024), b""):
                        handle.write(chunk)
                        downloaded += len(chunk)
                        amount = f"{downloaded // 1024 ** 2} МБ"
                        progress(f"Загрузка {name}: {amount}" + (f" / {total // 1024 ** 2} МБ" if total else ""))
                if digest(partial) != expected:
                    raise RuntimeError(f"Контрольная сумма загруженного {name} не совпала. Повторите запуск.")
                partial.replace(target)
            finally:
                partial.unlink(missing_ok=True)
    return directory


def ffmpeg():
    configured = os.environ.get("IMAGEIO_FFMPEG_EXE")
    if configured:
        return configured
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def prepare_ffmpeg_path(workspace):
    # GigaAM invokes the name `ffmpeg`; provide its bundled binary without system installation.
    directory = Path(workspace) / "bin"
    directory.mkdir(exist_ok=True)
    target = directory / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if not target.exists():
        try:
            target.symlink_to(ffmpeg())
        except OSError:
            shutil.copy2(ffmpeg(), target)
    os.environ["PATH"] = str(directory) + os.pathsep + os.environ.get("PATH", "")
