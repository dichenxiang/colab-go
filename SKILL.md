---
name: colab-go
description: >-
  End-to-end Google Colab GPU automation skill using the official google-colab-cli (no third-party desktop app required).
  Use whenever the user asks to set up Google Colab CLI on Windows (WSL2 Ubuntu + mirrored proxy + gnome-keyring) or macOS/Linux,
  deploy uncensored open-source GGUF LLMs (Qwen3.8-27B, Qwen3.6-35B-A3B MoE, Gemma-3-12B) as local OpenAI-compatible APIs,
  or deploy ComfyUI + MiniMax H3 (FL2VA / Ref2VA video + stereo audio) on Colab GPUs and open the ComfyUI window in the user's local browser.
---

# Google Colab GPU 全自动部署技能（无审查大模型 API + ComfyUI MiniMax H3 视频工作流）

本技能指导 Agent 仅通过谷歌官方 **`google-colab-cli`**（无需浏览器点点点，也无需第三方桌面软件），全自动完成环境配置、引导登录 Google 账号、展示可用 GPU 选型表、租用云端显卡、拉取内置模型或 ComfyUI MiniMax H3 工作流、端口转发到本机，以及帮用户在电脑上直接打开 ComfyUI 窗口。

完整模型与 GPU 参数明细见 [references/models-and-gpus.md](./references/models-and-gpus.md)。

---

## 执行总原则
1. **遇到需用户交互的节点必须暂停提示**：包括第一次打开 Ubuntu 设密码、浏览器完成 Google OAuth 登录、以及**正式开付费卡前的确认**。
2. **严禁猜命令行参数**：优先调用本 Skill `scripts/` 目录下的经过验证的脚本。
3. **防烧钱铁律**：任何时候结束使用或用户说停机，必须运行 `colab stop` 并用 `colab sessions` 确认返回 `No active sessions found on server.`。

---

## 阶段一：本地环境自动检查与配置

判断当前操作系统：
- **macOS / Linux**：确认已安装 `ssh`、`uv`（若无则安装），执行 `uv tool install google-colab-cli`，确认 `colab --help` 正常。
- **Windows**：`google-colab-cli` 依赖 Linux 密钥环与 SSH，必须运行在 **WSL 2 (Ubuntu)** 内，按顺序执行：
  1. **检查 WSL 发行版**：运行 `wsl -l -v`。
     - 若无 `Ubuntu`（例如只有 `docker-desktop` 或为空）：执行 `wsl --install -d Ubuntu --no-launch`，然后**⏸️ 暂停并提示用户**打开开始菜单里的 Ubuntu 设置一次 Linux 用户名和密码，完成后回复继续。
     - **必查防坑**：若带 `*` 号的默认发行版是 `docker-desktop`，立即执行 `wsl --set-default Ubuntu`（`docker-desktop` 内无 `bash` 会直接报错）。
  2. **配置镜像网络与代理共享**（解决国内代理访问 Google / Hugging Face，并让 WSL 转发的 `127.0.0.1` 端口直接被 Windows 访问）：
     - 检查 `%USERPROFILE%\.wslconfig`，若未配置 `networkingMode=mirrored`，写入：
       ```ini
       [wsl2]
       networkingMode=mirrored
       autoProxy=true
       ```
     - 执行 `wsl --shutdown` 重启 WSL，并在 Ubuntu 内测试 `curl -sI --max-time 8 https://www.google.com | head -n 1` 确认代理连通。
  3. **安装密钥环与 `google-colab-cli`**：
     - 以 root 安装基础组件（无需用户 sudo 密码）：
       `wsl -d Ubuntu -u root -e bash -lc "DEBIAN_FRONTEND=noninteractive apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y gnome-keyring libsecret-tools openssh-client curl"`
     - 在用户目录下初始化**免密自动解锁**的默认密钥环（避免命令行等待 GUI 弹窗卡死）：
       ```bash
       mkdir -p ~/.local/share/keyrings && chmod 700 ~/.local/share/keyrings
       cat > ~/.local/share/keyrings/Default_keyring.keyring << 'EOF'
       [keyring]
       display-name=Default keyring
       ctime=1700000000
       mtime=1700000000
       lock-on-idle=false
       lock-after=false
       EOF
       printf "Default_keyring" > ~/.local/share/keyrings/default
       chmod 600 ~/.local/share/keyrings/Default_keyring.keyring ~/.local/share/keyrings/default
       systemctl --user restart gnome-keyring-daemon.service
       ```
     - 安装 `uv`（若无：`curl -LsSf https://astral.sh/uv/install.sh | sh`）并执行 `~/.local/bin/uv tool install google-colab-cli`。
     - 验证 `~/.local/bin/colab --help` 退出码为 `0`。

---

## 阶段二：Google 账号登录（⏸️ 暂停并提醒用户）

