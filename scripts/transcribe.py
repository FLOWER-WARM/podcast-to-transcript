# -*- coding: utf-8 -*-
"""faster-whisper 本地转写（CPU int8），支持长音频分片 + 断点续传。

用法:
  python transcribe.py <audio> <out_txt> [--model small] [--beam N] [--lang zh]
                       [--compute int8] [--chunk-min M] [--no-resume]

分片规则:
  --chunk-min 0（默认）  自动：音频 ≤120 分钟整条跑；>120 分钟按 30 分钟/片
  --chunk-min M         固定 M 分钟一片（可为小数，便于测试）
分片原因:
  1) 断点续传 —— 每片单独落盘，中断后重跑自动跳过已完成的片
  2) 抑制复读 —— faster-whisper 的 condition_on_previous_text 默认 True，
     会把上一段输出当提示喂给下一段；音频超过 ~2 小时易出现循环复读。
     分片让每片都是独立调用，上下文自然重置。
model 不传则自动用 <工作区>/model-<型号>，不存在再从 hf-mirror 下载并落成本地目录。

内存提醒: 整条音频会一次性解码为 float32/16kHz 进内存（约 时长秒 x 16000 x 4 字节）。
1 小时 ≈ 230MB，5 小时 ≈ 1.15GB。这是分片切片的前提，不额外放大占用。
"""
import argparse
import os
import sys
import time

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")  # 国内必须走镜像

DEFAULT_MODEL_REPO = "Systran/faster-whisper-small"
SR = 16000
AUTO_CHUNK_THRESHOLD_S = 120 * 60  # 超过 2 小时才自动分片
AUTO_CHUNK_MIN = 30.0


