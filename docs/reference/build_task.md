# Build custom tasks

This is the migration entry for the former Task-based tutorial. That tutorial
described an older FunASR architecture; its `AbsTask` / `ASRTask` examples are not
interfaces in the current checkout. Do not copy them into a new integration.

## Choose an extension point

| What you need | Maintained guide | What to verify |
| --- | --- | --- |
| Run an existing checkpoint | [Python SDK](../python_api.md) | Model, input and output contract |
| Fine-tune an existing architecture | [Training](../training.md) | Recipe, data format, checkpoint and evaluation |
| Add a model architecture | [Model registration](../model_registration.md) | Registry name, configuration, `inference()` and result fields |
| Connect a third-party model | [MOSS integration](../moss_transcribe_diarize.md) | Upstream attribution, dependencies and adapter boundary |
| Expose a transcription service | [Deployment matrix](../deployment_matrix.md) | Runtime, protocol and supported model combination |

The current model registration mechanism is implemented in
[register.py](../../funasr/register.py); inference orchestration is in
[auto_model.py](../../funasr/auto/auto_model.py). Registering a model is not the
same as adding support to every HTTP, WebSocket or C++ runtime. Follow the
specific service contract and test the intended route separately.

## Migrate an older extension

1. Record the original FunASR commit, configuration, checkpoint and dependency
   versions before changing the environment.
2. Choose a current recipe or registered model with matching inputs and outputs.
   Map the old preprocessing, collation and model construction responsibilities
   to that recipe; do not assume the old Task class has a drop-in replacement.
3. Test configuration loading, checkpoint compatibility and a small inference
   sample before training or serving. Compare outputs against the old pinned
   environment, then run the relevant evaluation.

For historical experiments, keep their matching source revision in an isolated
environment. This page preserves the old documentation URL; current implementation
instructions live in the guides above.