1. 检查登录状态：`colab whoami`（Windows 下通过 `wsl -d Ubuntu -e bash -lc "~/.local/bin/colab whoami"`）。
2. **若未登录**：
   - 运行 `colab usage` 触发 OAuth 授权，把终端输出的 Google 授权 URL 完整发给用户。
   - **⏸️ 暂停并明确提醒用户**：“请点击上方链接登录你的 Google 账号（建议是有 Google AI Pro / Ultra 算力单元或可用免费额度的账号），完成授权后把授权码发给我（或按网页提示完成确认）。”
3. 登录成功后，运行 `colab usage` 读取并汇报用户当前的 **算力单元余额（CU）** 和当前活跃会话数。

---

## 阶段三：展示可用 GPU 表格与内置模型/工作流选项（⏸️ 让用户拍板）

登录成功并汇报 CU 余额后，**必须向用户展示以下选型表格**，让用户选好「显卡型号 + 部署内容」后再开机（防止未经确认直接烧单元）：

### 可用 GPU 对照表

| GPU | 显存 | 参考消耗 | 推荐可跑的模型 / 工作流 |
| :--- | :--- | :--- | :--- |
| **T4** | 16 GB | 免费号 0 CU / Pro ~**1.15 CU/h** | 轻量文本/RP：`Gemma-3-12B-abliterated`（`t4-gemma12b`） |
| **L4** ⭐ | 24 GB | 约 **1.94 CU/h**（性价比最高） | • 极速 MoE：`Qwen3.6-35B-A3B`（`l4-qwen36-moe`，128K，53~71 t/s）<br>• 稳健逻辑：`Qwen3.8-27B`（`l4-qwen38-27b`，128K，~30 t/s）<br>• 视频生成：**ComfyUI + MiniMax H3 GGUF**（5秒带声视频约 6 分钟） |
| **A100 (40G)** | 40 GB | 约 **6.73 ~ 13 CU/h** | • 满血极速：`Qwen3.8-27B Q4_K_M`（`a100-qwen38-q4`，256K，81~100 t/s）<br>• 准无损：`Qwen3.8-27B Q8_0`（`a100-qwen38-q8`，128K，~58 t/s）<br>• 视频生成：**ComfyUI + MiniMax H3**（GGUF 或官方 FP8 版） |

### 内置一键拉取清单
- **大模型预设**（`scripts/deploy_llm_remote.py`）：`t4-gemma12b` / `l4-qwen36-moe` / `l4-qwen38-27b` / `a100-qwen38-q4` / `a100-qwen38-q8`（完整 HF 仓库与文件名见 [references/models-and-gpus.md](./references/models-and-gpus.md)）。
- **MiniMax H3 视频工作流预设**（`scripts/deploy_comfyui_minimax_h3.py`，仓库 `workflows/` 目录已直接内置 6 套对齐好的 JSON 工作流）：
  - `fl2va-2pass`（**二采放大推荐**：首尾帧/图生视频 + `LBH-123-AI` 3D/2D Latent 放大二次采样精修，L4/A100 通用）
  - `ref2va-2pass`（**二采放大推荐**：参考图角色/服饰一致性 + 3D/2D Latent 放大二次采样精修，L4/A100 通用）
  - `fl2va-gguf`（首尾帧/图生视频+音频，GGUF 单采）
  - `ref2va-gguf`（参考图生视频+音频，GGUF 单采）
  - `fl2va-fp8` / `ref2va-fp8`（A100 官方 FP8 单采版）

---

## 阶段四：Agent 直接开机、拉取部署与打开本地窗口

### 1. 直接开机（租用 GPU）
根据用户选择的 GPU 执行：
```bash
colab new -s <会话名> --gpu <T4|L4|A100>
```
*(如高峰期 A100 分配失败，告知用户并建议改开 `L4`。)*

---

### 分支 A：部署无审查开源大模型（OpenAI 兼容 API）

1. **后台拉取并启动**（避免 `colab exec` 30 秒超时，脚本会自动在 Colab 后台下载并拉起 CUDA `llama-server`）：
   ```bash
   colab exec -s <会话名> --timeout 60 \
     --env LLM_PRESET=<预设名> \
     --env LLM_PORT=8000 \
     -f <本Skill目录>/scripts/deploy_llm_remote.py
   ```
   *(若要同时开两张卡，可将第二张卡的 `LLM_PORT` 设为 `8001`。)*
2. **轮询就绪**：间隔 30~60 秒查看 `/tmp/llm_deploy_<port>.log`，直到出现 `READY|PORT=...`。
3. **打通本地端口转发**（作为后台守护任务启动）：
   ```bash
   bash <本Skill目录>/scripts/open_tunnel.sh <会话名> <本地端口> <远端端口>
   ```
