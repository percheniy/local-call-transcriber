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
