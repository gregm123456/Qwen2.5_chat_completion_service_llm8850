# Qwen2.5 (LLM-8850) Chat Completion Service — Implementation Plan

Purpose
- Create a production-friendly chat-completion service that exposes an **OpenAI-compatible API** (POST /v1/chat/completions) backed by the Qwen2.5-1.5B model running on the LLM-8850 NPU accelerator card.
- The service **mimics Ollama and OpenAI chat completion endpoints** so existing chatbot applications can call it as a drop-in replacement without code changes.
- It must accept **standard chat transcripts** with system messages, user messages, and assistant messages (OpenAI message format), apply the Qwen2.5 chat template, and return assistant completions.
- The service must keep the model loaded on the LLM-8850 (do not reload per request), be resilient and startable as a system service, and integrate the existing tokenizer server and model binaries from `Qwen2.5-1.5B-Instruct-GPTQ-Int4`.

Project structure and repo integration
- The new project (`Qwen2.5_chat_completion_service`) will **incorporate the `Qwen2.5-1.5B-Instruct-GPTQ-Int4` repository** by providing download instructions for users to clone it separately (not as a git submodule, to avoid the 1.5GB model files slowing down the main project clone).
- **Recommended approach**: The service repo does NOT include the model repo as a submodule. Instead, `scripts/download_models.sh` clones the model repo to `models/Qwen2.5-1.5B-Instruct-GPTQ-Int4/` and checks out a **pinned commit** for reproducibility.
- **Pinned model repo version**:
  - Repo: `https://huggingface.co/AXERA-TECH/Qwen2.5-1.5B-Instruct-GPTQ-Int4`
  - Commit: `01d5a6eb90d9be5dd3de32518ec99c04d9ae5da5`
  - Date: 2025-04-01
  - Message: "Update README.md"
  - **Why pinned**: Prevents breaking changes from upstream updates; ensures reproducible builds and deployments.
- If modifications to the model repo are needed (e.g., adding an RPC adapter), fork the repo or maintain patches in a `patches/` directory and document how to apply them.

Licensing and compatibility
- The service intentionally does NOT vendor the upstream model repository and instead references a pinned upstream commit (see `scripts/download_models.sh`). This avoids redistributing large model binaries in this repo while keeping reproducible builds.
- The upstream model repo is expected to use a permissive license (for example, BSD-3-Clause). BSD-3-Clause is compatible with the MIT license, so licensing this service under MIT is acceptable.
- Important rules when working with upstream files:
  - If you do NOT copy or vendor upstream files into this repo (we only instruct users to download the model separately), you may license this repository under MIT without conflicting with the upstream license.
  - If you DO copy or vendor files from the upstream model repo into this repository, you MUST preserve the upstream LICENSE file and copyright notices, and include a clear attribution in `README.md` describing the upstream source and its license.
  - Do not remove or attempt to relicense upstream files; the original upstream license must remain visible and accompany any redistributed files.
- Recommendation: add an `LICENSE` (MIT) to this repo for your service code, and add a "Third-party software" section to `README.md` that documents the pinned upstream model repo URL, the pinned commit hash, and the upstream license to make obligations clear to downstream users.

High-level contract (service expectations)
- **Primary API**: POST /v1/chat/completions (OpenAI-compatible)
  - Input: 
    - `model`: "qwen2.5" (or model identifier)
    - `messages`: array of `{role: "system"|"user"|"assistant", content: "..."}` — standard chat transcript format
    - `temperature`, `top_k`, `top_p`, `max_tokens`, `stop` (optional generation parameters)
    - `stream`: boolean (optional) — if true, return SSE stream of token chunks
  - Output: OpenAI-compatible JSON response with `choices[0].message.content` (assistant reply) and `usage` metadata
  - Error modes: 400 for invalid requests, 503 if tokenizer/model unavailable, 500 for unexpected failures
