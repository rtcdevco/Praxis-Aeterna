#!/usr/bin/env bash
set -e
MODE="${1:-}"

case "$MODE" in
  local)
    source .venv/bin/activate 2>/dev/null || true
    exec python -m uvicorn face.main:app --host 127.0.0.1 --port 8000 --reload
    ;;
  docker)
    docker build -t fable5-os .
    exec docker run --rm -p 8000:8000 --env-file .env \
      -v "$PWD/vault:/app/vault" -v "$PWD/skills:/app/skills" fable5-os
    ;;
  systemd)
    if [ "$(id -u)" -eq 0 ]; then
      echo "Run this as your normal user, not root — it uses sudo itself where needed." >&2
      exit 1
    fi
    sed "s|__DIR__|$PWD|g" deploy/fable5.service | sudo tee /etc/systemd/system/fable5.service >/dev/null
    sudo systemctl daemon-reload
    sudo systemctl enable --now fable5
    echo "Installed + started fable5.service"
    ;;
  *)
    echo "Usage: ./deploy.sh [local|docker|systemd]" >&2
    exit 1
    ;;
esac
