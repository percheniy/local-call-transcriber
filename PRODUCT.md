# Product
<!-- impeccable:product-schema 1 -->

## Platform
web

## Users
People transcribing local Russian call recordings, including nontechnical users.

## Product Purpose
Select a folder and receive speaker-labelled TXT files beside recordings, recursively.

## Capabilities and Constraints
GigaAM v3 and Sortformer. MP3 and WAV required. Adaptive concurrency of one to five processes. Local-only processing. No intermediate transcription JSON. Public distribution with human and AI installation manuals. The user explicitly requested a simple local interface; the existing implementation is Python.

## Operating Context
Desktop browser controlling a loopback Python process. Files stay local. Existing results must be preserved. Large queues must not retain model memory in the parent process.