- **Health**: GET /health -> JSON `{status: "ok"|"degraded"|"down", details: {...}}`
  - Include tokenizer and model process health, NPU status, uptime
- **Admin endpoints** (optional, for ops):
  - POST /admin/reload — reload config or restart model process
  - POST /admin/shutdown — graceful shutdown

Chat completion flow (key requirement)
1. Client sends POST /v1/chat/completions with a **chat transcript** (e.g., `[{role:"system", content:"You are a helpful assistant"}, {role:"user", content:"Hello!"}]`).
2. Service applies the **Qwen2.5 chat template** (see `qwen2.5_tokenizer.py` for the prompt format: `<|im_start|>system\n...<|im_end|>\n<|im_start|>user\n...<|im_end|>\n<|im_start|>assistant\n`) to convert the message array into a single prompt string.
3. Service sends the prompt to the **model manager** which forwards it to the running model process (kept loaded on the LLM-8850).
4. Model returns the assistant's reply; service wraps it in OpenAI-compatible JSON and returns to client.
5. Existing chatbot apps that call OpenAI or Ollama can point to this service's endpoint and use it without changes (same request/response schema).

Assumptions (state these explicitly)
- The `Qwen2.5-1.5B-Instruct-GPTQ-Int4` folder (downloaded to `models/`) contains a tokenizer server script (`qwen2.5_tokenizer.py`) and model run script(s) (`run_qwen2.5_1.5b_gptq_int4_axcl_aarch64.sh`) that load the model into the LLM-8850 card.
- The model binaries/driver (AXCL / `main_axcl_aarch64`) are already installed on the host system and accessible (LLM-8850 driver is present and its environment is set by `/etc/profile`).
- The model process is long-lived and exposes a **listener socket** for prompt requests (preferred) rather than an interactive stdin/stdout REPL. The plan assumes the model process listens on either a Unix domain socket (preferred, default `/run/qwen/model.sock`) or a loopback TCP port (configurable, default `localhost:11411`). `model_manager` will connect to that socket for each request.
- If the model binary does not natively expose an RPC listener, the plan's fallback remains: wrap/modify the runner to add a small RPC adapter that binds a local Unix domain socket and forwards framed requests to the model. We will avoid pty-based interaction where possible since a socket is more robust and suitable for production.
- **This project is responsible for deploying and managing both the tokenizer server and the model process**. The tokenizer server (either the upstream `qwen2.5_tokenizer.py` or an equivalent in-process server) must be started by this service and kept running at `localhost:12345` for encode/decode/chat_template operations. The service will manage the tokenizer lifecycle (start/stop/restart/health-check) alongside the model process.

Defaults for Raspberry Pi 5 (Bookworm)
- Project install root (recommended, configurable): `/opt/qwen` (service files, venv, logs). For development the repo path `/home/robot/llm8850` may be used.
- Virtualenv (default): `/opt/qwen/venv` (or `/opt/qwen/qwen_venv`).
- Service user: `qwen` (system user, home `/var/lib/qwen`, logs under `/var/log/qwen`). Systemd unit will run as this user.
- Tokenizer HTTP port (default): `127.0.0.1:12345`.
- API HTTP port (default): `127.0.0.1:8080` (bind to loopback only by default).
- Model listener (default): Unix domain socket `/run/qwen/model.sock`. Fallback TCP: `127.0.0.1:11411`.
- Log locations (defaults): `/var/log/qwen/model.log`, `/var/log/qwen/tokenizer.log`, `/var/log/qwen/service.log`.
- PID files (defaults): `/run/qwen/tokenizer.pid`, `/run/qwen/model.pid`.

These defaults are configurable in `config.yaml` but provide sane Raspberry Pi choices for Bookworm.