def ts(t: float) -> str:
    h, rem = divmod(int(t), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def ensure_model(spec: str) -> str:
    """spec 为 'small' 等短名时，解析为本地目录；缺失则下载到本地（不用 symlink）。"""
    if os.path.isdir(spec):
        return spec
    local = os.path.join(os.getcwd(), f"model-{spec}")
    if os.path.isfile(os.path.join(local, "model.bin")):
        return local
    # 下载到临时缓存，再把 blob 拷成实体文件（规避 Windows symlink 0 字节问题）
    from huggingface_hub import snapshot_download
    print(f"downloading model {spec} via {os.environ['HF_ENDPOINT']} ...", flush=True)
    cache = snapshot_download(DEFAULT_MODEL_REPO if spec == "small" else
                              f"Systran/faster-whisper-{spec}")
    src = os.path.join(cache, "snapshots")
    snap = os.path.join(src, os.listdir(src)[0])
    os.makedirs(local, exist_ok=True)
    import shutil
    for name in ("model.bin", "config.json", "tokenizer.json", "vocabulary.txt"):
        p = os.path.join(snap, name)
        if os.path.getsize(p) > 0:
            shutil.copyfile(p, os.path.join(local, name))
        else:  # symlink 损坏，从 blobs 按 hash 找实体
            real = os.path.realpath(p)
            if os.path.isfile(real):
                shutil.copyfile(real, os.path.join(local, name))
    return local


def snap_boundary(samples, idx: int, search_sec: float = 6.0) -> int:
    """把切点挪到附近能量最低处，尽量不切在字中间。"""
    frame = int(0.02 * SR)  # 20ms 一帧
    lo = max(0, idx - int(search_sec * SR))
    hi = min(len(samples), idx + int(search_sec * SR))
    seg = samples[lo:hi]
    n = len(seg) // frame
    if n < 3:
        return idx
    energy = (seg[:n * frame].reshape(n, frame) ** 2).mean(axis=1)
    k = int(energy.argmin())
    return lo + k * frame + frame // 2


def build_bounds(samples, chunk_min: float):
    """返回 [(start_sample, end_sample), ...]；chunk_min<=0 则整条一段。"""
    total = len(samples)
    if chunk_min <= 0 or total <= int(chunk_min * 60 * SR):
        return [(0, total)]
    step = int(chunk_min * 60 * SR)
    bounds = []
    s = 0
    while s < total:
        e = min(s + step, total)
        if e < total:
            snapped = snap_boundary(samples, e)
            # 只有挪动幅度合理时才采纳，避免把片切成畸形长度
            if s + step // 2 < snapped <= e + 6 * SR:
                e = snapped
        if e <= s:
            e = min(s + step, total)
        bounds.append((s, e))
        s = e
    return bounds


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("out_txt")
    ap.add_argument("--model", default="small")
    ap.add_argument("--beam", type=int, default=5)
    ap.add_argument("--lang", default="zh")
    ap.add_argument("--compute", default="int8")
    ap.add_argument("--chunk-min", type=float, default=0.0,
                    help="每片分钟数；0=自动（>2h 才分片），可为小数")
    ap.add_argument("--no-resume", action="store_true", help="忽略已有分片，全部重转")
    args = ap.parse_args()

    from faster_whisper import WhisperModel
    from faster_whisper.audio import decode_audio

    t0 = time.time()
    model_dir = ensure_model(args.model)
    print(f"loading {model_dir} ({args.compute}/cpu)", flush=True)
    model = WhisperModel(model_dir, device="cpu", compute_type=args.compute,
                         cpu_threads=os.cpu_count() or 4)
    print(f"model ready in {time.time()-t0:.1f}s", flush=True)

    print("decoding audio ...", flush=True)
    samples = decode_audio(args.audio, sampling_rate=SR)
    total = len(samples)
    dur = total / SR
    print(f"audio {dur/60:.1f} min; decoded {samples.nbytes/1024**2:.0f} MB in RAM", flush=True)

    chunk_min = args.chunk_min
    auto = chunk_min == 0
    if auto:
        chunk_min = AUTO_CHUNK_MIN if dur > AUTO_CHUNK_THRESHOLD_S else 0.0
    bounds = build_bounds(samples, chunk_min)

    est = dur * 1.17 / 60
    mode = f"分片 {chunk_min:g} min x {len(bounds)}" if len(bounds) > 1 else "整条"
    print(f"mode={mode}; 预计耗时 ≈ {est:.0f} min"
          f"（small/int8/beam{args.beam}：音频时长 x1.17，beam=1 约减半）", flush=True)

    parts_dir = os.path.join(os.path.dirname(os.path.abspath(args.audio)),
                             os.path.splitext(os.path.basename(args.audio))[0] + ".parts")
    os.makedirs(parts_dir, exist_ok=True)

    t1 = time.time()
    for i, (s, e) in enumerate(bounds):
        part = os.path.join(parts_dir, f"part{i:03d}.txt")
        tag = f"[{i+1}/{len(bounds)}] {ts(s/SR)}-{ts(e/SR)}"
        if os.path.isfile(part) and not args.no_resume:
            print(f"  {tag} 已完成，跳过（续传）", flush=True)
            continue
        segs, _info = model.transcribe(
            samples[s:e], language=args.lang, beam_size=args.beam,
            vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500))
        off = s / SR
        n = 0
        with open(part, "w", encoding="utf-8") as f:
            for seg in segs:
                f.write(f"[{ts(seg.start + off)}] {seg.text.strip()}\n")
                f.flush()
                n += 1
                if n % 50 == 0:
                    print(f"    {tag} seg {n} @ {ts(seg.start + off)}", flush=True)
        print(f"  {tag} 完成 {n} 段，累计 {time.time()-t1:.0f}s", flush=True)

    with open(args.out_txt, "w", encoding="utf-8") as out:
        total_seg = 0
        for i in range(len(bounds)):
            part = os.path.join(parts_dir, f"part{i:03d}.txt")
            if not os.path.isfile(part):
                print(f"警告：缺少分片 {part}，输出不完整", file=sys.stderr)
                continue
            with open(part, encoding="utf-8") as f:
                for line in f:
                    out.write(line)
                    if line.strip():
                        total_seg += 1
    print(f"DONE segments={total_seg} total={time.time()-t0:.0f}s -> {args.out_txt} "
          f"(分片留在 {parts_dir}，可删)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
