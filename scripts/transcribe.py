# -*- coding: utf-8 -*-
"""faster-whisper 本地转写（CPU int8）。
用法:
  python transcribe.py <audio> <out_txt> [--model DIR] [--beam N] [--lang zh] [--compute int8]
model 不传则自动用 <工作区>/model-small，不存在再从 hf-mirror 下载并落成本地目录。
"""
import argparse
import os
import sys
import time

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")  # 国内必须走镜像

DEFAULT_MODEL_REPO = "Systran/faster-whisper-small"


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("out_txt")
    ap.add_argument("--model", default="small")
    ap.add_argument("--beam", type=int, default=5)
    ap.add_argument("--lang", default="zh")
    ap.add_argument("--compute", default="int8")
    args = ap.parse_args()

    from faster_whisper import WhisperModel

    t0 = time.time()
    model_dir = ensure_model(args.model)
    print(f"loading {model_dir} ({args.compute}/cpu)", flush=True)
    model = WhisperModel(model_dir, device="cpu", compute_type=args.compute,
                         cpu_threads=os.cpu_count() or 4)
    print(f"model ready in {time.time()-t0:.1f}s", flush=True)

    segments, info = model.transcribe(
        args.audio, language=args.lang, beam_size=args.beam,
        vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500))
    print(f"audio {info.duration/60:.1f} min; 预计耗时 ≈ {info.duration*1.17/60:.0f} min"
          f"（small/int8/beam5 口径，beam=1 约减半）", flush=True)

    n = 0
    t1 = time.time()
    with open(args.out_txt, "w", encoding="utf-8") as f:
        for seg in segments:
            f.write(f"[{ts(seg.start)}] {seg.text.strip()}\n")
            f.flush()
            n += 1
            if n % 50 == 0:
                print(f"  seg {n} @ {ts(seg.start)} / {ts(info.duration)} "
                      f"elapsed {time.time()-t1:.0f}s", flush=True)
    print(f"DONE segments={n} total={time.time()-t0:.0f}s -> {args.out_txt}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