Architecture overview (components)
- **Project root**: `Qwen2.5_chat_completion_service/`
  - `models/Qwen2.5-1.5B-Instruct-GPTQ-Int4/` — **NOT a git submodule**; users download separately via `scripts/download_models.sh` (clones the repo and checks out the pinned commit `01d5a6eb90d9be5dd3de32518ec99c04d9ae5da5`)
  - `qwen_service/` — new Python service package
    - `app.py` (FastAPI) — HTTP API that implements OpenAI-compatible `/v1/chat/completions`, `/health`, and admin endpoints
    - `chat_completion.py` — handles chat message formatting, applies Qwen2.5 chat template (`<|im_start|>...<|im_end|>`), calls model_manager and tokenizer_client
    - `model_manager.py` — starts/monitors the model process (run script), exposes an in-process API to send prompts and receive responses; keeps model loaded on the LLM-8850 and manages kv cache
    - `tokenizer_manager.py` — **starts/monitors the tokenizer server process** (`qwen2.5_tokenizer.py --port 12345`), health-checks it, restarts on failure; ensures tokenizer is available before accepting API requests
    - `tokenizer_client.py` — HTTP client wrapper for the tokenizer service at localhost:12345 (encode/decode/apply_chat_template); called by `chat_completion.py` and `app.py`
    - `session_manager.py` — (optional) tracks conversation state, rolling context window, session tokens, and per-session caches if needed
    - `config.py` / `config.yaml` — runtime configuration: ports, limits, model paths, service user, logging, chat template
    - `logging.conf` — log configuration
  - `systemd/` — service unit files
    - `qwen-chat.service` — a systemd service to run `qwen_service.app:main` under a dedicated user, restart on crash, set environment (e.g., source /etc/profile); **this service manages both the tokenizer and model processes internally** via `tokenizer_manager` and `model_manager`
  - `scripts/` — helper scripts
    - `download_models.sh` — **clones the model repo to `models/Qwen2.5-1.5B-Instruct-GPTQ-Int4/` and checks out pinned commit `01d5a6eb90d9be5dd3de32518ec99c04d9ae5da5`**; sets executable permissions on binaries/scripts
    - `start_qwen.sh` / `stop_qwen.sh` — convenience wrappers for manual start/stop (start tokenizer, start model, start API server)
    - `setup.sh` — creates venv, installs deps, calls `download_models.sh`
  - `requirements.txt` — Python dependencies (fastapi, uvicorn, httpx, pydantic, pexpect if needed, pytest)
  - `README.md` — project documentation, quick start guide, API examples

Interaction flow (request -> response)
1. Client POST /v1/chat/completions with a **standard chat transcript** (array of messages: `[{role:"system", content:"..."}, {role:"user", content:"..."}, ...]`) -> `app.py`
2. `app` validates the request (check `messages` format, `model` identifier, generation params)
3. `app` calls `chat_completion.apply_chat_template(messages)` to convert the message array into a Qwen2.5-formatted prompt string using the `<|im_start|>...<|im_end|>` template (this may delegate to `tokenizer_client` if the tokenizer provides a chat template API, or apply the template locally)
4. `app` calls `model_manager.generate(prompt, options)` with the formatted prompt and generation options (temperature, top_k, max_tokens, etc.)
   - `model_manager` maintains a single long-lived model process (or a small pool) and sends the prompt to it, then waits for the response
   - If the model is interactive via stdin/stdout, `model_manager` communicates over an allocated pty using a robust protocol (e.g., length-prefixed JSON or line-delimited markers with unique request IDs)
   - If the model can be instrumented to expose a TCP/Unix domain socket endpoint, prefer that and call directly
