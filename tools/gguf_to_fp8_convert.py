# -*- coding: utf-8 -*-
"""GGUF(任意gguf量化) -> fp8_e4m3 safetensors 反量化转换
用法: python gguf_to_fp8_convert.py <输入.gguf> <输出.safetensors> [config.json字符串]
说明: 保留原文件的 config 元数据(如 animate2 架构声明)，用于 Wan-Animate-2 等
      靠元数据选架构的模型。输出为 fp8_e4m3 原生 dtype，可直接用标准 UNETLoader 加载。
"""
import os
import sys
import json
import importlib.util
import types as _t

def load_city96_loader(comfy_dir):
    gg = os.path.join(comfy_dir, "custom_nodes", "ComfyUI-GGUF")
    pkg = _t.ModuleType("comfyui_gguf_pkg")
    pkg.__path__ = [gg]
    sys.modules["comfyui_gguf_pkg"] = pkg
    spec = importlib.util.spec_from_file_location(
        "comfyui_gguf_pkg.loader", os.path.join(gg, "loader.py"),
        submodule_search_locations=[gg])
    mod = importlib.util.module_from_spec(spec)
    sys.modules["comfyui_gguf_pkg.loader"] = mod
    spec.loader.exec_module(mod)
    return mod

def main():
    if len(sys.argv) < 3:
        print(__doc__)
        print("示例: python gguf_to_fp8_convert.py in.gguf out.safetensors")
        sys.exit(1)
    src, dst = sys.argv[1], sys.argv[2]
    comfy_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "..", "..", "ComfyUI-Installs", "ComfyUI", "ComfyUI")
    comfy_dir = os.path.abspath(comfy_dir)
    if not os.path.isdir(os.path.join(comfy_dir, "custom_nodes", "ComfyUI-GGUF")):
        comfy_dir = r"D:\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI"

    mod = load_city96_loader(comfy_dir)
    import torch
    from safetensors.torch import save_file

    sd, extra = mod.gguf_sd_loader(src)
    metadata = dict((extra or {}).get("metadata", {}) or {})
    cfg = {}
    if metadata.get("config"):
        try:
            cfg = json.loads(metadata["config"])
        except Exception:
            cfg = {}

    print(f"张量数: {len(sd)}，开始反量化到 fp8_e4m3 ...")
    out_sd = {}
    for i, (k, v) in enumerate(sd.items()):
        if getattr(v, "tensor_shape", None) is not None:
            out_sd[k] = mod.ops.dequantize_tensor(v, torch.float8_e4m3fn).contiguous()
        else:
            out_sd[k] = v.to(torch.float8_e4m3fn).contiguous() if v.is_floating_point() else v.contiguous()
        if (i + 1) % 200 == 0:
            print(f"  {i+1}/{len(sd)}")

    # 保留架构元数据
    meta = {"format": "pt"}
    if cfg:
        meta["config"] = json.dumps(cfg)
    elif metadata.get("config"):
        meta["config"] = metadata["config"]

    print(f"写入 {dst} ...")
    save_file(out_sd, dst, metadata=meta)
    print(f"完成: {os.path.getsize(dst)/1024/1024/1024:.2f} GB")

if __name__ == "__main__":
    main()
