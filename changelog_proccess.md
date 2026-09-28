# Implementation decisions

- Initial choice: official GigaAM v3 E2E RNNT and NVIDIA streaming Sortformer v2.1, sequential local inference, CPU baseline, isolated Python environment. Preserve Sortformer speaker identity across the complete recording. Align ASR words by overlap with diarized turns; never force extra detected voices into two identities.
- Validation contract: run both actual models on a Russian two-voice MP3, verify speaker labels and transcript, record time and memory. User-call accuracy requires a supplied recording.
- Supplied user recording replaced the synthetic fixture as acceptance input. Full 287.65-second MP3 passed CPU inference in 43.69 seconds wall time, 2,519,924,736-byte maximum RSS, 37 segments / 894 words / exactly two speaker labels. Timestamp range assertions, dependency compatibility, model checksums, and four alignment tests passed.
- Offline MPS smoke test passed under macOS sandbox network denial on a 35-second excerpt. Architecture unchanged; CPU remains the default. No inference failures or architecture reversals occurred.
- Offline CPU check passed on the same 35-second excerpt: 15.34 seconds wall versus 25.95 seconds for MPS. Both outputs retain two speakers. CPU default is supported by this measurement.

## Folder UI delivery

- Architecture: keep inference alignment; isolate recordings in short-lived processes, measure a first-file pilot, admit one to five workers based on current resources, publish atomic TXT only. A token-protected loopback server serves a simple UI. Distribution uses locked uv installations or Linux CPU containers.
- Actual mixed-folder acceptance passed for one MP3 and two WAV recordings at three directory levels, two speakers each, no JSON outputs.
- User additions require step-by-step and AI manuals, WAV, and measured memory stability on large queues. UI pagination and bounded process lifetime address queue-scale memory.
- Browser tool failure: shared Chrome caches failed signature verification. Isolated installation also retained an invalid signature; repairing the isolated app signature is the next diagnostic correction. Shared caches remain untouched.
- Memory soak exposed transient host-pressure failure after three completed files: admission control ended the queue when free memory briefly dropped. This violates resilient large-queue handling. Keep the architecture and reserve unchanged; pause new admissions and retain the queue until memory returns or the user cancels. Peak parent memory did not grow and no workers survived the initial stop.

- Latest UI corrections: remove the full queue/browser modal; use native OS directory selection, bounded ten-record history, and auto/manual 1–5 admission. Manual mode retains memory reservation and first-file calibration. Container selection maps a transient browser-created marker inside the mounted root without audio uploads.
- Container ARM check failed on missing libgomp.so.1; install the required libgomp1 runtime library without changing the locked model dependencies.
- Container ARM imports now pass. Actual inference revealed an unwritable Numba cache under the root-owned environment when running as the non-root app user; direct its JIT cache to /tmp/numba. Keep non-root execution and the same real MP3/WAV acceptance.
- Cancellation cleanup now terminates the dedicated worker process group, including a running FFmpeg child. This closes a concrete orphan-decoder case while retaining per-recording process isolation. Native supported platforms and containers are POSIX.

- Folder selection now immediately streams indexing progress and audio counts. Discovery uses its existing recursive traversal with throttled progress callbacks; unknown directory totals use indeterminate progress, followed by measured result checks. No second pre-count pass or simulated percentage.

## README video (play button)

- Requirement: README video with a play button, per the user's `[![preview](img)](user-attachments URL)` pattern.
- A: preview image linked to the uploaded attachment. GitHub replaces it with its native inline player, which has play controls.
- B: the same preview linked to the repository `blob/main/media/demo.mp4` page. It was rejected because GitHub does not play the file there, and `raw` serves `application/octet-stream`, which downloads the file. B violated the "play" requirement.
- Returned to A; this is not an oscillation. A is final because it is the only link that actually plays for visitors. Do not switch again.

## Background matrix copy

- Requirement: replace meaningless matrix glyphs with readable background lines supplied by the user (pipeline-flavoured system messages, jokes, continuation series, rare Matrix easter eggs, dynamic templates).
- Decision: horizontal typed lines on the same black/red canvas. Copy lives in `web/matrix-lines.js` (single lines and series; tech log ≈70%, humor ≈25%, eggs every 30–60 s). Lines are placed only in areas the panel leaves visible and wrapped to that width; shuffle bags avoid repeats.
- Browser check found two placement defects: an unrelated line could sit directly under a series, and right-hand lines ran under the scrollbar. Fixed with a blank-row gap between messages and the `clientWidth` right edge. No reversals.

## Token without the link fragment

- Defect: opening `http://127.0.0.1:<port>/` without `#token` (new tab, bookmark, typed address) sent no token, so every API call returned 401 «Откройте ссылку, напечатанную в терминале при запуске.» and folder selection failed.
- Fix: the server embeds the token in the served page, only after the existing loopback Host/Origin check; app.js prefers it over the fragment. Cross-site pages still cannot read the page or call the API. Verified: bare URL loads without errors, API without token still returns 401, new test covers the foreign Host rejection.

## Queue frozen after a disk I/O error

- Defect: on a large queue on an external drive, the volume returned `Errno 5` while a finished worker's hidden `.part` file was being removed. The exception went to `_run`, whose handler removed the same kind of file again and raised a second error. The batch thread died with the state still `running`: «Остановить» only set a flag that nothing read, and «Расшифровать» stayed disabled. Only a server restart helped.
- Fix: temp `.part` removal is best-effort (`discard`), and the `_run` error handler reaches a terminal phase in `finally` even if process cleanup fails, marking pending/running jobs cancelled. Queue architecture unchanged.
- Verified: two new tests fail on the previous code (`'running' != 'done'`, `'preparing' != 'error'`) and pass now; the full suite passes (23 tests). Live server on :57205 was relaunched; start → cancel through the API reached `cancelled` with no workers left.
