# Colab GPU 规格、内置模型目录与 MiniMax H3 参数参考

## 1. Google Colab 可用 GPU 规格与算力对照表

> 登录 Google 账号后，Agent 需先执行 `colab usage` 查看用户当前余额（CU），再向用户展示以下表格让用户选择要开的显卡与任务：

| GPU 型号 | 显存 (VRAM) | 参考消耗 (CU/小时) | 适用账号 | 推荐可跑的大模型 / 视频工作流 | 实测速度与特点 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **NVIDIA T4** | 16 GB | 免费号 0 CU（限时）<br>Pro 约 **1.15 CU/h** | 免费号 / Pro | • `Gemma-3-12B-abliterated` (`Q4_K_M`)<br>• `Qwen3-14B-abliterated` (`Q4_K_M`)<br>• 轻度视频超分 / 3D 渲染 | 免费号白嫖主力；跑 12B~14B 约 20~28 tokens/s，可开 16K~32K 上下文 |
| **NVIDIA L4** | 24 GB（可用 ~22.5 GB） | 约 **1.94 CU/h** | Pro / Ultra | • **极速 MoE**：`Qwen3.6-35B-A3B` (`i1-IQ4_XS`, 128K)<br>• **稳健推理**：`Qwen3.8-27B` (`IQ4_XS`, 128K)<br>• **视频生成**：ComfyUI + **MiniMax H3 GGUF** (`Q3_K_M`/`Q4_K_M` + 8步 Turbo LoRA) | **性价比天花板**（200 CU 可跑 ~100 小时）；35B-A3B 实测 53~71 t/s；MiniMax H3 5秒带声视频约 6 分钟（~0.2 CU） |
| **NVIDIA A100 (40GB)** | 40 GB | 约 **6.73 ~ 13 CU/h** | Pro / Ultra | • **满血 256K**：`Qwen3.8-27B` (`Q4_K_M`, 256K)<br>• **准无损**：`Qwen3.8-27B` (`Q8_0`, 128K)<br>• **视频生成**：ComfyUI + **MiniMax H3** (`Q4_K_M` 或官方 `fp8_scaled`) | 显存宽裕、带宽极高；27B Q4 实测 **81~100 t/s**，Q8 实测 **~58 t/s**；适合复杂写卡/代码与高质量视频 |
| **NVIDIA A100 (80GB)** | 80 GB | 约 **13 ~ 15 CU/h** | Pro / Ultra（随机分配，高峰期不保证） | • 70B 级大模型（如 `Qwen2.5-72B` / `Llama-3.3-70B`）<br>• ComfyUI + MiniMax H3 全精度/高分辨率批处理 | 顶级单卡，耗单元较快，适合高强度突击任务 |

*(注：2026 年 9 月 22 日起，Google AI Pro 每月赠送 200 CU，未用完可滚动保留最多 3 个月；Ultra 每月赠送 1,000~2,000 CU。实际费率以 `colab usage` 实时显示为准。)*

---

## 2. 内置无审查开源大模型拉取清单（GGUF / llama.cpp）

所有预设均已内置在 `scripts/deploy_llm_remote.py` 中，通过 `--preset <预设名>` 一键拉取部署：

| 预设名 (`--preset`) | 推荐显卡 | Hugging Face 仓库 | 精确文件名 | 体积 | 默认上下文 | 说明 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `t4-gemma12b` | T4 (16GB) | `bartowski/mlabonne_gemma-3-12b-it-abliterated-GGUF` | `mlabonne_gemma-3-12b-it-abliterated-Q4_K_M.gguf` | 7.3 GB | 32K (`32768`) | 免费号 T4 文本/RP 首选，文笔细腻 |
| `l4-qwen36-moe` | L4 (24GB) | `mradermacher/Qwen3.6-35B-A3B-abliterated-i1-GGUF` | `Qwen3.6-35B-A3B-abliterated.i1-IQ4_XS.gguf` | 18.73 GB | 128K (`131072`) | **L4 性价比首选**，每次仅激活 3B，实测 53~71 t/s，读上下文 >1900 t/s |
| `l4-qwen38-27b` | L4 (24GB) | `mradermacher/Huihui-Qwen3.8-27B-abliterated-GGUF` | `Huihui-Qwen3.8-27B-abliterated.IQ4_XS.gguf` | 15.4 GB | 128K (`131072`) | L4 上复杂代码/规划/金融推演最稳（带 MTP，实测 ~30 t/s） |
| `a100-qwen38-q4` | A100 (40GB) | `mradermacher/Huihui-Qwen3.8-27B-abliterated-GGUF` | `Huihui-Qwen3.8-27B-abliterated.Q4_K_M.gguf` | 15.7 GB | 256K (`262144`) | **A100 速度与长文主力**（带 MTP，原生满血 256K，实测 81~100 t/s） |
| `a100-qwen38-q8` | A100 (40GB) | `mradermacher/Huihui-Qwen3.8-27B-abliterated-GGUF` | `Huihui-Qwen3.8-27B-abliterated.Q8_0.gguf` | 27.1 GB | 128K (`131072`) | A100 准无损精度（带 MTP，实测 ~58 t/s；注意 40GB 卡勿强开 256K 否则会退回 CPU） |