5. When the model returns the assistant's reply text (or token ids), `app` decodes via `tokenizer_client.decode()` if necessary, constructs an OpenAI-compatible response JSON structure (`{choices: [{message: {role:"assistant", content:"..."}}], usage: {...}}`) and returns it to the caller
6. Existing chatbot apps that call OpenAI or Ollama can point to `http://localhost:8080/v1/chat/completions` and use this service as a drop-in replacement (same request/response schema)
Key implementation details and choices
- **Persistent model in NPU**: model process must be started once at boot (systemd) and must not unload model weights between requests. We will rely on the run script/binary to perform the loading step on startup. `model_manager` must detect whether the model is ready (monitor model log for success line such as "LLM init ok") before accepting requests.
- **Tokenizer server lifecycle**: `tokenizer_manager` starts the tokenizer server (`python qwen2.5_tokenizer.py --port 12345`) as a subprocess at service startup, monitors its health (ping `http://localhost:12345` or check process PID), and restarts it on failure. The main service will not accept requests until both the tokenizer and model are healthy.
- **Service startup order**: 
  1. `tokenizer_manager` starts tokenizer subprocess and waits for it to be ready (HTTP health check or log parsing)
  2. `model_manager` starts model subprocess (run script) and waits for "LLM init ok" in logs
  3. `app.py` begins accepting API requests on `/v1/chat/completions`
- **IPC between API and model**:
  - Preferred: modify or wrap the model runner so it exposes an RPC interface (Unix domain socket or HTTP) for prompt requests. This is the cleanest and most robust approach for production.
  - Fallback: spawn the run script from `model_manager` and attach to a pty to send/receive prompts. Use `pexpect` or `ptyprocess` and implement a robust request/response framing (e.g., prefix with JSON with a request id and delimit responses with a unique delim). Implement timeouts and watchdogs.
- **Tokenizer client**: `tokenizer_client.py` calls `http://localhost:12345` for encode/decode and chat template application. Implement retries and timeouts. If the tokenizer is down, requests fail fast with 503 and the `/health` endpoint reports degraded status.
- **Concurrency**: the LLM-8850 is a hardware accelerator — it likely supports only a limited level of concurrency. Implementation plan: single model process (single model instance) with a request queue and concurrency=1 by default. Support queuing with configurable max concurrency and request timeouts. If you have multiple accelerator cards or the binary supports multiple contexts, we can expand to a worker pool.
- **Session & KV cache**: preserve kv cache between turns for responsiveness. `session_manager` will map session ids to conversation state; the `generate` call must include session-specific context tokens; implement max_context_tokens and LRU eviction.
- **Streaming**: implement optional streaming (SSE or chunked transfer). Internally the model may stream tokens; `model_manager` should forward them to the HTTP client.

Files to add (suggested)
- **Project root**: `Qwen2.5_chat_completion_service/`
  - `models/Qwen2.5-1.5B-Instruct-GPTQ-Int4/` — **not in git**; downloaded separately by `scripts/download_models.sh` (add `models/` to `.gitignore`)
  - `qwen_service/`
    - `__init__.py`
    - `app.py` — FastAPI + OpenAPI; implements `/v1/chat/completions` (OpenAI-compatible), `/health`, `/admin/*`
    - `chat_completion.py` — chat message formatting, applies Qwen2.5 chat template, orchestrates tokenizer_client + model_manager
    - `model_manager.py` — ModelProcess class: start/stop/monitor model subprocess, send_prompt(), stream_prompt()
    - `tokenizer_manager.py` — **TokenizerProcess class: start/stop/monitor tokenizer subprocess (`qwen2.5_tokenizer.py`), health-check, auto-restart on failure**
    - `tokenizer_client.py` — HTTP client wrapper for encode/decode/chat_template endpoints (calls `localhost:12345`)
    - `session_manager.py` — session lifecycle, context windowing (optional, for stateful sessions)
    - `config.py` / `config.yaml` — config loader (ports, model paths, limits, chat template)
  - `systemd/qwen-chat.service` — example systemd unit file (manages tokenizer + model + API server as a single service)
  - `scripts/`
    - `download_models.sh` — **clones `https://huggingface.co/AXERA-TECH/Qwen2.5-1.5B-Instruct-GPTQ-Int4` to `models/Qwen2.5-1.5B-Instruct-GPTQ-Int4/`, checks out commit `01d5a6eb90d9be5dd3de32518ec99c04d9ae5da5`, and sets executable permissions**
    - `start_qwen.sh` / `stop_qwen.sh` — convenience wrappers (start tokenizer, start model, start API)
    - `setup.sh` — create venv, install deps, call `download_models.sh`
  - `requirements.txt` — FastAPI, uvicorn, httpx, pydantic, pexpect (if used), pytest
  - `README.md` — project docs, quick start, API examples
  - `.gitignore` — include `models/` to exclude the downloaded model repo from git

