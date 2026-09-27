# Local Call Transcriber

Локальная расшифровка русских звонков: **GigaAM v3 E2E RNNT + Sortformer v2.1**. Выберите папку в интерфейсе: приложение обработает MP3 и WAV, включая подпапки, и сохранит диалоги с метками `speaker 1` и `speaker 2`.

[![Видео: Local Call Transcriber за 22 секунды](media/demo.jpg)](media/demo.mp4)

*Ролик сгенерирован автоматически с помощью ИИ.*

- Автоматически от 1 до 5 одновременных записей по свободной памяти, загрузке CPU и измеренному расходу первой записи.
- В каждой папке с аудио создаётся `transcription`. Сохраняется только TXT; исходники не изменяются.
- Готовые результаты пропускаются, ошибки отдельных записей не прерывают остальные.
- После установки моделей аудио обрабатывается локально, без API-ключей.

## Одна команда для запуска

**macOS Apple Silicon и Linux x86-64 / ARM64** — вставьте строку в терминал:

```sh
installer=$(mktemp) && curl -fsSL https://raw.githubusercontent.com/percheniy/local-call-transcriber/v1.0.0/install.sh -o "$installer" && sh "$installer"
```

Установщик загрузит `uv`, Python 3.11, зависимости, FFmpeg и модели, затем откроет браузер. Первый запуск требует интернета и нескольких минут. [Пошаговый manual](MANUAL.md) объясняет повторный и офлайн-запуск.

**Windows, Intel Mac, Linux и Apple Silicon с Docker** — откройте терминал в папке звонков и выполните:

```sh
docker run --rm -it -p 127.0.0.1:18765:18765 --mount type=bind,source=.,target=/calls --mount type=volume,source=call-transcriber-models,target=/models $(docker build -q https://github.com/percheniy/local-call-transcriber.git#v1.0.0)
```

Одна строка работает в PowerShell и POSIX shell. Сначала Docker собирает приложение из публичного репозитория, затем запускает его. Откройте полную ссылку из терминала, включая `#…`, и нажмите «Выбрать папку»: в Chrome или Edge откроется системное окно. Выберите подключённую папку звонков; контейнер сопоставит её с `/calls`. Требуется работающий Docker Desktop / Engine с Linux-контейнерами и минимум 8 ГБ выделенной RAM.

Поддержка «любого компьютера» ограничена современными 64-битными настольными ОС и достаточными ресурсами: рекомендуется 8+ ГБ RAM, от 5 ГБ свободного диска для native-установки и 10 ГБ для Docker. Пять процессов требуют больше ресурсов. CUDA не нужна. Для Windows и Intel macOS предусмотрен Docker; нативный запуск на них не заявляется.

## Документация

- **[MANUAL.md](MANUAL.md)** — step-by-step guide для человека.
- **[AI_INSTALL.md](AI_INSTALL.md)** — установка под ключ через Claude Code или Codex.
- **[VALIDATION.md](VALIDATION.md)** — проверки и ограничения.

## Результаты

```text
Звонки/разговор.mp3             → Звонки/transcription/разговор.mp3.txt
Звонки/Отдел/разговор.wav       → Звонки/Отдел/transcription/разговор.wav.txt
```

Пример формата (иллюстративный текст):

```text
[00:00:03–00:00:06] speaker 1: Здравствуйте, хочу уточнить время встречи.

[00:00:07–00:00:10] speaker 2: Добрый день. Встреча завтра в десять.
```

Говорящие нумеруются заново для каждого звонка. При количестве голосов, отличном от двух, показывается предупреждение. Sortformer поддерживает до четырёх голосов. Шум и одновременная речь могут приводить к ошибкам.

## Из исходников

```sh
git clone https://github.com/percheniy/local-call-transcriber.git
cd local-call-transcriber
./setup.sh
./ui
```

Очередь из терминала: `./transcribe "/путь/к/папке"`.
Тесты: `uv run python -m unittest discover -s tests -v`.

Источники моделей: [GigaAM](https://github.com/salute-developers/GigaAM) (MIT), [Sortformer v2.1](https://huggingface.co/nvidia/diar_streaming_sortformer_4spk-v2.1) (NVIDIA Open Model License). Код приложения — MIT. Веса скачиваются из официальных источников и проверяются по SHA-256. [uv](https://docs.astral.sh/uv/) управляет Python; [imageio-ffmpeg](https://pypi.org/project/imageio-ffmpeg/) поставляет FFmpeg.

**Автор: [percheniy](https://github.com/percheniy) · [gridchin.ru](https://gridchin.ru) · [t.me/gridchin](https://t.me/gridchin).** При модернизации сохраняйте видимое указание автора в продукте и документации; при fork указывайте **percheniy в соавторах**. [Обязательная процедура, включая ИИ-агентов](ATTRIBUTION.md) · [Авторы](AUTHORS.md).