4. **验证并汇报**：在本机请求 `http://127.0.0.1:<本地端口>/v1/chat/completions` 发一条简短测试消息，汇报实测 `tokens/s`、Base URL（`http://127.0.0.1:<本地端口>/v1`）与 Model ID。
5. **Agent 思考参数兼容提醒**：若用户的 Agent 客户端强制发送 `reasoning_effort: "high"` 或 `"max"` 触发 400 报错（`Huihui-Qwen3.8-27B` 仅支持 `low`/`medium`/`xhigh`），在本地后台启动 [scripts/reason_proxy.py](./scripts/reason_proxy.py)（例如 `python reason_proxy.py 8002:8001`）让客户端改连 `8002`。

---

### 分支 B：部署 ComfyUI + MiniMax H3 视频工作流（并在用户电脑打开窗口）

1. **拉取 ComfyUI + 必备节点 + MiniMax H3 全套权重与工作流 JSON**：
   ```bash
   colab exec -s <会话名> --timeout 60 \
     --env H3_MODE=<fl2va-2pass|ref2va-2pass|fl2va-gguf|ref2va-gguf|fl2va-fp8|ref2va-fp8> \
     --env H3_QUANT=Q4_K_M \
     --env H3_PORT=8188 \
     -f <本Skill目录>/scripts/deploy_comfyui_minimax_h3.py
   ```
   - 脚本会自动完成：
     1. 克隆最新版 `ComfyUI`、`ComfyUI-GGUF`、`ComfyUI-VideoHelperSuite`、`ComfyUI-KJNodes`、`Comfyui_Minimax_h3_latent_Upscaler`（二采 3D/2D Latent 放大及分块重采样必备）。
     2. 开启 `HF_XET_HIGH_PERFORMANCE=1` 高速拉取主模型、Qwen3-VL-32B Text Encoder、Video/Audio VAE、Turbo 加速 LoRA，以及（在 `2pass` 模式下）`LBH-123-AI/Minimax_h3_latent_Upscaler` 的 3D/2D 放大权重到 `models/latent_upscale_models/`。
     3. 自动将本仓库 `workflows/` 下已对齐好模型下拉框文件名的 6 套工作流 JSON（含 `minimax_h3_i2v_2pass_latent_upscaler.json` 和 `minimax_h3_r2v_2pass_latent_upscaler.json` 两套二采放大工作流）放进 `/content/ComfyUI/user/default/workflows/`。
     4. 自动识别显卡显存（≤26GB 自动加 `--lowvram`，否则 `--normalvram`），在远端 `127.0.0.1:8188` 启动 ComfyUI。
2. **轮询就绪**：间隔 60 秒查看 `/tmp/comfyui_deploy.log`（整套权重约 42 GB，Colab 内网一般需要 3~5 分钟），直到出现 `COMFYUI_READY|PORT=8188`。
3. **打通本地 `8188` 端口转发**（作为后台守护任务启动）：
   ```bash
   bash <本Skill目录>/scripts/open_tunnel.sh <会话名> 8188 8188
   ```
4. **验证端口并直接在用户电脑上打开 ComfyUI 窗口**：
   - 先验证本机访问 `http://127.0.0.1:8188/system_stats` 返回 HTTP 200。
   - **自动拉起用户电脑的默认浏览器窗口**：
     - Windows（PowerShell）：`Start-Process "http://127.0.0.1:8188"`
     - macOS：`open "http://127.0.0.1:8188"`
     - Linux：`xdg-open "http://127.0.0.1:8188"`
   - 在回复中同时给出可点击链接 `http://127.0.0.1:8188`，并告诉用户：
     1. 点 ComfyUI 左侧 **Workflows（工作流）** 图标，直接点开已自动下载好的 `minimax_fl2v_gguf_workflow.json`（或 `ref2va` / `Vantage-Minimax-H3-...json`）。
     2. 确认采样节点里的 **CFG Scale = `1.0`**（MiniMax H3 切勿设高）。
     3. 生成好的带声视频既可在网页直接右键保存，也可叫 Agent 执行 `colab download -s <会话名> /content/ComfyUI/output/<文件名> ./` 批量拉回本地。

---

## 阶段五：常见故障自愈与防烧钱收尾

### 1. 端口转发断连 / 报“已有其他连接”
Colab 单个运行时仅允许 **1 个并发 SSH 连接**。若网络抖动导致重连卡死，先运行僵尸 SSH 清理脚本，再重拉隧道：
```bash
colab exec -s <会话名> -f <本Skill目录>/scripts/fix_remote_sshd.py
```

### 2. 查看实时 GPU 占用与速度
通过 `colab exec -s <会话名>` 执行 `nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader` 并查看 `/tmp/llama_server_<port>.log` 或 `/tmp/comfyui.log` 尾部。

### 3. 停机与算力核验（必须执行）
任务完成后或用户指令关机时，依次执行：
```bash
colab stop -s <会话名>
colab sessions
colab usage
```
**必须亲眼看到 `colab sessions` 输出 `No active sessions found on server.`** 才能向用户确认已停止计费（同时提醒用户：Colab 扣费统计可能有几十分钟延迟，以 `colab sessions` 无活跃实例为准）。
