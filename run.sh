#!/usr/bin/env bash
set -euo pipefail

case "${1:-generate}" in
  generate)
    python3 -m src.main generate
    ;;
  no-ai)
    python3 -m src.main no-ai
    ;;
  serve)
    cd docs
    bundle exec jekyll serve --host 127.0.0.1 --port 4000
    ;;
  *)
    echo "Usage: ./run.sh {generate|no-ai|serve}"
    exit 1
    ;;
esac
