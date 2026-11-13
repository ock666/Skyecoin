#!/usr/bin/env bash
#
# Deploy a checked-out Skyecoin tree to the live Unraid appdata dir.
# Runs inside the Jenkins container; the deploy dir is bind-mounted at the same
# path as on the host, and the Docker socket is mounted.
#
# Usage: deploy.sh <source-workspace> <deploy-dir> <health-url> [compose-profile]
set -euo pipefail

SRC="${1:?usage: deploy.sh <source-workspace> <deploy-dir> <health-url> [compose-profile]}"
DEST="${2:?}"
HEALTH="${3:?}"
PROFILE="${4:-}"

[ -d "$DEST" ] || { echo "deploy dir missing: $DEST"; exit 1; }

# Clear the deploy dir as root in a throwaway container so files written by
# other UIDs (app-side data syncs, previous root builds) can be replaced.
docker run --rm -v "$DEST:/dest" alpine:3.20 sh -c '
  cd /dest
  for f in * .[!.]*; do
    case "$f" in
      .|..|.env|.git|docker-compose.override.yml|scripts) continue ;;
    esac
    rm -rf -- "$f"
  done
'

tar -C "$SRC" \
  --exclude=./.git \
  --exclude=./node_modules \
  --exclude=./dist \
  --exclude=./build \
  --exclude=./data \
  --exclude=./__pycache__ \
  --exclude='*.pyc' \
  --exclude=./.venv \
  --exclude=./venv \
  --exclude=./tests \
  --exclude=./.pytest_cache \
  --exclude='*.egg-info' \
  -cf - . | tar -C "$DEST" -xf -

cd "$DEST"
docker compose $PROFILE up -d --build --wait --wait-timeout 180

for _ in $(seq 1 30); do
  if curl -fsS --max-time 3 "$HEALTH" >/dev/null; then
    echo "[deploy] healthy: $HEALTH"
    exit 0
  fi
  sleep 2
done

echo "[deploy] health check failed; recent logs:"
docker compose $PROFILE logs --tail 60 || true
exit 1
