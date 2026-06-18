#!/usr/bin/env python3
"""Check whether the current Python environment can use Huawei Ascend NPU with FunASR."""

import importlib
import importlib.util
import platform
import sys


def has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def print_status(name: str, ok: bool, detail: str = "") -> None:
    marker = "OK" if ok else "FAIL"
    suffix = f" - {detail}" if detail else ""
    print(f"[{marker}] {name}{suffix}")


def main() -> int:
    print(f"Python: {sys.version.split()[0]}")
    print(f"Platform: {platform.platform()}")

    torch_ok = has_module("torch")
    print_status("torch importable", torch_ok)
    if not torch_ok:
        return 1

    import torch

    print(f"torch: {torch.__version__}")

    torch_npu_ok = has_module("torch_npu")
    print_status("torch_npu importable", torch_npu_ok)
    if not torch_npu_ok:
        return 1

    torch_npu = importlib.import_module("torch_npu")

    npu_module = getattr(torch_npu, "npu", None) or getattr(torch, "npu", None)
    npu_available = bool(npu_module and npu_module.is_available())
    print_status("NPU available", npu_available)

    cann_version = getattr(torch.version, "cann", None)
    if cann_version:
        print(f"CANN: {cann_version}")

    if npu_module and hasattr(npu_module, "device_count"):
        try:
            print(f"NPU count: {npu_module.device_count()}")
        except Exception as exc:
            print_status("NPU count query", False, str(exc))

    funasr_ok = has_module("funasr")
    print_status("funasr importable", funasr_ok)

    if funasr_ok:
        from funasr.auto.auto_model import is_npu_available

        print_status("FunASR NPU availability helper", is_npu_available())

    return 0 if npu_available and funasr_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
