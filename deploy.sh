#!/bin/bash
set -e

SERVER="root@192.168.0.51"
REMOTE_DIR="/mnt/user/appdata/skyecoin"
KEY="$HOME/.ssh/id_rsa"
SSH_OPTS="-o StrictHostKeyChecking=accept-new -i $KEY"

echo "=== Skyecoin Deploy ==="
echo "Server: $SERVER"
echo "Target: $REMOTE_DIR"
echo ""

echo "[1/4] Testing SSH..."
ssh $SSH_OPTS -o ConnectTimeout=10 "$SERVER" "echo '  SSH OK'"

echo "[2/4] Creating remote directory..."
ssh $SSH_OPTS "$SERVER" "mkdir -p $REMOTE_DIR"

echo "[3/4] Syncing project files..."
rsync -avz --delete \
    --exclude '.git' \
    --exclude '.venv' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.pytest_cache' \
    --exclude 'data/skyecoin.db' \
    --exclude 'data/config.json' \
    -e "ssh $SSH_OPTS" \
    ./ "$SERVER:$REMOTE_DIR/"

echo "[4/4] Building and starting containers..."
ssh $SSH_OPTS "$SERVER" "cd $REMOTE_DIR && docker compose up -d --build"

echo ""
echo "Deploy complete!"
echo "  Web UI:   http://192.168.0.51:5000"
echo "  API Docs: http://192.168.0.51:5000/docs"
echo ""
echo "Miner (optional):"
echo "  ssh root@192.168.0.51 'cd $REMOTE_DIR && docker compose --profile miner up -d'"
echo ""
echo "View logs:"
echo "  ssh root@192.168.0.51 'cd $REMOTE_DIR && docker compose logs -f'"