Minimal API design (OpenAI-compatible)
- POST /v1/chat/completions
  - Request body (JSON):
    ```json
    {
      "model": "qwen2.5",
      "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
      ],
      "temperature": 0.9,
      "top_k": 10,
      "top_p": 0.95,
      "max_tokens": 256,
      "stop": ["#"],
      "stream": false
    }
    ```
  - Response (JSON, OpenAI-compatible):
    ```json
    {
      "id": "chatcmpl-abc123",
      "object": "chat.completion",
      "created": 1234567890,
      "model": "qwen2.5",
      "choices": [
        {
          "index": 0,
          "message": {
            "role": "assistant",
            "content": "Hello! How can I assist you today?"
          },
          "finish_reason": "stop"
        }
      ],
      "usage": {
        "prompt_tokens": 20,
        "completion_tokens": 10,
        "total_tokens": 30
      }
    }
    ```
  - Supports standard OpenAI parameters and returns OpenAI-compatible responses so existing chatbot apps can call this endpoint without code changes.
Systemd unit example (concept)
-----
[Unit]
Description=Qwen2.5 Chat Completion Service (LLM-8850)
After=network.target

[Service]
Type=simple
User=qwen
Group=qwen
Environment=PYTHONUNBUFFERED=1
# WorkingDirectory should point to the service install root (default `/opt/qwen`), or the repo path for dev
WorkingDirectory=/opt/qwen
# ExecStart points to a small wrapper script that sources /etc/profile and activates the venv
ExecStart=/home/robot/llm8850/scripts/start_service.sh
Restart=on-failure
RestartSec=5
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
-----

- Operational notes
- Ensure `/etc/profile` is sourced prior to starting the service if drivers or environment variables are injected there. For systemd we strongly recommend using a small wrapper script (example below) that:
  1. sources `/etc/profile` (so the llm8850 driver environment is available),
  2. activates the service virtualenv (e.g. `source /home/robot/llm8850/qwen/bin/activate`), and
  3. execs the Python service (so systemd receives the real python PID).
  
  Example wrapper `scripts/start_service.sh` (make executable):
  ```bash
  #!/usr/bin/env bash
  set -euo pipefail
  # source system profile for driver env vars
  if [ -f /etc/profile ]; then
    # shellcheck disable=SC1090
    source /etc/profile
  fi

  # activate venv
  VENV_DIR="/opt/qwen/venv"
  if [ -f "$VENV_DIR/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
  fi

  # optional: export additional env vars
  export PYTHONUNBUFFERED=1

  # exec the Python service (replace with uvicorn invocation if preferred)
  exec "$VENV_DIR/bin/python" -m qwen_service.app
  ```

- Logs: write model logs to `model.log` (already created by the run script) and service logs via systemd/journal. Provide `--log-file` options in `app.py` for local file logging.
- Security: bind to loopback by default and place a reverse proxy (nginx) or API gateway in front for authentication and rate-limiting. Consider TLS and API keys.
  
  Notes:
  - Using a wrapper script ensures `/etc/profile` is applied and the venv is activated in the same process tree as the exec'd Python process, which avoids subtle environment differences when systemd starts the service.
  - Alternatively, you can provide an `EnvironmentFile=/etc/default/qwen-chat` in the unit and drop environment variables there, but driver-specific initialization is often best handled by sourcing `/etc/profile` in a wrapper.

 - Run Python inside the dedicated venv (create `qwen_venv` or reuse the `qwen` venv). Install `fastapi`, `uvicorn`, `httpx`, `pexpect` (if used) and other deps.
