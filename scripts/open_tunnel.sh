#!/usr/bin/env bash
# Forward a remote Colab port to 127.0.0.1 on the local machine via google-colab-cli.
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

if [ ! -f "$HOME/.ssh/id_ed25519" ] && [ ! -f "$HOME/.ssh/id_ecdsa" ]; then
  mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
  ssh-keygen -t ed25519 -N "" -f "$HOME/.ssh/id_ed25519" >/dev/null
fi

echo "Forwarding http://127.0.0.1:${LOCAL_PORT} -> Colab(${SESSION}):${REMOTE_PORT} ..."
exec ssh -N -T -F /dev/null \
  -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 \
  -o StrictHostKeyChecking=no \
  -o UserKnownHostsFile=/dev/null \
  -o LogLevel=ERROR \
  -o BatchMode=yes \
  -o ConnectTimeout=60 \
  -o ProxyCommand="${COLAB_BIN} ${CONFIG_ARG} ssh --proxy-mode -s ${SESSION}" \
  -L "127.0.0.1:${LOCAL_PORT}:127.0.0.1:${REMOTE_PORT}" \
  root@colab-runtime
