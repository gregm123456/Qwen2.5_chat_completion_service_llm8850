# Known Issues and Limitations

## Model Integration Issue

### Problem
The current implementation cannot start successfully because of an architectural mismatch between the service design and the actual model runner.

**Expected:**
- The plan assumed the model would run as a persistent RPC server
- Model would stay loaded and accept requests via Unix socket or TCP

**Actual Reality:**
- `main_axcl_aarch64` is a **CLI tool** that runs once per prompt
- The runner script `run_qwen2.5_1.5b_gptq_int4_axcl_aarch64.sh` expects:
  ```bash
  --prompt "$1"  # Single prompt argument
  ```
- Model loads, generates response, and **exits** (not persistent)

### Current Error
```
[E][init][ 386]: Set AXCL device failed{0x80300186}.
[device manager][request_ports][464]: request ports from device 1 fail, errno: 1 Operation not permitted
```

This error occurs because the model tries to initialize NPU but the script doesn't provide a prompt, so it may be failing in an unexpected way.

### Solutions

#### Option 1: Per-Request Model Loading (Simple but Slow)
Modify `ModelManager` to:
- Run the model binary once per chat request
- Pass the full formatted prompt as `--prompt "..."`
- Wait for output, capture result
- Model exits after each request

**Pros:** Works with existing binary
**Cons:** Slow (model reload every request), defeats purpose of keeping model in NPU

#### Option 2: Interactive Wrapper (Better Performance)
Create a wrapper script/program that:
- Launches `main_axcl_aarch64` in interactive mode (if supported)
- Keeps model loaded in NPU
- Exposes Unix socket/TCP interface
- Routes requests to the loaded model

**Pros:** Fast, model stays loaded
**Cons:** Requires examining `main_axcl_aarch64` capabilities or wrapping it

#### Option 3: Modify C++ Binary (Best but Complex)
If source code is available:
- Modify `main_axcl_aarch64` to run as a daemon
- Add socket/TCP listener
- Keep model loaded between requests

**Pros:** Optimal performance, clean architecture
**Cons:** Requires C++ changes, recompilation

## Recommended Next Steps

1. **Test the model directly** to verify it works:
   ```bash
   cd models/Qwen2.5-1.5B-Instruct-GPTQ-Int4
   source /etc/profile
   bash run_qwen2.5_1.5b_gptq_int4_axcl_aarch64.sh "Hello, how are you?"
   ```

2. **Check if interactive mode exists:**
   ```bash
   ./main_axcl_aarch64 --help
   ```
   Look for options like `--interactive`, `--server`, or `--daemon`

3. **Implement Option 1 as a quick proof-of-concept:**
   - Modify `model_manager.py` to run model per request
   - Accept slower performance as trade-off
   - Get end-to-end API working

4. **Then pursue Option 2:**
   - Write a Python/bash wrapper that manages model lifecycle
   - Implement proper RPC interface
   - Achieve production-ready performance

## Current Status

- ✅ Tokenizer server: **Working**
- ✅ Configuration: **Working**
- ✅ FastAPI endpoints: **Implemented**
- ❌ Model integration: **Blocked by architectural mismatch**

The service infrastructure is complete and correct, but needs adaptation for the actual model binary's interface.