- Logs: write model logs to `model.log` (already created by the run script) and service logs via systemd/journal. Provide `--log-file` options in `app.py` for local file logging.
- Security: bind to loopback by default and place a reverse proxy (nginx) or API gateway in front for authentication and rate-limiting. Consider TLS and API keys.

Tokenizer HTTP API (contract)

If the upstream `qwen2.5_tokenizer.py` is used, it already provides a simple HTTP listener. The service will rely on a small, stable API to interact with tokenization. If the upstream listener differs, we will provide a minimal shim exposing the same contract below.

Endpoints (all on `127.0.0.1:12345` by default)
- POST /encode
  - Request: { "text": "string" }
  - Response: { "tokens": [int], "length": int }
- POST /decode
  - Request: { "tokens": [int] }
  - Response: { "text": "string" }
- POST /chat_template
  - Request: { "messages": [{"role":"user|assistant|system","content":"..."}, ...], "template": "instruction" }
  - Response: { "prompt": "string" }

Usage notes
- The `model_manager` will call `/chat_template` to produce the final prompt to send to the model, then call `/encode` when it needs the tokenized representation (if the model runner requires token ids rather than raw text). After the model produces token-ids, `/decode` will be used for final text output when needed.
- All tokenizer calls are loopback-only; the API will not expose the tokenizer port externally.

Edge cases and failure modes
- **Tokenizer unavailable**: return 503 and health degraded; `tokenizer_manager` attempts automatic restart with backoff. If tokenizer fails repeatedly, service stays up but rejects requests until tokenizer recovers.
- **Model crash on prompt**: `model_manager` must restart process automatically (with backoff) and fail pending requests with 502.
- **Long-running requests**: enforce per-request timeout and a queue size limit to prevent memory exhaustion.
- **Disk/permissions**: model files are large; ensure the service user has read access to `Qwen2.5-1.5B-Instruct-GPTQ-Int4` and the AXCL driver resources.
- **Tokenizer startup race**: API server must not accept requests until `tokenizer_manager` confirms the tokenizer is healthy (HTTP ping succeeds or log parsing confirms "http://localhost:12345" is listening).

Testing and validation
- Unit tests for `tokenizer_client` (mock the HTTP tokenizer), `session_manager` context trimming.
- Integration test: start tokenizer, start model (in a test mode or with a small prefill), run `curl` against `/v1/chat/completions` and assert a valid response.
- Performance test: measure latency for warm prompt vs cold (loading already done), measure token/s throughput.

Minimal validation commands (developer)
- **Download model repo** (run once, or via `./scripts/setup.sh`):
  ```bash
  cd /path/to/Qwen2.5_chat_completion_service
  mkdir -p models
  git clone https://huggingface.co/AXERA-TECH/Qwen2.5-1.5B-Instruct-GPTQ-Int4 models/Qwen2.5-1.5B-Instruct-GPTQ-Int4
  cd models/Qwen2.5-1.5B-Instruct-GPTQ-Int4
  git checkout 01d5a6eb90d9be5dd3de32518ec99c04d9ae5da5
  chmod +x main_axcl_aarch64 run_qwen2.5_1.5b_gptq_int4_axcl_aarch64.sh run_qwen2.5_1.5b_gptq_int4_axcl_x86.sh
  cd ../..
  ```
