#!/usr/bin/env python3
"""
Remote Colab deployment script for GGUF LLMs via llama.cpp (OpenAI-compatible API).
Run on a Colab VM via:
  colab exec -s <session> --timeout 180 -f deploy_llm_remote.py
Configure via environment variables passed with `colab exec --env KEY=VAL`:
  LLM_PRESET   : t4-gemma12b | l4-qwen36-moe | l4-qwen38-27b | a100-qwen38-q4 | a100-qwen38-q8
  LLM_REPO     : (optional) custom Hugging Face repo ID
  LLM_FILE     : (optional) custom .gguf filename inside repo
  LLM_CTX      : (optional) context length override (e.g. 131072)
  LLM_PORT     : (optional) remote listen port (default: 8000)
  LLM_ALIAS    : (optional) model ID exposed in /v1/models
  LLM_MTP      : (optional) 1 to enable --spec-type draft-mtp, 0 to disable
  LLM_SLOTS    : (optional) parallel slots -np (default: 1)
"""
import os
import subprocess
import sys
import time
import urllib.request

LLAMA_TAG = "b12503"
LLAMA_URL = f"https://github.com/ggml-org/llama.cpp/releases/download/{LLAMA_TAG}/llama-{LLAMA_TAG}-bin-ubuntu-cuda-12.8-x64.tar.gz"
CUDART_URL = f"https://github.com/ggml-org/llama.cpp/releases/download/{LLAMA_TAG}/cudart-llama-{LLAMA_TAG}-bin-ubuntu-cuda-12.8-x64.tar.gz"

PRESETS = {
    "t4-gemma12b": {
        "repo": "bartowski/mlabonne_gemma-3-12b-it-abliterated-GGUF",
        "file": "mlabonne_gemma-3-12b-it-abliterated-Q4_K_M.gguf",
        "ctx": [32768, 16384],
        "alias": "gemma-3-12b-abliterated",
        "mtp": False,
    },
    "l4-qwen36-moe": {
        "repo": "mradermacher/Qwen3.6-35B-A3B-abliterated-i1-GGUF",
        "file": "Qwen3.6-35B-A3B-abliterated.i1-IQ4_XS.gguf",
        "ctx": [131072, 65536, 32768],
        "alias": "qwen3.6-35b-a3b-abliterated",
        "mtp": False,
    },
    "l4-qwen38-27b": {
        "repo": "mradermacher/Huihui-Qwen3.8-27B-abliterated-GGUF",
        "file": "Huihui-Qwen3.8-27B-abliterated.IQ4_XS.gguf",
        "ctx": [131072, 65536, 32768],
        "alias": "huihui-qwen3.8-27b-abliterated",
        "mtp": True,
    },
    "a100-qwen38-q4": {
        "repo": "mradermacher/Huihui-Qwen3.8-27B-abliterated-GGUF",
        "file": "Huihui-Qwen3.8-27B-abliterated.Q4_K_M.gguf",
        "ctx": [262144, 131072, 65536],
        "alias": "huihui-qwen3.8-27b-abliterated",
        "mtp": True,
    },
    "a100-qwen38-q8": {
        "repo": "mradermacher/Huihui-Qwen3.8-27B-abliterated-GGUF",
        "file": "Huihui-Qwen3.8-27B-abliterated.Q8_0.gguf",
        "ctx": [131072, 65536],
        "alias": "huihui-qwen3.8-27b-abliterated",
        "mtp": True,
    },
}


