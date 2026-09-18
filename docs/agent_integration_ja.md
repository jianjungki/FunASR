# FunASR Agent 連携

[English](agent_integration.md) | [中文](agent_integration_zh.md) | [한국어](agent_integration_ko.md)

用途に合ったインターフェースを選んでください。HTTP によるファイル文字起こし、
ローカル MCP ツール、デスクトップ録音、ローカル字幕生成では、利用できるモデル、
オプション、出力フィールドが異なります。プロセス内で直接推論する場合は
[Python SDK（英語）](python_api.md)を参照してください。

## HTTP サーバー

以下は、後の節で使うサンプルスクリプトも含めたソースからの準備手順です。
POSIX シェルで、新しいチェックアウトと仮想環境を使ってください。
PyPI パッケージだけをインストールしても、これらのリポジトリ内サンプルは配置されません。

```bash
git clone https://github.com/modelscope/FunASR.git FunASR-agent
cd FunASR-agent
git checkout --detach e19029adca384a06a2f60bd8c18cb98f1a0499aa
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m pip install fastapi uvicorn python-multipart
python -m pip check
```

固定されるのはソースのリビジョンであり、依存パッケージやモデルの重みのすべてではありません。
[インストールガイド（英語）](installation/installation.md)に従って CPU/GPU 環境を準備し、
実際のパッケージ・モデルのバージョンを記録して、対象モデルでリクエストを確認してください。
`pip check` だけでは CUDA、音声デコード、新規環境へのインストール成功を検証できません。

準備した環境で、次のコマンドの**どちらか一方**を実行します。
CPU の例では SenseVoice を明示的に指定しています。CUDA の例には動作する GPU 環境が必要です。
サーバーのターミナルを開いたままにし、クライアントは別の準備済みターミナルから実行してください。

```bash
funasr-server --host 127.0.0.1 --device cpu --model sensevoice --port 8000
# Alternative: stop the CPU server before using the same port.
funasr-server --host 127.0.0.1 --device cuda --model sensevoice --port 8000
```

```bash
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:8000/v1/models
```

- ファイルアップロード先は `/v1/audio/transcriptions` です。
- 稼働中のサービスのスキーマは `/openapi.json` にあります。
- Swagger UI は `/docs` です。このパスは FunASR のウェブサイトの文書ディレクトリではありません。

ヘルスチェックやモデル一覧の応答だけでは、対象モデルによる文字起こしの成功は確認できません。

パッケージ付属の `funasr-server` と[サンプル HTTP サーバー（英語）](../examples/openai_api/README.md#api-contract)では、
デフォルト、モデルの別名、応答スキーマが異なります。起動時だけでなく、リクエストにも
`model` を指定してください。`paraformer-en` はサンプルサーバーの別名であり、
パッケージ付属サーバーの組み込み別名ではありません。
カスタムモデルは適切な `--hub` と `--model-path` で指定し、リクエストには
`model="custom"` を使います。任意のモデル ID がそのまま `--model` の組み込み別名になるわけではありません。

SenseVoice の HTTP 表示テキストからはリッチタグが除去されます。
これは感情・イベントを専用フィールドで返す API ではありません。
基本の Fun-ASR-Nano は中国語・英語・日本語と中国語方言・地域アクセントの評価経路であり、
31 言語の Fun-ASR-MLT-Nano は**別の checkpoint**です。
基本 Nano の範囲から韓国語対応を推測したり、HTTP インターフェースだけを根拠に
タイムスタンプを保証したりしないでください。
[モデル選択](model_selection_ja.md)と[デプロイ方式](deployment_matrix_ja.md)で実際の経路を確認してください。

[MOSS-Transcribe-Diarize（英語）](moss_transcribe_diarize.md)は OpenMOSS が提供する第三者モデルで、
独自のデプロイ要件があります。ネイティブの話者ラベルは録音内の匿名ラベルであり、実在する人物の識別ではありません。
外部 VAD や外部話者モデルは不要なので、これらの段階を追加しないでください。
すべてのクライアントがモデル出力を余さず表示するとも限りません。

ローカルサーバーは、以下の SDK の仮の API キーを認証しません。
ネットワークに公開する前に、[セキュリティガイド（英語）](../examples/openai_api/SECURITY.md)に従い、
TLS、認証、アップロードサイズ制限、レート制限を設けてください。CORS は認証ではありません。

## SDK と curl

クライアント環境には、OpenAI HTTP クライアントを別途インストールします。

```bash
python -m pip install openai
```

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="local-development")
with open("meeting.wav", "rb") as audio:
    result = client.audio.transcriptions.create(
        model="sensevoice",
        file=audio,
        response_format="verbose_json",
    )
