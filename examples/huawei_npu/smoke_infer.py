#!/usr/bin/env python3
"""Run a minimal FunASR inference smoke test on CPU, CUDA, or Huawei Ascend NPU."""

import argparse
import json
import time


def parse_args():
    parser = argparse.ArgumentParser(description="FunASR Huawei Ascend NPU smoke inference")
    parser.add_argument("--device", default="npu:0", help="Inference device, for example npu:0 or cpu")
    parser.add_argument("--model", default="paraformer-zh", help="FunASR model name or path")
    parser.add_argument(
        "--audio",
        default="https://isv-data.oss-cn-hangzhou.aliyuncs.com/ics/MaaS/ASR/test_audio/asr_example_zh.wav",
        help="Audio path or URL",
    )
    parser.add_argument("--batch-size", type=int, default=1, help="Inference batch size")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    from funasr import AutoModel

    start = time.perf_counter()
    model = AutoModel(model=args.model, device=args.device, disable_update=True)
    load_seconds = time.perf_counter() - start

    actual_device = model.kwargs.get("device", args.device)
    print(f"Requested device: {args.device}")
    print(f"Actual device: {actual_device}")
    print(f"Model load seconds: {load_seconds:.3f}")

    start = time.perf_counter()
    result = model.generate(input=args.audio, batch_size=args.batch_size)
    infer_seconds = time.perf_counter() - start

    print(f"Inference seconds: {infer_seconds:.3f}")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if args.device.startswith("npu") and not str(actual_device).startswith("npu"):
        print("WARNING: requested NPU but FunASR fell back to another device.")
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
