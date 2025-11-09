# REPL Response Investigation

This document captures the investigation into spurious / duplicate prompt-response cycles observed when driving the Qwen2.5 Axera NPU model binary in persistent REPL mode. It explains the root cause, evidence collected, short-term mitigations, and recommended next steps for a robust fix.

Date: 2025-11-09

Authors: Project agent (logs + edits), operator

## Summary

When issuing a single chat request (for example "What is 2+2?"), the model process frequently printed multiple discrete responses (greetings, canned lines, previous completions) in addition to the expected numeric answer. Our wrapper (a persistent stdin/stdout REPL manager) collected those lines and returned ambiguous results. This made single-request → single-response semantics unreliable.

Root cause: The supplied model runner/binary runs in an interactive/continuous mode (flags such as `--continue` and `--live_print` in the shipped run script). It prints greetings, progress lines, and previous/extra completions asynchronously. The ModelManager assumes a simple one-prompt → one-response mapping and therefore cannot reliably distinguish which printed lines correspond to the prompt just sent.

## Evidence (what we inspected)

- `src/model_manager.py` (persistent process using stdin/stdout):
  - Starts the runner once and keeps it open.
  - Drains the stdout queue then writes the prompt to stdin and collects subsequent stdout lines until it sees a prompt marker `>>`.
  - Prior to recent edits it used simple filtering; heuristics were added during debugging to reduce noise but proved brittle.

- `models/Qwen2.5-1.5B-Instruct-GPTQ-Int4/run_qwen2.5_1.5b_gptq_int4_axcl_aarch64.sh`:
  - Calls `main_axcl_aarch64` with `--live_print 1` and `--continue 1` and `--prompt "$1"` which indicates an interactive/continuous mode.

- `models/.../README.md`: The upstream demo is intentionally interactive: examples show the binary printing `Type "q" to exit, Ctrl+c to stop current running` and printing multiple lines during usage.

- `logs/model.log` (captured during tests): multiple candidate outputs for one curl request, including English and Chinese greetings and multiple answer lines.

## Reproduction steps (how we tested)

1. Started tokenizer server (local HTTP service shipped in `models/qwen2.5_tokenizer.py`).
2. Launched the service (FastAPI app) which starts:
   - `TokenizerManager` (spawns tokenizer script)
   - `ModelManager` (spawns run script once and keeps it running)
3. Sent a single POST to `/v1/chat/completions` with the message `What is 2+2?`.
4. Observed `logs/model.log` containing several printed responses around the same time.

Sample model.stdout excerpt (simplified):

```
>> I'm Qwen.

>> The answer to 2+2 is 4.

>> 你好！请告诉我您需要帮助......
```

Our wrapper returned the first seen line or attempted to apply heuristics, which is not robust.

## Why string heuristics are brittle

- Greetings and canned messages vary by language and phrasing; they are not enumerable.
- The binary prints content asynchronously (progress bars, previous completions) so temporal heuristics (first seen / last seen) are race-prone.
- The wrapper cannot atomically correlate the time a prompt is written to the exact produced output lines; there is no explicit request/response boundary token printed by the binary.

## Options considered (tradeoffs)

1. Per-request process invocation (spawn-per-request)
   - How: invoke `run_qwen2.5_...sh "$PROMPT"` for each incoming request and capture stdout.
   - Pros: clean, deterministic — one-run → one-output mapping.
   - Cons: heavy startup cost; reinitializes model/NPU each call; may stress NPU driver and increase latency.

2. Change runner flags to disable interactive/verbose behavior
   - How: edit run script to set `--continue 0 --live_print 0` (or relevant flags for the binary) and keep persistent REPL.
   - Pros: cheap to try; keeps low-latency persistent model.
   - Cons: I don't have authoritative flag docs for the binary; flags may be named differently or have side effects. It may reduce helpful logging or change generation behavior. It may not eliminate all extra lines (the binary could still print prefill/greeting once on some events).

3. Marker/sentinel protocol in prompt
   - How: wrap the prompt so that the model is instructed to include a unique sentinel token at the end of its reply (e.g., "Please end with <|END-UUID|>"). Then read stdout until that marker appears and only return the content before the marker.
   - Pros: robust parsing if the model reliably echoes the marker.
   - Cons: requires the model to actually output the marker reliably (models sometimes strip or misplace markers), and it alters prompts / could influence generation.