def main():
    preset_name = os.environ.get("LLM_PRESET", "l4-qwen36-moe")
    cfg = dict(PRESETS.get(preset_name, PRESETS["l4-qwen36-moe"]))

    repo = os.environ.get("LLM_REPO") or cfg["repo"]
    filename = os.environ.get("LLM_FILE") or cfg["file"]
    alias = os.environ.get("LLM_ALIAS") or cfg["alias"]
    port = int(os.environ.get("LLM_PORT", "8000"))
    slots = int(os.environ.get("LLM_SLOTS", "1"))
    mtp = os.environ.get("LLM_MTP")
    use_mtp = (mtp == "1") if mtp is not None else cfg["mtp"]

    if os.environ.get("LLM_CTX"):
        ctx_list = [int(os.environ["LLM_CTX"])]
    else:
        ctx_list = cfg["ctx"]

    worker_code = f"""
import os, subprocess, time, urllib.request

os.environ["HF_XET_HIGH_PERFORMANCE"] = "1"
os.makedirs("/content/llama-bin", exist_ok=True)
os.makedirs("/content/models", exist_ok=True)

bin_dir = "/content/llama-bin/llama-{LLAMA_TAG}"
server_bin = os.path.join(bin_dir, "llama-server")
if not os.path.exists(server_bin):
    print("[1/3] Installing llama.cpp CUDA binary ({LLAMA_TAG})...", flush=True)
    subprocess.run(["bash", "-c", '''
        cd /content/llama-bin &&
        curl -sL -o llama.tar.gz "{LLAMA_URL}" &&
        curl -sL -o cudart.tar.gz "{CUDART_URL}" &&
        tar -xzf llama.tar.gz && tar -xzf cudart.tar.gz &&
        cp --update=none /content/llama-bin/cudart-llama-{LLAMA_TAG}-bin-ubuntu-cuda-12.8-x64/* {bin_dir}/ 2>/dev/null || cp -n /content/llama-bin/cudart-llama-{LLAMA_TAG}-bin-ubuntu-cuda-12.8-x64/* {bin_dir}/ &&
        rm -f llama.tar.gz cudart.tar.gz
    '''], check=True)

print("[2/3] Ensuring huggingface_hub and downloading {repo} / {filename}...", flush=True)
subprocess.run(["pip", "install", "-q", "-U", "huggingface_hub"], check=False)
from huggingface_hub import hf_hub_download
model_path = hf_hub_download("{repo}", filename="{filename}", local_dir="/content/models")
print("Downloaded:", model_path, flush=True)

print("[3/3] Starting llama-server on 127.0.0.1:{port}...", flush=True)
mtp_flag = "--spec-type draft-mtp" if {use_mtp} else ""
log_file = "/tmp/llama_server_{port}.log"

for ctx in {ctx_list}:
    subprocess.run(["bash", "-c", "pkill -f 'llama-server.*--port {port}' 2>/dev/null || true"])
    time.sleep(1)
    cmd = (
        f"LD_LIBRARY_PATH={{bin_dir}}:$LD_LIBRARY_PATH "
        f"nohup {{server_bin}} -m {{model_path}} "
        f"-c {{ctx}} -np {slots} -ngl 999 -fa on --jinja "
        f"--alias {alias} --cache-type-k q8_0 --cache-type-v q8_0 "
        f"--host 127.0.0.1 --port {port} {{mtp_flag}} "
        f"> {{log_file}} 2>&1 &"
    )
    subprocess.Popen(["bash", "-c", cmd])
    ready = False
    for _ in range(40):
        time.sleep(1.5)
        try:
            r = urllib.request.urlopen("http://127.0.0.1:{port}/health", timeout=2).read().decode()
            if '"ok"' in r:
                ready = True
                break
        except Exception:
            pass
    if ready:
        gpu = subprocess.getoutput("nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader")
        print(f"READY|PORT={port}|CTX={{ctx}}|ALIAS={alias}|GPU={{gpu}}", flush=True)
        break
    else:
        print(f"CTX={{ctx}} failed on port {port}, trying fallback...", flush=True)
"""
    worker_path = f"/tmp/run_llm_deploy_{port}.py"
    with open(worker_path, "w") as f:
        f.write(worker_code)

    deploy_log = f"/tmp/llm_deploy_{port}.log"
    subprocess.Popen(["bash", "-c", f"python3 -u {worker_path} > {deploy_log} 2>&1 &"])
    print(f"LAUNCHED_BG|PRESET={preset_name}|REPO={repo}|FILE={filename}|PORT={port}|LOG={deploy_log}")


if __name__ == "__main__":
    main()
