"""One recording per process; progress protocol stays separate from library logging."""
import argparse
import json
import traceback
from .runtime import prepare_ffmpeg_path


def emit(event, **values):
    print("CALL_EVENT " + json.dumps(dict(event=event, **values), ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('source')
    parser.add_argument('output')
    parser.add_argument('models')
    parser.add_argument('workspace')
    parser.add_argument('--threads', type=int, required=True)
    parser.add_argument('--partial', required=True)
    args = parser.parse_args()
    try:
        prepare_ffmpeg_path(args.workspace)
        from .engine import transcribe_file
        result = transcribe_file(args.source, args.output, args.models, args.threads,
                                 lambda stage, percent: emit('progress', stage=stage, percent=percent), args.workspace, args.partial)
        emit('done', **result)
    except Exception as error:
        traceback.print_exc()
        emit('error', message=str(error))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