- **Manual startup (for testing components individually)**:
  - Start tokenizer (managed by `tokenizer_manager` in production, but can be run manually for dev):
    ```bash
    source /etc/profile
    source qwen/bin/activate
    cd models/Qwen2.5-1.5B-Instruct-GPTQ-Int4
    python qwen2.5_tokenizer.py --port 12345
    # (or in background: nohup python qwen2.5_tokenizer.py --port 12345 > tokenizer.log 2>&1 & echo $! > ../../tokenizer.pid)
    ```
  - Start model (managed by `model_manager` in production):
    ```bash
    cd models/Qwen2.5-1.5B-Instruct-GPTQ-Int4
    ./run_qwen2.5_1.5b_gptq_int4_axcl_aarch64.sh
    # (or in background: nohup ./run_qwen2.5_1.5b_gptq_int4_axcl_aarch64.sh > model.log 2>&1 & echo $! > ../../model.pid)
    ```
- **Start service (dev mode — tokenizer_manager and model_manager start subprocesses automatically)**:
  ```bash
  source qwen/bin/activate
  uvicorn qwen_service.app:app --host 127.0.0.1 --port 8080 --log-level info
  # On startup, app.py will call tokenizer_manager.start() and model_manager.start() and wait for both to be ready
  ```
- Test API (standard chat completion):
  ```bash
  curl -X POST "http://127.0.0.1:8080/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d '{
      "model": "qwen2.5",
      "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
      ],
      "max_tokens": 64
    }'
  ```
Roadblocks / open questions (need confirmation)
1. Protocol for interacting programmatically with the model binary: does `run_qwen...` expose a socket or only an interactive terminal? If only interactive, confirm whether it's safe/reliable to attach a pty, or whether we should modify the run scripts to enable a simple RPC (preferred).
2. Expected concurrency supported by the accelerator — how many simultaneous inferences should we permit? Default single-worker queue is safest.
3. Service user and filesystem permissions: which Linux user should own the service and have access to the hardware device files?
4. If streaming token-level responses are required by clients, confirm that the model binary can stream tokens or provide hooks to read partial outputs.

Next steps (concrete implementation tasks)
1. **Download and pin the Qwen2.5-1.5B-Instruct-GPTQ-Int4 model repo**: 
   - Create `scripts/download_models.sh` that clones `https://huggingface.co/AXERA-TECH/Qwen2.5-1.5B-Instruct-GPTQ-Int4` to `models/Qwen2.5-1.5B-Instruct-GPTQ-Int4/` and checks out commit `01d5a6eb90d9be5dd3de32518ec99c04d9ae5da5` (pinned for reproducibility).
   - **Note**: The upstream repo does not have executable permissions set on `main_axcl_aarch64`, `run_qwen2.5_1.5b_gptq_int4_axcl_aarch64.sh`, and `run_qwen2.5_1.5b_gptq_int4_axcl_x86.sh`. The `download_models.sh` script must explicitly `chmod +x` these files after cloning.
   - Add `models/` to `.gitignore` to prevent the 1.5GB model repo from being committed to the service repo.
