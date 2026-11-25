#!/usr/bin/env python3
"""
Remote Colab deployment script for ComfyUI + MiniMax H3 (Video + Native Stereo Audio),
including 2-Pass Latent Upscaler ("二采放大") workflows.

Run on a Colab VM via:
  colab exec -s <session> --timeout 60 -f deploy_comfyui_minimax_h3.py

Configure via environment variables passed with `colab exec --env KEY=VAL`:
  H3_MODE  :
    - fl2va-2pass  (推荐：首尾帧/图生视频 + 3D/2D Latent 放大二采精修，INT8 主模型，适配 L4/A100)
    - ref2va-2pass (推荐：参考图一致性生视频 + 3D/2D Latent 放大二采精修，INT8 主模型，适配 L4/A100)
    - fl2va-gguf   (首尾帧/图生视频 GGUF 单采，适配 L4/A100)
    - ref2va-gguf  (参考图生视频 GGUF 单采，适配 L4/A100)
    - fl2va-fp8    (首尾帧/图生视频官方 FP8 单采，适配 A100)
    - ref2va-fp8   (参考图生视频官方 FP8 单采，适配 A100)
  H3_QUANT : Q4_K_M (default for GGUF modes, ~19.9GB) | Q3_K_M (~15.6GB)
  H3_PORT  : remote ComfyUI port (default: 8188)
"""
import os
import subprocess


