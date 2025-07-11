# Models Directory

This directory is used by llama.cpp for local model caching when using Hugging Face direct loading.

## Quick Start

Nova is configured to automatically download and load models from Hugging Face:

```bash
# Start llama.cpp service (automatically downloads model)
docker-compose up -d llamacpp
```

The service will automatically download the DeepSeek R1 Q8_K_XL model on first startup.

## Model Variants

### DeepSeek R1 0528 (Recommended)

- **Q8_K_XL**: `DeepSeek-R1-0528-Qwen3-8B-UD-Q8_K_XL.gguf` (~10GB VRAM)
  - Highest quality quantization that fits in 16GB VRAM
  - Primary model configured in docker-compose.yml
  
- **Q4_K_M**: `DeepSeek-R1-0528-Qwen3-8B-UD-Q4_K_M.gguf` (~5GB VRAM)
  - Balanced performance and quality
  - Good for testing or higher throughput

- **Q2_K**: `DeepSeek-R1-0528-Qwen3-8B-UD-Q2_K.gguf` (~3GB VRAM)
  - Ultra-lightweight for testing
  - Lower quality but very fast

## Automatic Model Loading

Nova uses llama.cpp's Hugging Face integration to automatically download models:

```yaml
# Current configuration in docker-compose.yml
command: >
  --server
  --host 0.0.0.0
  --port 8080
  --hf-repo unsloth/DeepSeek-R1-0528-Qwen3-8B-GGUF
  --hf-file DeepSeek-R1-0528-Qwen3-8B-UD-Q8_K_XL.gguf
  --n-gpu-layers -1
  --ctx-size 32768
  --n-parallel 4
  --chat-template chatml
  --log-format json
```

## Manual Download (Optional)

If you prefer to manually manage models, you can use huggingface-cli:

```bash
# Install huggingface-hub
pip install huggingface-hub

# Download specific model file
huggingface-cli download unsloth/DeepSeek-R1-0528-Qwen3-8B-GGUF \
  DeepSeek-R1-0528-Qwen3-8B-UD-Q8_K_XL.gguf \
  --local-dir ./models

# Then update docker-compose.yml to use local file:
# --model /models/DeepSeek-R1-0528-Qwen3-8B-UD-Q8_K_XL.gguf
```

## Model Selection

The docker-compose.yml is configured to use the Q8_K_XL model by default:

```yaml
--hf-repo unsloth/DeepSeek-R1-0528-Qwen3-8B-GGUF
--hf-file DeepSeek-R1-0528-Qwen3-8B-UD-Q8_K_XL.gguf
```

To use a different model, update the `--hf-file` parameter in the llamacpp service command:

```yaml
# For Q4_K_M (lighter, faster)
--hf-file DeepSeek-R1-0528-Qwen3-8B-UD-Q4_K_M.gguf

# For Q2_K (very lightweight)
--hf-file DeepSeek-R1-0528-Qwen3-8B-UD-Q2_K.gguf
```

## Performance Specifications

| Model | VRAM | Quality | Speed | Use Case |
|-------|------|---------|-------|----------|
| Q8_K_XL | ~10GB | Highest | Good | Production (16GB VRAM) |
| Q4_K_M | ~5GB | Good | Fast | Balanced performance |
| Q2_K | ~3GB | Lower | Fastest | Testing/development |

## Troubleshooting

### Out of Memory (OOM) Errors

If you encounter OOM errors with Q8_K_XL:

1. Switch to Q4_K_M model
2. Reduce context size: `--ctx-size 16384`
3. Enable CPU offloading: `--n-gpu-layers 20` (instead of -1)

### Model Loading Issues

- Ensure the model file is completely downloaded
- Check file permissions: `chmod 644 models/*.gguf`
- Verify the file path matches the docker-compose.yml configuration

## Links

- [Unsloth DeepSeek R1 GGUF Models](https://huggingface.co/unsloth/DeepSeek-R1-0528-Qwen3-8B-GGUF)
- [llama.cpp Documentation](https://github.com/ggerganov/llama.cpp)
- [Nova ADR-015: Local LLM Infrastructure](../docs/adr/010-local_llm_infrastructure.md)