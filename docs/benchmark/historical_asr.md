# Historical ASR Benchmark

[中文](historical_asr_zh.md)

This is a historical record with incomplete provenance, retained for readers of
earlier FunASR comparisons. It is not a new measurement, a universal leaderboard,
or a guarantee for a current checkpoint, machine or deployment. For a new
evaluation, start with the [performance methodology](rtf_reproducibility.md).

## Historical Summary

The table below preserves the original report's wording and numbers. Its
"best" labels refer only to that report, not to all available models or hardware.

| Metric | Result |
| --- | --- |
| Dataset | 184 long-form Chinese audio files, 11,539 s total, 192.3 min. |
| GPU | NVIDIA H100 80GB HBM3. |
| Best GPU speed | SenseVoice-Small: 169.6x realtime in the full benchmark, 211.8x in the initial run. |
| Best CPU speed | SenseVoice-Small: 17.2x realtime; Paraformer-Large: 15.6x realtime. |
| Baseline | OpenAI Whisper-large-v3: 13.4x realtime on GPU. |

The **169.6x full run and 211.8x initial run are separate reported results**.
The original page does not disclose the measurement date. The source was
checked on **2026-09-07**, which is a snapshot audit date, not the measurement date.

## Historical Results

All values and notes in this table are archived claims from the original report.
The notes are not current API capability guarantees. In particular, a model's
raw tags do not imply that an HTTP endpoint returns those tags, and an old
timestamp limitation must not replace the current [model selection guide](../model_selection.md).

| Model | Device | RTF | Speed | CER | Notes |
| --- | --- | --- | --- | --- | --- |
| SenseVoice-Small | GPU | 0.005896 | 169.6x | 7.81% | ASR + language / emotion / event tags; CER after tag stripping. |
| Paraformer-Large | GPU | 0.008359 | 119.6x | 10.18% | Fast non-autoregressive Chinese ASR with VAD/punctuation pipeline. |
| Fun-ASR-Nano | GPU | 0.058803 | 17.0x | 8.06% | LLM-based ASR for Chinese, English, Japanese, seven Chinese dialect groups, and 26 regional accents; supports hotwords. Reliable checkpoint-native timestamps are not available ([#106](https://github.com/QwenAudio/Fun-ASR/issues/106)). |
| GLM-ASR-Nano | GPU | 0.026974 | 37.1x | 31.07% | LLM-based multilingual ASR. |
| Whisper-large-v3-turbo (OpenAI) | GPU | 0.021708 | 46.1x | 21.71% | OpenAI Whisper implementation. |
| Whisper-large-v3 (OpenAI) | GPU | 0.074694 | 13.4x | 20.02% | Baseline for large Whisper quality. |
| SenseVoice-Small | CPU | 0.057988 | 17.2x | 7.81% | CPU run from the remaining benchmark script. |
| Paraformer-Large | CPU | 0.064056 | 15.6x | 10.18% | CPU viable for batch jobs. |
| Fun-ASR-Nano | CPU | 0.274318 | 3.6x | 8.06% | LLM-based model is heavier but still above realtime. |

The repeated CPU/GPU CER values do not establish independent per-device scoring.
The raw predictions, references and scoring program are not available in the
audited record. The tag-stripping statement is preserved as a historical claim,
not as newly verified scorer output. Numerical precision and rounded speed/RTF
pairs are retained without recalculation.

## Provenance and Limitations

The [original English HTML](https://github.com/modelscope/FunASR/blob/67d63b80a246dc33749e43904c294e0409cd9183/benchmark.html)
is pinned to its historical GitHub Pages commit. Its bytes matched the archived
public page during the source audit. That establishes the source of this table,
not the correctness or reproducibility of the underlying measurements.

The old report describes RTF as total inference time divided by total audio
duration, and speed as its reciprocal. The latter is also called RTFx:

```text
RTF  = total inference time / total audio duration
RTFx = total audio duration / total inference time = 1 / RTF
```

The following commands are **historical text and cannot be run directly from
the audited checkout**. All three referenced files were absent at FunASR source
revision `386f6f9106684ba5a114e796147db4396a09eab5`; no replacement scripts or
reproduction data are supplied by this document.

```text
python benchmark/run_full_benchmark.py
python benchmark/run_remaining.py
python benchmark/fix_sensevoice_cer.py
```

The audited report does not provide a CPU model/thread count, dataset membership
and reference manifest, exact checkpoint revisions, software/driver versions,
per-file predictions or timing logs, or a complete timing scope covering warmup,
I/O and preprocessing. Without these materials, the old table is not directly
reproducible and its CPU-versus-GPU headline is not a production-wide guarantee.

This record's **11,539 seconds** must remain separate from the **11,541 seconds**
reported in the [vLLM methodology](rtf_reproducibility.md). Both mention 184 files,
but that alone does not prove identical dataset membership. Do not merge their
rows or silently normalize the two-second discrepancy.

## Choosing a Current Path

The following is the **original recommendation table, retained as historical
context only**. It is not a newly validated recommendation or performance ranking.

| Need | Recommended model |
| --- | --- |
| Fastest production transcription | SenseVoice-Small or Paraformer-Large. |
| CPU batch transcription | SenseVoice-Small first; Paraformer-Large for Chinese production pipelines. |
| Chinese/English/Japanese LLM-style recognition with dialect and accent coverage | Fun-ASR-Nano; use the separate [Fun-ASR-MLT-Nano](https://huggingface.co/FunAudioLLM/Fun-ASR-MLT-Nano-2512) checkpoint for 31 languages, and use [vLLM](../vllm_guide.md) for higher LLM decoding throughput. |
| OpenAI-compatible local endpoint | [funasr-server](../agent_integration.md) with model alias `sensevoice`, `paraformer`, or `fun-asr-nano`. |

For current decisions, use the [model and capability guide](../model_selection.md),
[Agent integration contracts](../agent_integration.md), and
[vLLM deployment guide](../vllm_guide.md). The separate MLT checkpoint's language
coverage must not be attributed to Fun-ASR-Nano. Evaluate your own audio, runtime
and end-to-end latency before selecting a deployment.

Use the [performance methodology](rtf_reproducibility.md) for new measurements
and the [WebSocket benchmark guide](realtime_ws_benchmark.md) for concurrent
realtime services. The current
[migration timing helper](../../examples/migration/benchmark_funasr.py) measures
FunASR on your own audio; it does not compute CER/WER, run Whisper or reproduce
the missing historical scripts. Keep your timing scope, failed files and quality
evaluation separate and explicit.