4. Use an upstream change in the binary/runtime (preferred long-term)
   - How: change the upstream runtime to offer a request/response mode (HTTP/CLI IPC) or a flag that switches to synchronous single-request behavior.
   - Pros: correct at source; enables proper production-grade operation.
   - Cons: requires editing/needing upstream toolchain or vendor cooperation; may be non-trivial.

5. Instrumentation and diagnostics
   - How: temporarily log raw model stdout lines with precise timestamps before any filtering so we can determine ordering and origin of lines.
   - Pros: reveals exact behaviour without changing runtime semantics; low risk.
   - Cons: only diagnostic, not a long-term fix.

## Recommendation

1. Do the low-risk diagnostic first (instrument raw stdout timestamps): confirm whether the extra lines are emitted before we write a prompt (i.e., stale/queued), or whether they are emitted as part of the binary's generation for that prompt.

2. If diagnostics show the binary prints previous/stale output around our prompt time, prefer option (1) or (4): per-request runs (1) for immediate correctness in a controlled environment, or upstream fixes (4) to support long-running production workloads.

3. If diagnostics show the binary prints extra lines but only because of `--live_print`/`--continue`, try option (2) — turn off those flags — and re-test with the persistent REPL.

4. As an extra mitigation (safe, quick): add a configuration toggle to `ModelManager` to switch between persistent REPL and spawn-per-request modes. That lets operators choose correctness vs latency and eases testing.

## Suggested actions and short commands

- To reproduce a single-run invocation (shell):
```bash
cd models/Qwen2.5-1.5B-Instruct-GPTQ-Int4
./run_qwen2.5_1.5b_gptq_int4_axcl_aarch64.sh "<prompt here>"
```

- To test changing flags (quick experiment): edit `run_qwen2.5_1.5b_gptq_int4_axcl_aarch64.sh`, change `--continue 1` to `--continue 0` and `--live_print 1` to `--live_print 0`, and then restart `src/app.py`.

- To enable raw logging (temporary): modify `src/model_manager.py::_read_output()` to write timestamps before each logged line (example: `log_f.write(f"{time.time():.6f} | {line}")`) and restart the app. Capture one test request and inspect `logs/model_raw.log`.

## Files of interest (quick reference)

- `src/model_manager.py` — persistent REPL manager and current heuristics.
- `src/chat_completion.py` — orchestrates templating/tokenization and calls `ModelManager.generate()`.
- `models/.../run_qwen2.5_1.5b_gptq_int4_axcl_aarch64.sh` — the runner script that launches `main_axcl_aarch64` with live/continue flags.
- `models/qwen2.5_tokenizer.py` — tokenizer server (separate compatibility issues noted earlier).
- `logs/model.log` and `logs/model.log_error` — collected model stdout for analysis.

## Next steps (concrete)

1. (Recommended) Add temporary raw-timestamp logging in `ModelManager._read_output()` and capture a single request trace. Attach the trace for follow-up.
2. If the trace confirms the binary prints stale lines, either:
   - switch to spawn-per-request (fast to implement test), or
   - coordinate an upstream change to the Axera runtime to support synchronous request/response or disable the interactive extras.
3. Add a `config` option to choose the run mode (persistent vs spawn-per-request) and include rate-limiting / backoff to protect the NPU from frequent restarts.

## Appendix: quick patch hints

- Example change to `run_qwen2.5_...sh` to silence interactive output:
```diff
- --live_print 1 \
- --continue 1 \
+ --live_print 0 \
+ --continue 0 \
```

- Example logging addition in `ModelManager._read_output()` (temporary diagnostic):
```py
with open(log_file, 'a') as log_f:
    for line in self.process.stdout:
        ts = time.time()
        log_f.write(f"{ts:.6f} | {line}")
        log_f.flush()
        self._output_queue.put(line)
```

---

If you'd like, I can: (A) add the raw timestamp logging and capture a test, (B) flip the `--continue`/`--live_print` flags in the run script and restart the persistent process, or (C) implement an opt-in spawn-per-request flow (with a configuration toggle). Tell me which you prefer and I'll proceed and record the change in this docs file's history.
