"""Sequential local Sortformer and GigaAM inference inside an isolated worker."""
import gc
import os
from pathlib import Path
import subprocess
import tempfile
import time
from .alignment import parse_turns, speech_regions, label_word, group_words, timestamp
from .runtime import ffmpeg

RATE = 16000
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("WANDB_MODE", "disabled")


def transcribe_file(source, output, model_dir, threads, progress, workspace, partial):
    import numpy as np
    import soundfile as sf
    import torch

    torch.set_num_threads(threads)
    torch.set_num_interop_threads(1)
    source, output, model_dir = Path(source), Path(output), Path(model_dir)
    if output.exists():
        raise FileExistsError(f"Результат уже существует: {output}")
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="audio-", dir=workspace) as temp:
        wav = Path(temp) / "audio.wav"
        progress("Подготовка аудио", 2)
        subprocess.run([ffmpeg(), "-nostdin", "-v", "error", "-i", str(source),
                        "-vn", "-ac", "1", "-ar", str(RATE), "-c:a", "pcm_s16le", str(wav)], check=True)
        duration = sf.info(wav).duration
        if duration <= 0:
            raise ValueError("Пустая запись")
        progress("Определение говорящих", 8)
        from nemo.collections.asr.models import SortformerEncLabelModel

        diar = SortformerEncLabelModel.restore_from(str(model_dir / "sortformer.nemo"), map_location="cpu")
        diar.eval()
        diar.sortformer_modules.chunk_len = 340
        diar.sortformer_modules.chunk_right_context = 40
        diar.sortformer_modules.fifo_len = 40
        diar.sortformer_modules.spkcache_update_period = 300
        with torch.inference_mode():
            prediction = diar.diarize(audio=[str(wav)], batch_size=1, num_workers=0)
        turns = parse_turns(prediction[0])
        del diar, prediction
        gc.collect()
        diar_seconds = time.monotonic() - started
        speaker_count = len({t["speaker"] for t in turns})
        warnings = []
        if speaker_count != 2:
            warnings.append(f"Sortformer обнаружил говорящих: {speaker_count}; ожидалось 2. Проверьте разметку.")
        words = []
        progress("Распознавание речи", 35)
        if turns:
            import gigaam

            asr = gigaam.load_model("v3_e2e_rnnt", download_root=str(model_dir),
                                    device="cpu", fp16_encoder=False)
            regions = speech_regions(turns, duration)
            windows = []
            with sf.SoundFile(wav) as audio:
                for region_start, region_end in regions:
                    start = region_start
                    while start < region_end:
                        end = min(start + 22, region_end)
                        if end < region_end:
                            # Prefer a quiet 100 ms interval near the chunk boundary.
                            search_start = end - 2
                            audio.seek(int(search_start * RATE))
                            tail = audio.read(2 * RATE, dtype="float32")
                            blocks = tail[:len(tail) // 1600 * 1600].reshape(-1, 1600)
                            end = search_start + (int(np.argmin(np.mean(blocks ** 2, axis=1))) + .5) * .1
                        windows.append((start, end))
                        start = end
                for index, (start, end) in enumerate(windows):
                    # Context reduces clipped words; midpoint ownership removes duplicates.
                    clip_start, clip_end = max(0, start - .5), min(duration, end + .5)
                    audio.seek(int(clip_start * RATE))
                    samples = audio.read(int((clip_end - clip_start) * RATE), dtype="float32")
                    clip = Path(temp) / "chunk.wav"
                    sf.write(clip, samples, RATE)
                    result = asr.transcribe(str(clip), word_timestamps=True)
                    if result.text.strip() and not result.words:
                        raise RuntimeError("GigaAM вернул текст без временных меток слов")
                    for word in result.words or []:
                        word_start = max(0, clip_start + word.start)
                        word_end = min(duration, clip_start + word.end)
                        midpoint = (word_start + word_end) / 2
                        if not start <= midpoint < end:
                            continue
                        speaker, overlap = label_word(word_start, word_end, turns)
                        words.append(dict(start=round(word_start, 3), end=round(word_end, 3),
                                          speaker=speaker, text=word.text, overlap=overlap))
                    progress(f"Распознавание: {index + 1}/{len(windows)}", 35 + 60 * (index + 1) / len(windows))
            del asr
        segments = group_words(words)
        elapsed = time.monotonic() - started
        lines = [f"[{timestamp(s['start'])}–{timestamp(s['end'])}] {s['speaker']}: {s['text']}" for s in segments]
        if not lines:
            lines = ["Речь не обнаружена."]
        output.parent.mkdir(parents=True, exist_ok=True)
        # Publish atomically without replacing another process's or user's result.
        try:
            with open(partial, "x", encoding="utf-8") as handle:
                handle.write("\n\n".join(lines) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.link(partial, output)
        finally:
            Path(partial).unlink(missing_ok=True)
        progress("Готово", 100)
        return dict(duration=duration, elapsed=round(elapsed, 2), speakers=speaker_count,
                    warnings=warnings, words=len(words), segments=len(segments))