print(result.text)
for segment in getattr(result, "segments", []):
    print(segment)
```

```bash
curl -fsS http://localhost:8000/v1/audio/transcriptions \
  -F file=@audio.wav \
  -F model=sensevoice \
  -F response_format=verbose_json
```

`verbose_json` は応答形式を選ぶだけで、話者分離を有効にしたり、リッチタグを復元したり、
単語単位の時刻やアラインメントを保証したりするものではありません。
サンプルサーバーは既存の `sentence_info` から segments を作り、情報がなければ空リストを返します。
パッケージ付属サーバーは粗い代替区間を生成する場合があります。
両方とも segment の時刻は秒単位ですが、`duration` の意味は異なります。
時刻を利用する前に[クライアント応答の契約（英語）](../examples/openai_api/CLIENTS.md#response-formats)を確認してください。
`json` と `text` はより単純な応答形式です。
`spk=true` による話者処理はパッケージ付属 API の機能であり、サンプルサーバーのリクエストスキーマにはありません。
[話者ラベルと人物識別の違い（英語）](speaker_emotion.md)も参照してください。

### ワークフロー連携

Dify/n8n などの HTTP ノードでは、文字起こしエンドポイントに `POST` で multipart を送ります。
バイナリファイルのフィールド名は `file`、テキストフィールドは `model` と `response_format` です。
`file` に音声 URL を入れることは、音声のバイト列をアップロードすることとは異なります。
コンテナ内の `localhost` はそのコンテナ自身を指し、FunASR のホストではありません。
意図したゲートウェイを経由してアクセスできるサービスアドレスを設定してください。

- [Dify、n8n、webhook worker（英語）](../examples/openai_api/WORKFLOWS.md): リクエストの接続例。
- [JavaScript / TypeScript（英語）](../examples/openai_api/JAVASCRIPT.md): SDK と multipart クライアント。
- [Postman（英語）](../examples/openai_api/POSTMAN.md)と[スモークテスト](../examples/openai_api/smoke_test.py): デプロイ済みエンドポイントの確認。
- [Gradio（英語）](../examples/openai_api/GRADIO.md): ブラウザのアップロードとマイク入力。
- [OpenAPI（英語）](../examples/openai_api/OPENAPI.md): リポジトリ内サンプルのスキーマと稼働中のパッケージ付属サービスのスキーマの区別。

ホストフレームワークには、これらのリクエスト・応答の範囲に従って文字起こしツールを登録します。
URL worker の例は完全な安全対策を備えたダウンローダーではありません。
信頼できない URL を受け付ける前に、宛先の許可リスト、プライベートネットワークへのアクセス遮断、
リダイレクトの検証、サイズ制限、タイムアウトを追加してください。
ワークフローのフィールド表が両サーバーにそのまま当てはまるとは限らないため、上記の応答契約を使ってください。
これらの例は、すべてのフレームワークのバージョンで連携を検証した証拠でも、任意の URL の安全性を保証するものでもありません。

## MCP サーバー

準備済みのリポジトリのルートと環境から実行します。

```bash
python examples/mcp_server/funasr_mcp.py
```

文字起こしの前に、インストールガイドに従って PyTorch と互換性のある音声特徴抽出バックエンドを準備してください。
ツールキットのインストールや MCP のハンドシェイク成功だけでは、モデルの実行は検証できません。
このスクリプトに追加の MCP SDK パッケージは不要です。
MCP クライアントは HTTP ではなく stdio でスクリプトを起動します。
準備済み Python 環境とチェックアウトの絶対パスを設定してください。

```json
{
  "mcpServers": {
    "funasr": {
      "command": "/path/to/FunASR-agent/.venv/bin/python",
      "args": ["/path/to/FunASR-agent/examples/mcp_server/funasr_mcp.py"],
      "env": {
        "FUNASR_DEVICE": "cpu",
        "FUNASR_MODEL": "iic/SenseVoiceSmall"
      }
    }
  }
}
```

`transcribe_audio` はサーバーから見える既存のローカル `audio_path` を受け取ります。
コンテナに読み取り専用でマウントしたパスも使えますが、URL やライブストリームは受け取りません。
初回呼び出しでは重みのダウンロードとロードが発生する場合があります。
言語ヒントは `auto`、`zh`、`yue`、`en`、`ja`、`ko` です。
`FUNASR_MODEL` を変更してもツールのスキーマは変わらず、別のモデルとその VAD 経路の互換性も保証されません。

結果は MCP の `content` 内の `type=text` として整形され、必要に応じて区間情報を含みます。
HTTP の応答オブジェクトではありません。トップレベルの転写テキストからはリッチタグを除去しますが、
任意の区間テキストはモデル出力からコピーされます。
`FUNASR_DEVICE` のデフォルトは `cpu`、`FUNASR_MODEL` は `iic/SenseVoiceSmall` です。
[MCP のソースとコンテナ設定](../examples/mcp_server/README.md)でクライアント設定とマウント方法を確認してください。
アシスタントとサーバーがアクセスできるファイルを制限してください。ローカルツール自体はファイルシステムの権限境界ではありません。

## デスクトップ音声入力

HTTP サーバーを起動したまま、準備済みチェックアウトで別のターミナルを開きます。

```bash
python -m pip install sounddevice numpy pyperclip openai pynput
python examples/voice_input/funasr_input.py --server http://localhost:8000/v1 --model sensevoice
```

スクリプトは録音を開始・停止し、WAV を HTTP サービスにアップロードして、転写テキストをコピーします。
マイクの権限と音声デバイスの対応が必要です。macOS ではアクセシビリティ権限が必要な場合もあり、
Linux の自動貼り付けには `xdotool` を使います。クリップボードや貼り付けの挙動はデスクトップ環境に依存します。
現在の `--lang` は解析されますが文字起こしリクエストには渡されないため、この経路では有効な言語指定ではありません。

リモートの `--server` を指定すると、録音がそのエンドポイントに送信されます。
常に完全オフラインである、音声が端末外に出ない、一定の遅延を達成する、といった保証はありません。
デプロイ前に[設定項目](../examples/voice_input/README.md#配置选项)と
[実装](../examples/voice_input/funasr_input.py)を確認してください。

## 字幕生成

これはローカルの `AutoModel` パイプラインであり、HTTP や MCP のクライアントではありません。
準備済みチェックアウトで、ローカルの入力ファイルと適切な推論環境を使います。

```bash
python examples/subtitle/generate_subtitle.py video.mp4
python examples/subtitle/generate_subtitle.py meeting.wav --spk
python examples/subtitle/generate_subtitle.py podcast.mp3 --format vtt
python examples/subtitle/generate_subtitle.py audio.wav --device cpu
```

デフォルトのデバイスは CUDA です。最後のコマンドは CPU を明示的に選びます。
デフォルトのモデルは SenseVoiceSmall で、VAD と句読点モデルを併用します。
この固定パイプラインは任意のモデルに適用できる汎用手順ではありません。
`--spk` は CAM++ による匿名話者ラベルを追加しますが、人物の身元は検証しません。
`--format` は SRT/VTT を選択し、`--output` は出力先を指定します。
**既存の出力ファイルは上書きされます**。以前の字幕を残す場合は別のパスを指定してください。
`--lang` は `auto` 以外の言語ヒントを推論に渡します。
`--max-single-segment-time` の単位はミリ秒で、現在のデフォルトは `60000` です。

`--segment-mode readable` は認識テキストや句読点を書き換えず、表示用の字幕をまとめます。
`sentence` はモデルの元の文単位の区切りを保ちます。どちらも句読点の誤りを修正せず、音素の境界も保証しません。
実際のタイムスタンプの有無を確認し、元の音声と再生を照合してください。
時間情報が欠けると、長さがゼロの `(0, 0)` 区間にフォールバックする場合があります。
これは妥当性が確認された字幕ではありません。入力デコード、モデル・依存パッケージのロード、
GPU 容量は環境ごとに検証が必要です。
出力の解釈には[字幕オプション（英語）](../examples/subtitle/README.md#options)と
[話者ガイド（英語）](speaker_emotion.md)を参照してください。