> **自定义模型**：也支持通过 `--repo <HF仓库> --file <精确文件名> --ctx <上下文> --alias <模型ID>` 部署任意 Hugging Face GGUF 模型。

---

## 3. 内置 MiniMax H3 视频工作流拉取清单（ComfyUI）

MiniMax H3 是支持**原生立体声音频 + 高清视频同步生成**的开源 33B 全模态视频模型。部署脚本 `scripts/deploy_comfyui_minimax_h3.py` 会自动安装最新版 ComfyUI + `ComfyUI-GGUF` + `ComfyUI-VideoHelperSuite`，并将所有权重和工作流 JSON 放到正确的 ComfyUI 目录中：

### 预设模式（`--mode`）

| 模式 (`--mode`) | 推荐显卡 | 对应用途 | 配套权重（自动拉取） | 自动导入的 ComfyUI 工作流 JSON |
| :--- | :--- | :--- | :--- | :--- |
| `fl2va-gguf`（默认推荐） | **L4 (24GB)** / A100 | **首尾帧 / 图生视频 + 音频**（I2VA / FL2VA） | • UNet (`models/unet/`): `Abiray/MiniMax-H3-GGUF` → `unet/MiniMax-H3-FL2VA-Q4_K_M.gguf` (19.86 GB，可选 `--quant Q3_K_M` 降到 15.57 GB)<br>• Text Encoder (`models/text_encoders/`): `Abiray/MiniMax-H3-GGUF` → `text_encoders/qwen3vl_32b_minimax_h3-Q4_K_M.gguf` (14.58 GB)<br>• Video VAE (`models/vae/`): `Comfy-Org/MiniMax-H3` → `vae/minimax_h3_video_vae_fp16.safetensors` (5.21 GB)<br>• Audio VAE (`models/vae/`): `Comfy-Org/MiniMax-H3` → `vae/minimax_h3_audio_vae_fp32.safetensors` (0.61 GB)<br>• 8步加速 LoRA (`models/loras/`): `Comfy-Org/MiniMax-H3` → `loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors` (1.96 GB) | • `Abiray/MiniMax-H3-GGUF` → `minimax_fl2v_gguf_workflow.json`<br>• `vantagewithai/MiniMax-H3-comfyUI-GGUF` → `workflows/Vantage-Minimax-H3-8-Steps-Acc-FL2VA.json` |
| `ref2va-gguf` | **L4 (24GB)** / A100 | **参考图生视频 + 音频**（Ref2VA，主体/人物/服装一致性） | • UNet (`models/unet/`): `Abiray/MiniMax-H3-GGUF` → `unet/MiniMax-H3-Ref2VA-Q4_K_M.gguf` (19.85 GB，可选 `--quant Q3_K_M`)<br>• Text Encoder / Video VAE / Audio VAE 同上<br>• 4步加速 LoRA (`models/loras/`): `Comfy-Org/MiniMax-H3` → `loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors` (1.96 GB) | • `Abiray/MiniMax-H3-GGUF` → `minimax_ref2va_gguf_workflow.json`<br>• `vantagewithai/MiniMax-H3-comfyUI-GGUF` → `workflows/Vantage-Minimax-H3_4_steps-Ref2VA.json` |
| `fl2va-fp8` / `ref2va-fp8` | **A100 (40GB / 80GB)** | **官方 FP8 原生版**（精度更高） | • Diffusion (`models/diffusion_models/`): `Comfy-Org/MiniMax-H3` → `diffusion_models/minimax_h3_{fl2va\|ref2va}_pruned_fp8_scaled.safetensors` (20.96 GB)<br>• Text Encoder (`models/text_encoders/`): `Comfy-Org/MiniMax-H3` → `text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` (15.69 GB)<br>• VAEs & Turbo LoRAs 同上 | 同上（在 ComfyUI 节点中将加载器选为对应的 FP8 / AWQ 权重文件） |

### MiniMax H3 关键运行要点（务必提醒用户）
1. **CFG Scale 必须设为 `1.0`**：MiniMax H3 属于蒸馏/加速架构，CFG 超过 1.0（如传统的 7.0）会导致画面崩坏或报错。
2. **显存管理**：在 24GB L4 上，ComfyUI 启动时加上 `--lowvram`（脚本默认在显存 ≤26GB 时自动开启），确保 Qwen3-VL 文本编码器与 33B UNet 分时加载，不会爆显存。
3. **成片下载**：生成的视频默认保存在 Colab 远端 `/content/ComfyUI/output/`，除了直接在浏览器预览右键保存，也可以让 Agent 通过 `colab download -s <会话名> /content/ComfyUI/output/<文件名> ./` 批量拉回本地。
