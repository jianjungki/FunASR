# Speech Applications

Choose the application first, then select its model and serving contract.
The [use-case guide](../use_case_showcase.md) and
[community integrations](../community_projects.md) provide the maintained recipes.

## Audio Cut

Use [FunClip](https://github.com/modelscope/FunClip) for transcript-driven audio
and video clipping. For speaker-attributed recordings, start with
[MOSS-Transcribe-Diarize](../moss_transcribe_diarize.md): it produces transcription,
timestamps and anonymous speaker labels without an external VAD/speaker pipeline.
These labels are not verified real-world identities. Check the chosen FunClip
release and backend before assuming every ASR option has the same output fields.

## Realtime Speech Recognition

Start with the [deployment matrix](../deployment_matrix.md) and
[C++ WebSocket protocol](../../runtime/docs/websocket_protocol.md).
Python vLLM preview sessions and native C++ streaming services use different
messages and state transitions; their clients are not interchangeable.
Use the [realtime benchmark methodology](../benchmark/realtime_ws_benchmark.md)
to measure end-to-end latency under your traffic pattern.

MOSS is a long-form transcription/diarization option, not a replacement for a
native low-latency streaming model. Receiving an upload in chunks does not make
the underlying model a streaming recognizer.

## Audio Chat

For file or utterance transcription in an agent workflow, follow the
[Python HTTP service](../../examples/openai_api/README.md) and its
[workflow integration guide](../../examples/openai_api/WORKFLOWS.md).
FunASR supplies recognition; dialogue generation, speech synthesis, turn-taking
and interruption handling are separate application components. Validate their
combined latency and privacy requirements before deployment.

Next: [model selection](../model_selection.md),
[HTTP security](../../examples/openai_api/SECURITY.md),
and [troubleshooting](../troubleshooting.md).