def main():
    mode = os.environ.get("H3_MODE", "fl2va-2pass")
    quant = os.environ.get("H3_QUANT", "Q4_K_M")
    port = int(os.environ.get("H3_PORT", "8188"))

    worker_code = f'''
import os, shutil, subprocess, time, urllib.request

os.environ["HF_XET_HIGH_PERFORMANCE"] = "1"
COMFY_DIR = "/content/ComfyUI"
MODE = "{mode}"
QUANT = "{quant}"
PORT = {port}

def run(cmd):
    print(">>", cmd, flush=True)
    subprocess.run(["bash", "-c", cmd], check=True)

print("[1/4] Installing ComfyUI + GGUF + VideoHelperSuite + KJNodes + LBH Latent Upscaler...", flush=True)
if not os.path.exists(COMFY_DIR):
    run(f"git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git {{COMFY_DIR}}")
run(f"pip install -q -r {{COMFY_DIR}}/requirements.txt huggingface_hub gguf")

custom_nodes = [
    ("ComfyUI-GGUF", "https://github.com/city96/ComfyUI-GGUF.git"),
    ("ComfyUI-VideoHelperSuite", "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git"),
    ("ComfyUI-KJNodes", "https://github.com/kijai/ComfyUI-KJNodes.git"),
    ("Comfyui_Minimax_h3_latent_Upscaler", "https://github.com/LBH-123-AI/Comfyui_Minimax_h3_latent_Upscaler.git"),
]
for name, repo_url in custom_nodes:
    node_dir = os.path.join(COMFY_DIR, "custom_nodes", name)
    if not os.path.exists(node_dir):
        run(f"git clone --depth 1 {{repo_url}} {{node_dir}}")
        req = os.path.join(node_dir, "requirements.txt")
        if os.path.exists(req):
            run(f"pip install -q -r {{req}}")

from huggingface_hub import hf_hub_download

def dl(repo, remote_path, target_dir):
    os.makedirs(target_dir, exist_ok=True)
    dst = os.path.join(target_dir, os.path.basename(remote_path))
    if os.path.exists(dst) and os.path.getsize(dst) > 1000:
        print("Already exists:", dst, flush=True)
        return dst
    print(f"Downloading {{repo}} :: {{remote_path}} -> {{dst}}", flush=True)
    p = hf_hub_download(repo, filename=remote_path, local_dir="/tmp/hf_h3_cache")
    shutil.move(p, dst)
    print("Saved:", dst, flush=True)
    return dst

def dl_url(url, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    urllib.request.urlretrieve(url, dst)
    print("Workflow saved:", dst, flush=True)

print(f"[2/4] Downloading MiniMax H3 weights for mode={{MODE}}, quant={{QUANT}}...", flush=True)
# Shared VAEs (Video + Audio)
dl("Comfy-Org/MiniMax-H3", "vae/minimax_h3_video_vae_fp16.safetensors", f"{{COMFY_DIR}}/models/vae")
dl("Comfy-Org/MiniMax-H3", "vae/minimax_h3_audio_vae_fp32.safetensors", f"{{COMFY_DIR}}/models/vae")

is_ref = MODE.startswith("ref2va")
is_2pass = MODE.endswith("-2pass")
is_fp8 = MODE.endswith("-fp8")
variant = "ref2va" if is_ref else "fl2va"

# Acceleration Turbo LoRA
if is_ref:
    dl("Comfy-Org/MiniMax-H3", "loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors", f"{{COMFY_DIR}}/models/loras")
else:
    dl("Comfy-Org/MiniMax-H3", "loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors", f"{{COMFY_DIR}}/models/loras")

# Diffusion model + Text Encoder
if is_2pass:
    dl("Comfy-Org/MiniMax-H3", f"diffusion_models/minimax_h3_{{variant}}_pruned_int8_convrot.safetensors", f"{{COMFY_DIR}}/models/diffusion_models")
    dl("Comfy-Org/MiniMax-H3", "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", f"{{COMFY_DIR}}/models/text_encoders")
    # 3D + 2D Latent Upscaler models (for 2-pass refinement)
    dl("LBH-123-AI/Minimax_h3_latent_Upscaler", "minimax_h3_latent_upscaler_3d_conv_v1/minimax_h3_latent_upscaler_3d_conv_v1_fp16.safetensors", f"{{COMFY_DIR}}/models/latent_upscale_models")
    dl("LBH-123-AI/Minimax_h3_latent_Upscaler", "minimax_h3_latent_upscaler_2d_conv_v1/minimax_h3_latent_upscaler_2d_conv_v1_fp16.safetensors", f"{{COMFY_DIR}}/models/latent_upscale_models")
elif is_fp8:
    dl("Comfy-Org/MiniMax-H3", f"diffusion_models/minimax_h3_{{variant}}_pruned_fp8_scaled.safetensors", f"{{COMFY_DIR}}/models/diffusion_models")
    dl("Comfy-Org/MiniMax-H3", "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors", f"{{COMFY_DIR}}/models/text_encoders")
else:
    prefix = "MiniMax-H3-Ref2VA" if is_ref else "MiniMax-H3-FL2VA"
    dl("Abiray/MiniMax-H3-GGUF", f"unet/{{prefix}}-{{QUANT}}.gguf", f"{{COMFY_DIR}}/models/unet")
    dl("Abiray/MiniMax-H3-GGUF", "text_encoders/qwen3vl_32b_minimax_h3-Q4_K_M.gguf", f"{{COMFY_DIR}}/models/text_encoders")

print("[3/4] Installing pre-aligned MiniMax H3 workflow JSONs (including 2-pass)...", flush=True)
wf_dir = f"{{COMFY_DIR}}/user/default/workflows"
os.makedirs(wf_dir, exist_ok=True)
wf_base = "https://raw.githubusercontent.com/dichenxiang/colab-go/main/workflows"
wf_files = [
    "minimax_h3_i2v_2pass_latent_upscaler.json",
    "minimax_h3_r2v_2pass_latent_upscaler.json",
    "minimax_h3_fl2v_gguf.json",
    "minimax_h3_ref2va_gguf.json",
    "minimax_h3_fl2va_8step_turbo_gguf.json",
    "minimax_h3_ref2va_4step_turbo_gguf.json",
]
for wf in wf_files:
    try:
        dl_url(f"{{wf_base}}/{{wf}}", os.path.join(wf_dir, wf))
    except Exception as e:
        print(f"Warn: failed to fetch {{wf}} from colab-go repo: {{e}}", flush=True)

print(f"[4/4] Starting ComfyUI on 127.0.0.1:{{PORT}}...", flush=True)
subprocess.run(["bash", "-c", "pkill -f 'ComfyUI/main.py' 2>/dev/null || true"])
time.sleep(1)

vram_mb = int(subprocess.getoutput("nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits").splitlines()[0].strip())
vram_flag = "--lowvram" if vram_mb <= 26000 else "--normalvram"
cmd = f"cd {{COMFY_DIR}} && nohup python3 main.py --listen 127.0.0.1 --port {{PORT}} {{vram_flag}} > /tmp/comfyui.log 2>&1 &"
subprocess.Popen(["bash", "-c", cmd])

for _ in range(45):
    time.sleep(2)
    try:
        r = urllib.request.urlopen(f"http://127.0.0.1:{{PORT}}/system_stats", timeout=2).read().decode()
        if "comfyui_version" in r or "devices" in r:
            gpu = subprocess.getoutput("nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader")
            print(f"COMFYUI_READY|PORT={{PORT}}|MODE={{MODE}}|VRAM_FLAG={{vram_flag}}|GPU={{gpu}}", flush=True)
            break
    except Exception:
        pass
else:
    print("COMFYUI_NOT_READY_YET, check /tmp/comfyui.log", flush=True)
'''
    worker_path = "/tmp/run_comfyui_h3_deploy.py"
    with open(worker_path, "w") as f:
        f.write(worker_code)

    subprocess.Popen(["bash", "-c", f"python3 -u {worker_path} > /tmp/comfyui_deploy.log 2>&1 &"])
    print(f"COMFYUI_LAUNCHED_BG|MODE={mode}|QUANT={quant}|PORT={port}|LOG=/tmp/comfyui_deploy.log")


if __name__ == "__main__":
    main()