2. **Confirm the interaction protocol with the model binary** (answer open question #1). Test whether `run_qwen...` exposes a socket or only an interactive terminal. If the run script already exposes RPC, implement `model_manager` to call it directly; otherwise create a small adapter around the model binary to accept prompt requests over a Unix domain socket or via a pty/pexpect wrapper.
3. **Scaffold `qwen_service/`** with `__init__.py`, `app.py`, `chat_completion.py`, `model_manager.py`, `tokenizer_manager.py`, `tokenizer_client.py`, and required config files (`config.py` or `config.yaml`).
4. **Implement `tokenizer_manager.py`**: 
   - Start tokenizer subprocess (`python qwen2.5_tokenizer.py --port 12345`)
   - Monitor process health (HTTP ping to `http://localhost:12345` or PID check)
   - Restart on failure with exponential backoff
   - Provide `is_ready()` method for service startup coordination
5. **Implement `chat_completion.apply_chat_template(messages)`** to convert an array of `{role, content}` messages into the Qwen2.5 prompt format (`<|im_start|>system\n...<|im_end|>\n<|im_start|>user\n...<|im_end|>\n<|im_start|>assistant\n`). This can delegate to the tokenizer if it provides a chat template API, or apply the template locally.
6. **Implement `model_manager`** with start/stop/health-check and a queue for incoming requests. Add simple request timeout and error handling. Ensure the model process stays loaded on the LLM-8850 across requests. Provide `is_ready()` method.
   - **Before starting the model subprocess**, ensure executable permissions: `chmod +x models/Qwen2.5-1.5B-Instruct-GPTQ-Int4/main_axcl_aarch64` and `chmod +x models/Qwen2.5-1.5B-Instruct-GPTQ-Int4/run_qwen2.5_1.5b_gptq_int4_axcl_aarch64.sh`
7. **Implement `app.py` startup sequence**: 
   - On startup, call `tokenizer_manager.start()` and wait for `is_ready()`
   - Then call `model_manager.start()` and wait for `is_ready()`
   - Only then begin accepting requests on `/v1/chat/completions`
   - Implement `/health` to report status of both tokenizer and model
8. **Implement `app.py` endpoints** (`/v1/chat/completions`, `/health`, admin endpoints) and wire them to `chat_completion`, `model_manager`, and `tokenizer_client`. Return OpenAI-compatible JSON responses.
9. **Create `systemd` unit & `start_qwen.sh` wrapper** that sources `/etc/profile` and activates the venv prior to starting the service. Add `setup.sh` to initialize submodules and install dependencies.
   - **`setup.sh` must include**: `chmod +x models/Qwen2.5-1.5B-Instruct-GPTQ-Int4/main_axcl_aarch64 models/Qwen2.5-1.5B-Instruct-GPTQ-Int4/run_qwen2.5_1.5b_gptq_int4_axcl_aarch64.sh models/Qwen2.5-1.5B-Instruct-GPTQ-Int4/run_qwen2.5_1.5b_gptq_int4_axcl_x86.sh`
10. **Add tests** and CI jobs to validate basic behavior (tokenizer encode/decode, chat template application, single chat completion end-to-end with a standard chat transcript, tokenizer/model restart on failure).
11. **Document the API** in `README.md` with examples showing how to use the service as a drop-in replacement for OpenAI or Ollama chat completion endpoints.

Acceptance criteria
- POST /v1/chat/completions accepts a **standard chat transcript** (array of messages with system/user/assistant roles) and returns a valid assistant reply in OpenAI-compatible JSON format.
- The service correctly applies the Qwen2.5 chat template (`<|im_start|>...<|im_end|>`) to convert messages into a prompt.
- The model remains loaded in the LLM-8850 across multiple requests (no reload per request). Confirm with logs or by measuring response time (subsequent requests should be fast).
- **The tokenizer server is started and managed by the service** (via `tokenizer_manager`); it restarts automatically on failure and the service does not accept requests until the tokenizer is healthy.
- The service restarts automatically on failures and exposes a working /health endpoint that reports the status of both the tokenizer and model processes.
- **Existing chatbot apps can use this service as a drop-in replacement for OpenAI or Ollama** by pointing to `http://localhost:8080/v1/chat/completions` without code changes.

If anything above is unclear, tell me which of the open questions you want me to test/implement first and I will proceed with the next implementation step.

## Recommended next step(s)

- Validate the model runner IPC (confirm UDS/TCP vs interactive REPL). This determines whether `model_manager` can connect directly or needs a small RPC adapter.
- Implement `tokenizer_manager.py` and `tokenizer_client.py` so the service can start, health-check, and call `/encode`/`/decode`/`/chat_template` on the tokenizer.
- Scaffold `qwen_service.app` (FastAPI) and wire startup to wait for tokenizer and model readiness. This enables quick dev iteration and API tests.

These three steps provide the fastest path to a working end-to-end prototype. Once done, add the `download_models.sh`/`setup.sh` scripts and `systemd` wrapper for production deployment.

