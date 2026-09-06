# -*- coding: utf-8 -*-
"""舞蹈视频时长免疫切分器 v2（PyAV h264 版）
用法：把任意时长的舞蹈视频拖到「视频切分.bat」上
输出：自动统一格式（540x960/24fps/h264）并按 405 帧一段切分，片段直接放进 ComfyUI input 目录
v2 修复：顺序解码（不再 seek，杜绝黑帧）+ h264 编码（ComfyUI 可直接读取，mp4v 会被拒）
"""
import os
import sys
import glob
import av
from fractions import Fraction
import numpy as np

INPUT_DIR = r"D:\Comfy-Desktop\ComfyUI-Shared\input"
CHUNK_FRAMES = 405          # 一键工作流五段框架的容量（5 × 81）
TARGET_W, TARGET_H = 540, 960
TARGET_FPS = 24


def make_resizer():
    try:
        import cv2

        def resize(arr):
            ih, iw = arr.shape[:2]
            target_ratio = TARGET_W / TARGET_H
            cur_ratio = iw / ih
            if abs(cur_ratio - target_ratio) > 0.01:
                if cur_ratio > target_ratio:
                    nw = int(ih * target_ratio)
                    x0 = (iw - nw) // 2
                    arr = arr[:, x0:x0 + nw]
                else:
                    nh = int(iw / target_ratio)
                    y0 = (ih - nh) // 2
                    arr = arr[y0:y0 + nh, :]
            return cv2.resize(arr, (TARGET_W, TARGET_H), interpolation=cv2.INTER_AREA)
        return resize
    except Exception:
        def resize(arr):
            ih, iw = arr.shape[:2]
            target_ratio = TARGET_W / TARGET_H
            cur_ratio = iw / ih
            if abs(cur_ratio - target_ratio) > 0.01:
                if cur_ratio > target_ratio:
                    nw = int(ih * target_ratio)
                    arr = arr[:, (iw - nw) // 2:(iw - nw) // 2 + nw]
                else:
                    nh = int(iw / target_ratio)
                    arr = arr[(ih - nh) // 2:(ih - nh) // 2 + nh, :]
            ys = (np.arange(TARGET_H) * ih // TARGET_H).clip(0, ih - 1)
            xs = (np.arange(TARGET_W) * iw // TARGET_W).clip(0, iw - 1)
            return arr[ys][:, xs]
        return resize


def split_video(src):
    try:
        container = av.open(src)
    except Exception as e:
        print("无法打开视频:", src, e)
        return
    stream = container.streams.video[0]
    src_fps = float(stream.average_rate or stream.base_rate or stream.guessed_rate) or 30.0
    if src_fps <= 0:
        src_fps = 30.0
    total = stream.frames or 0
    w = stream.codec_context.width
    h = stream.codec_context.height
    dur = float(container.duration or 0) / 1_000_000
    if total <= 0 and dur > 0:
        total = int(dur * src_fps)
    print(f"源视频: {total} 帧 {w}x{h} @{round(src_fps,2)}fps = {round(total/src_fps,1) if total else round(dur,1)} 秒")

    for old in glob.glob(os.path.join(INPUT_DIR, "舞蹈片段_*.mp4")):
        os.remove(old)

    ratio = src_fps / TARGET_FPS
    total_out = int(round(total / ratio)) if total > 0 else 0
    if total_out <= 0:
        print("无法确定帧数，退出")
        return
    n_chunks = (total_out + CHUNK_FRAMES - 1) // CHUNK_FRAMES
    print(f"重采样后帧数: {total_out} @{TARGET_FPS}fps = {round(total_out/TARGET_FPS,1)} 秒")
    print(f"切分为 {n_chunks} 个片段（每段最多 {CHUNK_FRAMES} 帧 ≈ {round(CHUNK_FRAMES/TARGET_FPS,1)} 秒）")

    resize = make_resizer()
    state = {"writer": None, "ci": 0, "in_chunk": 0}

    def flush():
        wr = state["writer"]
        if wr is not None:
            for pkt in wr.encode(None):
                wr.container.mux(pkt)
            wr.container.close()
            state["writer"] = None

    def open_next():
        flush()
        state["ci"] += 1
        state["in_chunk"] = 0
        name = f"舞蹈片段_{state['ci']:02d}.mp4"
        path = os.path.join(INPUT_DIR, name)
        cout = av.open(path, "w")
        vs = cout.add_stream("h264", rate=TARGET_FPS)
        vs.width = TARGET_W
        vs.height = TARGET_H
        vs.pix_fmt = "yuv420p"
        vs.options = {"crf": "18", "preset": "medium"}
        state["writer"] = vs
        print(f"  生成: {name}")

    try:
        open_next()
        next_take = 0.0
        out_idx = 0
        read = 0
        for frame in container.decode(video=0):
            while out_idx < total_out and int(next_take) <= read:
                arr = resize(frame.to_ndarray(format="bgr24"))
                vf = av.VideoFrame.from_ndarray(arr[:, :, ::-1], format="rgb24")
                vf.pts = state["in_chunk"]
                vf.time_base = Fraction(1, TARGET_FPS)
                wr = state["writer"]
                for pkt in wr.encode(vf):
                    wr.container.mux(pkt)
                out_idx += 1
                state["in_chunk"] += 1
                next_take += ratio
                if state["in_chunk"] >= CHUNK_FRAMES and out_idx < total_out:
                    open_next()
            if out_idx >= total_out:
                break
            read += 1
    finally:
        flush()
        container.close()

    print(f"\n完成！共 {n_chunks} 个片段已放入 {INPUT_DIR}")
    print("接下来：打开 换装舞蹈动作迁移.json，在 Load Video 里选 片段01，跑完再选 片段02，最后在剪映拼接")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        src = sys.argv[1]
    else:
        cands = sorted(glob.glob(os.path.join(INPUT_DIR, "*.mp4")),
                       key=os.path.getmtime, reverse=True)
        if not cands:
            print("用法：把舞蹈视频拖到 视频切分.bat 上；或先放一个 mp4 到 input 目录")
            sys.exit(1)
        src = cands[0]
        print("自动选用 input 里最新的视频:", os.path.basename(src))
    split_video(src)
