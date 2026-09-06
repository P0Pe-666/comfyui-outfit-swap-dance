# 换装 + 舞蹈动作迁移 · 本地 ComfyUI 全流程

两段式工作流：**换装模块**（Qwen-Image-Edit-2511 把任意服装穿到任意模特身上）→ **舞蹈模块**（Wan-Animate-2 让换装后的模特跟随任意舞蹈视频运动）→ 可选 **SeedVR2 精修放大**。

全流程本地运行、开源模型、无 API 付费。在 RTX 5060 Ti 16GB 上实测：舞蹈出片约 20~40 分钟/条。

## 特性

- 两段式解耦：换装图先肉眼确认，再进舞蹈段；换衣服/模特只需重跑换装（约 12 分钟）
- fp8 原生权重：绕开 int8_convrot 内核在 RTX 50 系（Blackwell）上的性能缺陷（实测 20+ 倍差距）
- SageAttention 强制启用：修复 50 系上注意力算子病态回退（GPU 100% 空转无进度）
- 时长免疫：成片时长 = 驱动视频时长；超过 17 秒的驱动视频用附带切分工具切段

## 硬件与环境

- NVIDIA GPU ≥16GB 显存（RTX 50 系实测，40/30 系理论上可用）
- ComfyUI 0.34+ （Desktop 或 portable 均可）
- 自定义节点：ComfyUI-GGUF、KJNodes、SeedVR2_VideoUpscaler、Crystools（可选）

## 安装

1. ComfyUI 装好上述自定义节点
2. 按下表下载模型到 `models/` 对应目录（国内可用 ModelScope / hf-mirror.com）

| 模型 | 目录 | 来源 |
|---|---|---|
| qwen_image_edit 20B GGUF（Q5_K_M/Q4_K_M） | models/GGUF 或 diffusion_models | ModelScope: Comfy-Org/Qwen-Image-Edit |
| umt5_xxl_fp8_e4m3fn_scaled | models/text_encoders | Comfy-Org/Wan-Animate-2 |
| clip_vision_h | models/clip_vision | Comfy-Org/Wan-Animate-2 |
| Wan2_1_VAE_bf16 | models/vae | Comfy-Org/Wan-Animate-2 |
| lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16 | models/loras | Comfy-Org/Wan-Animate-2 |
| wan_animate_2 fp8（见下方转换） | models/diffusion_models | 本仓库工具生成 |
| seedvr2_ema_3b_fp16 + ema_vae_fp16 | models/seedvr2 | Comfy-Org/SeedVR2 |

3. **生成 fp8 舞蹈模型**：下载官方 `wan_animate_2_int8_convrot.safetensors` 后，运行 `tools/gguf_to_fp8_convert.py` 反量化转存为 fp8 safetensors。
   原因：int8_convrot 的自定义内核在 RTX 50 系上回退到病态路径（实测每步 20+ 分钟）；fp8 原生 dtype 快 20 倍以上且无兼容问题。

## 使用

### 第一步：换装
打开 `workflows/stage_A_tryon_stocking.json` → 填入模特照片、服装照片 → 运行（约 12 分钟）→ **肉眼确认**换装图正常后进入第二步。

### 第二步：舞蹈
打开 `workflows/舞蹈模块.json` → 参考图选第一步的换装图 → 驱动视频选舞蹈视频（建议 720p/24fps，≤17 秒）→ 运行（约 20~40 分钟）。

### 第三步（可选）：精修
成片复制到 input 目录 → 打开 `workflows/成片精修放大.json` → LoadVideo 选中它 → 运行 → 输出 1080p 精修版（约 70 分钟）。

> 驱动视频超过 17 秒：先用 `tools/视频切分.bat` 切段，逐段生成后剪辑拼接。
> 成片尾部约 1.4 秒是驱动播完后的自由发挥段（模型机制使然），剪辑时剪掉。

## 已知问题与修复记录（踩坑实录）

| 症状 | 根因 | 处理 |
|---|---|---|
| GPU 100% 但每步 20+ 分钟、温度不高 | int8_convrot 自定义内核在 Blackwell 上回退慢速路径 | 模型转 fp8（附转换脚本） |
| GPU 100% 空转、进度条长时间 0% | PyTorch SDPA 在 sm_120 无高效内核 | 安装 sageattention+triton-windows，强制 sage（见 patches/说明.md） |
| LoRA 全部不生效（无报错） | 旧配方 LoRA 被 bypass | 恢复官方配方：LoRA 激活 + 6 步 + cfg 1.0 |
| 禁用 DynamicVRAM/async offload 后反而更慢 | 经典 lowvram 逐权重搬运远慢于 0.34 智能加载 | 保持默认（两者都开启） |
| GGUF 模型 LoRA 报形状错误 + forward 崩溃 | comfy 0.34 权重机制与 GGML 字节视图不兼容 | 同样用 fp8 转换规避 |

## 文件说明

```
workflows/
  stage_A_tryon_stocking.json   换装模块
  舞蹈模块.json                  舞蹈出片（fp8 + 6步 + LoRA）
  成片精修放大.json              SeedVR2 1080p 精修
tools/
  gguf_to_fp8_convert.py        GGUF→fp8 反量化转换
  视频切分.bat / 切分脚本.py     长视频切段（540×960/24fps/h264，405帧每段）
patches/说明.md                 ComfyUI 源码补丁说明（sage attention 强制启用）
```

## 致谢

- [ComfyUI](https://github.com/comfyanonymous/ComfyUI) 与 [Comfy-Org Wan-Animate-2 工作流模板](https://huggingface.co/Comfy-Org/Wan-Animate-2)
- [Wan-Animate-2](https://github.com/Wan-Video/Wan-Animate-2)（阿里 Wan-Video，Apache-2.0）
- [SeedVR2](https://github.com/ByteDance-Seed/SeedVR2)（ByteDance Seed）
- [ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF)（city96）、[SageAttention](https://github.com/thu-ml/SageAttention)、[Rebels W3A8 Loader](https://github.com/RealRebelAI/Rebels_w3a8_Loader)

## 许可

代码与工作流按 Apache-2.0 提供。模型权重遵循各上游模型的许可（Wan 系列含使用限制），生成内容的肖像权与合规责任由使用者自负。
