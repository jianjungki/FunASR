"""
FunASR OpenAI-Compatible API Server

Drop-in replacement for OpenAI's /v1/audio/transcriptions endpoint.
Works with any agent framework that supports OpenAI audio API.

Usage:
    python server.py --model sensevoice --device cuda --port 8000

Then use with any OpenAI-compatible client:
    curl http://localhost:8000/v1/audio/transcriptions \
      -F file=@audio.wav -F model=sensevoice
"""

import argparse
import tempfile
import time
import os
import re
import logging
from typing import Optional

import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="FunASR OpenAI-Compatible API", version="1.0.0")

MODEL_REGISTRY = {}
DEVICE = "cpu"

MODEL_CONFIGS = {
    "sensevoice": {
        "model": "iic/SenseVoiceSmall",
        "vad_model": "fsmn-vad",
        "spk_model": "cam++",
        "spk_mode": "vad_segment",
        "punc_model": "ct-punc",
        "vad_kwargs": {"max_single_segment_time": 30000},
    },
    "paraformer": {
        "model": "paraformer-zh",
        "vad_model": "fsmn-vad",
        "punc_model": "ct-punc",
    },
    "paraformer-en": {
        "model": "paraformer-en",
        "vad_model": "fsmn-vad",
    },
    "fun-asr-nano": {
        "model": "FunAudioLLM/Fun-ASR-Nano-2512",
        "hub": "hf",
        "trust_remote_code": True,
        "vad_model": "fsmn-vad",
        "vad_kwargs": {"max_single_segment_time": 30000},
    },
}


def load_model(model_name: str):
    """Load a model and store in registry."""
    if model_name in MODEL_REGISTRY:
        logger.debug(f"Using cached model '{model_name}'")
        return MODEL_REGISTRY[model_name]

    if model_name not in MODEL_CONFIGS:
        available = list(MODEL_CONFIGS.keys())
        raise ValueError(f"Unknown model '{model_name}'. Available: {available}")

    from funasr import AutoModel

    cfg = MODEL_CONFIGS[model_name].copy()
    cfg["device"] = DEVICE
    cfg["disable_update"] = True

    logger.info(f"Loading model '{model_name}' on {DEVICE}...")
    logger.debug(f"Model config for '{model_name}': {cfg}")
    t0 = time.time()
    model = AutoModel(**cfg)
    elapsed = time.time() - t0
    logger.info(f"Model '{model_name}' loaded in {elapsed:.1f}s")
    logger.debug(f"Model '{model_name}' instance: {type(model).__name__}")

    MODEL_REGISTRY[model_name] = model
    return model


