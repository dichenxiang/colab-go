# colab-go

一个面向 AI Agent（Antigravity / Claude Code / Codex / OpenClaw 等）的 **Google Colab GPU 全自动部署 Skill**。

无需手动打开 Colab 网页，也不依赖第三方桌面客户端——只需把本仓库 / Skill 交给你的 AI Agent，它就会基于谷歌官方 **`google-colab-cli`** 全自动完成：

1. **自动配置本机环境**：支持 macOS / Linux，以及 **Windows（WSL2 Ubuntu + 防 `docker-desktop` 抢默认 + `.wslconfig` 镜像代理 + `gnome-keyring` 免密密钥环）**。
2. **暂停引导登录 Google 账号**：自动拉起 OAuth 登录流程并查询剩余计算单元（CU）。
3. **展示可用 GPU 选型表**：列出 T4 / L4 / A100 的显存、每小时消耗（CU/h）与可跑模型，确认后再开机。
4. **一键部署两大热门工作流**：
   - **无审查开源大模型（OpenAI 兼容 API）**：内置 `Gemma-3-12B`（T4）、`Qwen3.6-35B-A3B MoE`（L4）、`Qwen3.8-27B`（L4 / A100 Q4 256K & Q8 128K），自动装 CUDA `llama-server` 并映射到本地 `127.0.0.1`。
   - **ComfyUI + MiniMax H3 视频生成（带原生立体声音频）**：自动装 ComfyUI + `ComfyUI-GGUF` + `VideoHelperSuite`，内置 `FL2VA`（首尾帧/图生视频）与 `Ref2VA`（参考图一致性）全套权重和 JSON 工作流，打通 `8188` 端口后**自动在用户电脑默认浏览器弹出 ComfyUI 窗口**。
5. **故障自愈与防烧钱保命规则**：断连自动清理远端僵尸 `sshd`；结束强制执行 `colab stop` + `colab sessions` 核验停机。

---

## 快速使用

### 方式一：安装为 Agent Skill（推荐）
把本仓库克隆到你的 Agent 全局 Skills 目录（例如 Antigravity 的 `~/.gemini/config/skills/colab-go`）：

```bash
git clone https://github.com/dichenxiang/colab-go.git ~/.gemini/config/skills/colab-go
```

然后直接跟你的 Agent 说：
> **“使用 `colab-go` 帮我配置 Google Colab 环境并部署模型 / MiniMax H3 视频工作流。”**

### 方式二：直接发给任意 AI Agent
把本仓库链接或 `SKILL.md` 直接发给你的 AI Agent，让它严格按 `SKILL.md` 中的阶段一到阶段五逐步执行即可。

---

## 目录结构

```text
colab-go/
├── SKILL.md                           # Agent 主执行指令（含环境配置、登录引导、GPU 表、一键部署与防烧钱规则）
├── references/
│   └── models-and-gpus.md             # 完整 GPU 消耗对照表、内置 LLM 与 MiniMax H3 权重明细
├── workflows/                         # 预置 ComfyUI 工作流 JSON（开箱即用，已对齐模型文件名）
│   ├── minimax_h3_i2v_2pass_latent_upscaler.json   # ⭐ 二采放大：首尾帧/图生视频 + 3D Latent Upscaler
│   ├── minimax_h3_r2v_2pass_latent_upscaler.json   # ⭐ 二采放大：参考图一致性 + 3D Latent Upscaler
│   ├── minimax_h3_fl2v_gguf.json                   # 单采：首尾帧/图生视频 GGUF
│   ├── minimax_h3_ref2va_gguf.json                 # 单采：参考图生视频 GGUF
│   ├── minimax_h3_fl2va_8step_turbo_gguf.json      # 单采：8 步 Turbo 加速 FL2VA
│   └── minimax_h3_ref2va_4step_turbo_gguf.json     # 单采：4 步 Turbo 加速 Ref2VA
└── scripts/
    ├── deploy_llm_remote.py           # Colab 远端一键部署 CUDA llama-server + 内置 GGUF 预设
    ├── deploy_comfyui_minimax_h3.py   # Colab 远端一键部署 ComfyUI + MiniMax H3（含二采放大节点与权重）
    ├── open_tunnel.sh                 # 本地 SSH 端口转发脚本（LLM 8000/8001，ComfyUI 8188）
    ├── fix_remote_sshd.py             # 清理 Colab 僵尸 sshd 进程（解决重连报错）
    └── reason_proxy.py                # 可选本地流式代理（将 reasoning_effort high/max 自动转为 xhigh）
```

---

## 免责声明
- 本项目仅自动化调用 Google 官方 `google-colab-cli` 及开源社区权重。请遵守 Google Colab 服务条款及各开源模型许可证。
- 租用 Colab 付费 GPU 时，闲置也会计费；请务必在用完后确认 `colab sessions` 显示 `No active sessions found on server.`。
