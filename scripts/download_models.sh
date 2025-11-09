#!/bin/bash
# Download and pin the Qwen2.5-1.5B-Instruct-GPTQ-Int4 model repository
# This script clones the model repo and checks out a specific pinned commit
# for reproducibility and stability.

set -e  # Exit on error

# Pinned model repository details
MODEL_REPO_URL="https://huggingface.co/AXERA-TECH/Qwen2.5-1.5B-Instruct-GPTQ-Int4"
PINNED_COMMIT="01d5a6eb90d9be5dd3de32518ec99c04d9ae5da5"
MODEL_DIR="models/Qwen2.5-1.5B-Instruct-GPTQ-Int4"

# Get script directory (project root)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

echo "========================================"
echo "Qwen2.5 Model Download Script"
echo "========================================"
echo ""
echo "This script will download the Qwen2.5-1.5B-Instruct-GPTQ-Int4 model"
echo "repository to: $PROJECT_ROOT/$MODEL_DIR"
echo ""
echo "Pinned repository: $MODEL_REPO_URL"
echo "Pinned commit: $PINNED_COMMIT"
echo ""

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "Error: git is not installed. Please install git first."
    exit 1
fi

# Create models directory if it doesn't exist
cd "$PROJECT_ROOT"
mkdir -p models

# Check if model directory already exists
if [ -d "$MODEL_DIR" ]; then
    echo "Model directory already exists: $MODEL_DIR"
    echo ""
    read -p "Do you want to re-download? This will remove the existing directory. (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Removing existing model directory..."
        rm -rf "$MODEL_DIR"
    else
        echo "Using existing model directory."
        echo ""
        echo "Verifying pinned commit..."
        cd "$MODEL_DIR"
        CURRENT_COMMIT=$(git rev-parse HEAD)
        if [ "$CURRENT_COMMIT" = "$PINNED_COMMIT" ]; then
            echo "✓ Model is at pinned commit: $PINNED_COMMIT"
            exit 0
        else
            echo "⚠ Warning: Model is at commit $CURRENT_COMMIT (expected $PINNED_COMMIT)"
            echo "Run this script again and choose to re-download for the pinned version."
            exit 1
        fi
    fi
fi

# Clone the repository
echo "Cloning model repository..."
echo "This will download approximately 1.5GB of data."
echo ""

git clone "$MODEL_REPO_URL" "$MODEL_DIR"

# Checkout pinned commit
echo ""
echo "Checking out pinned commit: $PINNED_COMMIT"
cd "$MODEL_DIR"
git checkout "$PINNED_COMMIT"

echo ""
echo "========================================"
echo "Download Complete!"
echo "========================================"
echo ""
echo "Model repository downloaded to: $PROJECT_ROOT/$MODEL_DIR"
echo "Pinned to commit: $PINNED_COMMIT"
echo ""
echo "Important files:"
echo "  - Tokenizer: qwen2.5_tokenizer.py"
echo "  - Model runner: run_qwen2.5_1.5b_gptq_int4_axcl_aarch64.sh"
echo "  - Model binaries: main_axcl_aarch64"
echo ""
echo "Note: The model runner script may need to be modified to expose"
echo "      an RPC interface (Unix socket or TCP) for production use."
echo "      See reference_documentation/plan.md for details."
echo ""
echo "Next steps:"
echo "  1. Verify the LLM-8850 driver is installed (/etc/profile)"
echo "  2. Test the tokenizer: cd $MODEL_DIR && python qwen2.5_tokenizer.py"
echo "  3. Test the model: cd $MODEL_DIR && bash run_qwen2.5_1.5b_gptq_int4_axcl_aarch64.sh"
echo "  4. Install service dependencies: pip install -r requirements.txt"
echo "  5. Start the service: python src/app.py"
echo ""