def clean_text(text: str) -> str:
    """Remove SenseVoice special/control tags from output."""
    if text is None:
        return ""
    text = str(text)
    text = re.sub(r"<\s*\|[^<>]*?\|\s*>", "", text)
    text = re.sub(r"<\s*\|[^<>]*$", "", text)
    text = re.sub(r"^[^<>]*?\|\s*>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def srt_time(seconds: float) -> str:
    """Format seconds as an SRT timestamp."""
    seconds = max(float(seconds), 0.0)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis == 1000:
        secs += 1
        millis = 0
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def vtt_time(seconds: float) -> str:
    """Format seconds as a WebVTT timestamp."""
    return srt_time(seconds).replace(",", ".")


def timestamp_to_seconds(value) -> float:
    """Normalize FunASR timestamp values to seconds."""
    value = float(value)
    return value / 1000.0 if value > 1000 else value


def split_subtitle_text(text: str, max_chars: int = 28):
    """Split plain text into subtitle-sized chunks."""
    text = clean_text(text)
    if not text:
        return []

    chunks = []
    buffer = ""
    for part in re.findall(r"[^。！？.!?]+[。！？.!?]?", text):
        part = part.strip()
        if not part:
            continue
        while len(part) > max_chars:
            chunks.append(part[:max_chars])
            part = part[max_chars:]
        if len(buffer) + len(part) <= max_chars:
            buffer += part
        else:
            if buffer:
                chunks.append(buffer)
            buffer = part
    if buffer:
        chunks.append(buffer)
    return chunks or [text]


def build_approximate_segments(text: str, duration_seconds: Optional[float], max_segment_seconds: float = 6.0):
    """Build readable subtitle segments when reliable timestamps are unavailable."""
    chunks = split_subtitle_text(text)
    if not chunks:
        return []

    if not duration_seconds or duration_seconds <= 0:
        duration_seconds = max(len(chunks) * max_segment_seconds, max_segment_seconds)

    total_chars = max(sum(len(chunk) for chunk in chunks), 1)
    segments = []
    cursor = 0.0
    for index, chunk in enumerate(chunks):
        if index == len(chunks) - 1:
            end = duration_seconds
        else:
            ratio = len(chunk) / total_chars
            end = min(duration_seconds, cursor + max(0.8, duration_seconds * ratio))
        if end <= cursor:
            end = min(duration_seconds, cursor + 0.8)
        segments.append({"start": round(cursor, 3), "end": round(end, 3), "text": chunk})
        cursor = end
        if cursor >= duration_seconds:
            break
    return segments


def has_valid_segment_timing(segments, duration_seconds: Optional[float] = None) -> bool:
    """Return whether generated segment timestamps are plausible."""
    if not segments:
        return False

    previous_start = -1.0
    for seg in segments:
        try:
            start = float(seg.get("start", 0))
            end = float(seg.get("end", 0))
        except (TypeError, ValueError):
            return False
        if start < 0 or end <= start or start < previous_start:
            return False
        if duration_seconds and (start > duration_seconds + 1.0 or end > duration_seconds + 1.0):
            return False
        previous_start = start
    return True


def parse_timestamp_item(timestamp, words, index):
    """Parse dict, [start, end], or [token, start, end] timestamp entries."""
    if isinstance(timestamp, dict):
        start = timestamp_to_seconds(timestamp.get("start_time", timestamp.get("start", 0)))
        end = timestamp_to_seconds(timestamp.get("end_time", timestamp.get("end", start)))
        token = clean_text(timestamp.get("token", timestamp.get("word", "")))
        return start, end, token

    if not isinstance(timestamp, (list, tuple)):
        return None

    if len(timestamp) >= 3 and isinstance(timestamp[0], str):
        token = clean_text(timestamp[0])
        start = timestamp_to_seconds(timestamp[1])
        end = timestamp_to_seconds(timestamp[2])
        return start, end, token

    if len(timestamp) >= 2:
        start = timestamp_to_seconds(timestamp[0])
        end = timestamp_to_seconds(timestamp[1])
        token = clean_text(words[index]) if index < len(words) else ""
        return start, end, token

    return None


def build_segments(result_item, duration_seconds: Optional[float] = None, max_segment_seconds: float = 6.0):
    """Build subtitle segments from sentence_info or timestamp output."""
    segments = []
    for seg in result_item.get("sentence_info", []) or []:
        text = clean_text(seg.get("text", ""))
        if not text:
            continue
        segments.append({
            "start": timestamp_to_seconds(seg.get("start", 0)),
            "end": timestamp_to_seconds(seg.get("end", 0)),
            "text": text,
            "speaker": seg.get("spk", None),
        })

    if has_valid_segment_timing(segments, duration_seconds):
        return segments

    timestamps = result_item.get("timestamp", []) or []
    words = result_item.get("words", []) or []
    if not timestamps:
        return build_approximate_segments(result_item.get("text", ""), duration_seconds, max_segment_seconds)

    segments = []
    current_text = []
    current_start = None
    current_end = None
    for index, timestamp in enumerate(timestamps):
        parsed = parse_timestamp_item(timestamp, words, index)
        if parsed is None:
            continue
        start, end, token = parsed

        if not token:
            continue
        if current_start is None:
            current_start = start
        current_text.append(token)
        current_end = end

        should_flush = (
            token[-1:] in "。！？.!?"
            or (current_end - current_start) >= max_segment_seconds
        )
        if should_flush:
            segments.append({"start": current_start, "end": current_end, "text": "".join(current_text).strip()})
            current_text = []
            current_start = None
            current_end = None

    if current_text and current_start is not None:
        segments.append({"start": current_start, "end": current_end, "text": "".join(current_text).strip()})

    if has_valid_segment_timing(segments, duration_seconds):
        return segments

    logger.warning("Timestamp output is invalid for subtitle generation; using approximate timing fallback.")
    return build_approximate_segments(result_item.get("text", ""), duration_seconds, max_segment_seconds)


def format_srt(segments) -> str:
    """Format subtitle segments as SRT."""
    lines = []
    for index, seg in enumerate(segments, 1):
        lines.extend([
            str(index),
            f"{srt_time(seg.get('start', 0))} --> {srt_time(seg.get('end', 0))}",
            seg.get("text", ""),
            "",
        ])
    return "\n".join(lines)


def format_vtt(segments) -> str:
    """Format subtitle segments as WebVTT."""
    lines = ["WEBVTT", ""]
    for seg in segments:
        lines.extend([
            f"{vtt_time(seg.get('start', 0))} --> {vtt_time(seg.get('end', 0))}",
            seg.get("text", ""),
            "",
        ])
    return "\n".join(lines)


def get_audio_duration(path: str) -> Optional[float]:
    """Return audio duration in seconds when torchaudio can read metadata."""
    try:
        import torchaudio

        metadata = torchaudio.info(path)
        if metadata.sample_rate and metadata.num_frames:
            return metadata.num_frames / metadata.sample_rate
    except Exception as exc:
        logger.warning(f"Unable to read audio duration for subtitles: {exc}")
    return None


def format_speaker_segments(segments):
    """Format diarized segments as human-readable speaker lines."""
    formatted_lines = []
    for index, seg in enumerate(segments):
        logger.debug(f"Formatting segment {index}: {seg}")
        start_raw = seg.get("start", seg.get("start_time", 0))
        end_raw = seg.get("end", seg.get("end_time", 0))
        logger.debug(f"Segment {index} raw start/end: start={start_raw}, end={end_raw}")
        if start_raw is None or end_raw is None:
            logger.warning(f"Skipping segment {index} because start/end is missing: {seg}")
            continue
        try:
            start = float(start_raw) / 1000.0
            end = float(end_raw) / 1000.0
        except (TypeError, ValueError) as exc:
            logger.warning(f"Skipping segment {index} because timestamps are invalid: {seg}, error={exc}")
            continue
        speaker = seg.get("spk", None)
        if speaker is None:
            speaker = seg.get("speaker", index)
        text = clean_text(seg.get("text", ""))
        if not text:
            logger.debug(f"Segment {index} has empty text: {seg}")
        line = f"[{start:0>5.1f} → {end:0>5.1f}] Speaker {speaker}: {text}"
        logger.debug(f"Formatted segment {index}: {line}")
        formatted_lines.append(line)
    return formatted_lines


@app.post("/v1/audio/transcriptions")
async def transcribe(
    file: UploadFile = File(...),
    model: str = Form(default="sensevoice"),
    language: Optional[str] = Form(default=None),
    response_format: Optional[str] = Form(default="json"),
):
    """
    OpenAI-compatible audio transcription endpoint.
    
    Accepts the same parameters as OpenAI's /v1/audio/transcriptions:
    - file: Audio file (wav, mp3, flac, m4a, ogg, webm)
    - model: Model to use (sensevoice, paraformer, fun-asr-nano)
    - language: Optional language hint
    - response_format: json or verbose_json
    """
    if model not in MODEL_CONFIGS:
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model}' not found. Available: {list(MODEL_CONFIGS.keys())}"
        )

    suffix = os.path.splitext(file.filename)[1] if file.filename else ".wav"
    logger.debug(
        f"Received transcription request: filename={file.filename}, suffix={suffix}, model={model}, language={language}, response_format={response_format}"
    )
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        logger.debug(f"Uploaded file size: {len(content)} bytes")
        tmp.write(content)
        tmp_path = tmp.name
    logger.debug(f"Temporary file created at: {tmp_path}")

    try:
        asr_model = load_model(model)
        t0 = time.time()

        generate_kwargs = {
            "input": tmp_path,
            "batch_size": 1,
            "merge_vad": True,
            "merge_length_s": 15,
            "output_timestamp": True,
            "sentence_timestamp": True,
        }
        if language:
            generate_kwargs["language"] = language
        logger.debug(f"Generate kwargs: {generate_kwargs}")

        result = asr_model.generate(**generate_kwargs)
        logger.debug(f"Raw transcription result: {result}")
        elapsed = time.time() - t0

        text = clean_text(result[0]["text"])

        audio_duration = get_audio_duration(tmp_path)
        segments = build_segments(result[0], audio_duration)

        if response_format == "srt":
            return PlainTextResponse(format_srt(segments) if segments else text, media_type="text/plain; charset=utf-8")
        if response_format == "vtt":
            return PlainTextResponse(format_vtt(segments) if segments else text, media_type="text/vtt; charset=utf-8")
        if response_format == "verbose_json":
            return JSONResponse({
                "text": text,
                "segments": segments,
                "language": language or "auto",
                "duration": round(elapsed, 3),
                "model": model,
            })
        else:
            return JSONResponse({"text": text})

    except Exception as e:
        logger.exception(f"Transcription error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.unlink(tmp_path)


@app.post("/v1/audio/transcriptions/speaker")
async def transcribe_with_speakers(
    file: UploadFile = File(...),
    model: str = Form(default="sensevoice-cam++"),
    language: Optional[str] = Form(default=None),
):
    """
    Speaker-formatted transcription endpoint.

    Returns text lines like:
    [00:00.4 → 00:03.8] Speaker 0: Let's discuss the Q3 plan.
    """
    if model not in MODEL_CONFIGS:
        raise HTTPException(
            status_code=400,
            detail=f"Model '{model}' not found. Available: {list(MODEL_CONFIGS.keys())}"
        )

    suffix = os.path.splitext(file.filename)[1] if file.filename else ".wav"
    logger.debug(
        f"Received speaker transcription request: filename={file.filename}, suffix={suffix}, model={model}, language={language}"
    )
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        logger.debug(f"Uploaded speaker file size: {len(content)} bytes")
        tmp.write(content)
        tmp_path = tmp.name
    logger.debug(f"Temporary speaker file created at: {tmp_path}")

    try:
        asr_model = load_model(model)
        generate_kwargs = {
            "input": tmp_path,
            "batch_size": 1
        }
        if language:
            generate_kwargs["language"] = language
        logger.debug(f"Speaker generate kwargs: {generate_kwargs}")

        result = asr_model.generate(**generate_kwargs)
        logger.debug(f"Raw speaker transcription result: {result}")
        if result:
            logger.debug(f"Result[0] keys: {list(result[0].keys())}")
            logger.debug(f"Result[0] full payload: {result[0]}")
        sentence_info = result[0].get("sentence_info", []) if result else []
        logger.debug(f"sentence_info count: {len(sentence_info)}")
        logger.debug(f"sentence_info payload: {sentence_info}")

        if sentence_info:
            lines = format_speaker_segments(sentence_info)
            texts = [clean_text(seg.get("text", "")) for seg in sentence_info]
            text = " ".join(part for part in texts if part).strip()
        else:
            text = clean_text(result[0].get("text", "")) if result else ""
            logger.debug(f"No sentence_info found, fallback text: {text}")
            lines = [f"[00:00.0 → 00:00.0] Speaker 0: {text}"] if text else []

        if not lines:
            fallback_text = clean_text(result[0].get("text", "")) if result else ""
            logger.warning(
                f"No valid speaker lines produced; using fallback text. sentence_info={sentence_info}, fallback_text={fallback_text}"
            )
            text = fallback_text
            lines = [f"[00:00.0 → 00:00.0] Speaker 0: {text}"] if text else []

        logger.debug(f"Speaker formatted lines: {lines}")
        logger.debug(f"Speaker response text: {text}")
        return JSONResponse({
            "text": text,
            "lines": lines,
            "model": model,
            "language": language or "auto",
        })
    except Exception as e:
        logger.exception(f"Speaker transcription error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.unlink(tmp_path)


@app.get("/v1/models")
async def list_models():
    """List available models (OpenAI-compatible)."""
    models = []
    for name in MODEL_CONFIGS:
        models.append({
            "id": name,
            "object": "model",
            "created": 1700000000,
            "owned_by": "funasr",
            "ready": name in MODEL_REGISTRY,
        })
    return JSONResponse({"object": "list", "data": models})


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "device": DEVICE,
        "models_loaded": list(MODEL_REGISTRY.keys()),
        "models_available": list(MODEL_CONFIGS.keys()),
    }


def main():
    parser = argparse.ArgumentParser(description="FunASR OpenAI-Compatible API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8000, help="Bind port")
    parser.add_argument("--device", default="cuda", help="Device: cuda, cpu, mps")
    parser.add_argument("--model", default="sensevoice", help="Pre-load model at startup")
    args = parser.parse_args()

    global DEVICE
    DEVICE = args.device

    load_model(args.model)

    logger.info(f"FunASR API server starting on http://{args.host}:{args.port}")
    logger.info(f"  Device: {DEVICE}")
    logger.info(f"  Models: {list(MODEL_CONFIGS.keys())}")
    logger.info(f"  Docs:   http://{args.host}:{args.port}/docs")
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
