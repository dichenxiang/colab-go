#!/usr/bin/env bash
# Forward a remote Colab port to 127.0.0.1 on the local machine via google-colab-cli.
# On Windows, run this script inside WSL Ubuntu (where `colab` and `~/.ssh` live).
# Usage: bash open_tunnel.sh <session_name> <local_port> <remote_port> [colab_config_path]
set -euo pipefail

SESSION="${1:?Usage: open_tunnel.sh <session> <local_port> <remote_port> [config]}"
LOCAL_PORT="${2:-8000}"
REMOTE_PORT="${3:-8000}"
CONFIG_ARG=""
if [ -n "${4:-}" ]; then
  CONFIG_ARG="--config $4"
fi

COLAB_BIN="${COLAB_BIN:-$HOME/.local/bin/colab}"
if [ ! -x "$COLAB_BIN" ]; then
  COLAB_BIN="$(command -v colab)"
fi

mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"

# Pick a matching private+public Ed25519/ECDSA key pair, or generate a dedicated one.
KEY_FILE="${SSH_KEY:-}"
if [ -z "$KEY_FILE" ]; then
  if [ -f "$HOME/.ssh/id_ed25519" ] && [ -f "$HOME/.ssh/id_ed25519.pub" ]; then
    KEY_FILE="$HOME/.ssh/id_ed25519"
  elif [ -f "$HOME/.ssh/id_ecdsa" ] && [ -f "$HOME/.ssh/id_ecdsa.pub" ]; then
    KEY_FILE="$HOME/.ssh/id_ecdsa"
  elif [ -f "$HOME/.ssh/colab_ed25519" ] && [ -f "$HOME/.ssh/colab_ed25519.pub" ]; then
    KEY_FILE="$HOME/.ssh/colab_ed25519"
  else
    KEY_FILE="$HOME/.ssh/colab_ed25519"
    ssh-keygen -t ed25519 -N "" -f "$KEY_FILE" >/dev/null
  fi
fi

echo "Forwarding http://127.0.0.1:${LOCAL_PORT} -> Colab(${SESSION}):${REMOTE_PORT} (key: ${KEY_FILE}) ..."
exec ssh -N -T -F /dev/null \
  -i "$KEY_FILE" \
  -o IdentitiesOnly=yes \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -o StrictHostKeyChecking=no \
  -o UserKnownHostsFile=/dev/null \
  -o LogLevel=ERROR \
  -o BatchMode=yes \
  -o ConnectTimeout=60 \
  -o ProxyCommand="${COLAB_BIN} ${CONFIG_ARG} ssh --proxy-mode -i ${KEY_FILE} -s ${SESSION}" \
  -L "127.0.0.1:${LOCAL_PORT}:127.0.0.1:${REMOTE_PORT}" \
  root@colab-runtime
