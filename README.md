# Qwen2.5 Chat Completion Service

This repository will host the Qwen2.5 chat-completion service which exposes an OpenAI-compatible `/v1/chat/completions` API backed by the Qwen2.5 model on LLM-8850.

This is the service scaffold. The model binaries and tokenizer are downloaded separately into `models/` (the `models/` directory is gitignored).

See `reference_documentation/plan.md` for the full implementation plan and next steps.

Quick start (development):

1. Create a Python virtualenv and install dependencies (later: `requirements.txt`).
2. Download the model repo into `models/Qwen2.5-1.5B-Instruct-GPTQ-Int4/` per the plan.
3. Implement and run the service (FastAPI) locally for development.
