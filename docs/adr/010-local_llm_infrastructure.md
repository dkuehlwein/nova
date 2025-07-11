# ADR-015: Local LLM Infrastructure with llama.cpp

**Date**: 2025-07-10  
**Status**: Proposed  
**Deciders**: Daniel (Product Owner), Claude Code (Implementation)

## Context

Nova currently relies on cloud-based LLMs (Google Gemini) and attempted to integrate local models via Ollama. However, research reveals that both DeepSeek R1 and Microsoft Phi-4 models have **broken function calling templates in Ollama**, causing endless tool-calling loops that make them unusable for agent applications.

Additionally, while vLLM offers superior performance, it lacks support for GGUF models due to missing DeepSeek architecture support in the transformers library, preventing use of the latest optimized models like Unsloth's DeepSeek variants.

### Current Issues with Ollama
- **DeepSeek R1**: Tool calling templates are broken, causing infinite loops
- **Phi-4**: Similar tool calling issues with unstable JSON responses
- **GitHub Issues**: [#8517](https://github.com/ollama/ollama/issues/8517), [#9437](https://github.com/ollama/ollama/issues/9437) - no clear fix timeline
- **Community workarounds**: Unreliable and require custom Modelfile modifications

### Business Requirements
- **Local inference**: Reduce cloud API dependencies and costs
- **Function calling**: Essential for Nova's agent architecture (tools like email, memory, task management)
- **Performance**: Support 16GB VRAM constraints
- **Reliability**: Production-ready solution for agent workloads

## Research Findings

### llama.cpp Advantages
1. **GGUF Model Support**: Full support for latest GGUF models including Unsloth DeepSeek variants
2. **Latest Models**: Access to cutting-edge quantized models like Q8_K_XL
3. **LiteLLM Integration**: Compatible with Nova's existing LiteLLM proxy via OpenAI-compatible server
4. **Mature & Stable**: Proven solution with extensive model support
5. **Function Calling**: Supports function calling via chat templates and JSON modes
6. **Quantization**: Native support for various quantization levels (Q2_K to Q8_0)

### llama.cpp Function Calling Features (2025)
- OpenAI-compatible function calling via `/v1/chat/completions`
- JSON mode with schema validation
- Custom chat templates for tool calling
- Grammar-guided generation for structured output

### Hardware Compatibility (16GB VRAM)
- **Q8_K_XL Models**: ~10GB VRAM (like DeepSeek-R1-0528-Qwen3-8B-Q8_K_XL)
- **Q4_K_M Models**: ~4-6GB VRAM for 8B parameter models  
- **Q2_K Models**: ~2-3GB VRAM for ultra-efficient deployment
- **CPU Offloading**: Can offload layers to system RAM when needed

### DeepSeek R1 in llama.cpp
- **Full GGUF Support**: ✅ Native support for all DeepSeek GGUF variants
- **Unsloth Models**: ✅ Full compatibility with optimized Unsloth quantizations
- **Latest Models**: Access to DeepSeek-R1-0528-Qwen3-8B-GGUF:Q8_K_XL
- **Performance**: Efficient inference with GPU acceleration
- **Quantization**: Multiple quantization levels available (Q2_K to Q8_0)
- **Quality**: R1-0528 models have improved accuracy and function calling

### Model Support Status
- **DeepSeek R1**: ✅ Full support including latest 0528 variants
- **Unsloth GGUF**: ✅ All quantization levels supported
- **Function Calling**: ✅ OpenAI-compatible endpoints with tool support
- **Performance**: ~11.5 tokens/s (vs vLLM 14.8 tokens/s) but access to latest models

## Decision

**Adopt llama.cpp as Nova's local LLM infrastructure** to replace Ollama, enabling access to the latest GGUF models including Unsloth DeepSeek variants with reliable function calling.

### Implementation Plan

#### Phase 1: llama.cpp Service Integration
1. **Docker Service**: Add llama.cpp server container to docker-compose.yml
2. **LiteLLM Configuration**: Configure llama.cpp as OpenAI-compatible provider
3. **Model Selection**: Deploy DeepSeek-R1-0528-Qwen3-8B-GGUF:Q8_K_XL
4. **Testing**: Validate function calling with Nova's tools

#### Phase 2: Production Optimization
1. **Performance Tuning**: Optimize GPU layers, context size, and batch parameters
2. **Model Management**: Implement model switching and loading strategies
3. **Monitoring**: Add health checks and performance metrics
4. **Documentation**: Update deployment and operations guides

#### Phase 3: Advanced Features
1. **Multiple Models**: Support multiple GGUF model variants
2. **Dynamic Loading**: Hot-swap models based on task requirements
3. **Quantization Management**: Optimize quantization levels for different use cases

## Technical Implementation

### Docker Compose Configuration
```yaml
llamacpp:
  image: ghcr.io/ggerganov/llama.cpp:server-cuda
  runtime: nvidia
  environment:
    - CUDA_VISIBLE_DEVICES=0
  ports:
    - "8080:8080"
  volumes:
    - ./models:/models
    - ~/.cache/huggingface:/root/.cache/huggingface
  command: >
    --server
    --host 0.0.0.0
    --port 8080
    --model /models/DeepSeek-R1-0528-Qwen3-8B-UD-Q8_K_XL.gguf
    --n-gpu-layers -1
    --ctx-size 32768
    --n-parallel 4
    --chat-template chatml
    --log-format json
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

### LiteLLM Configuration
```yaml
model_list:
  # llama.cpp Local Models
  - model_name: deepseek-r1-local
    litellm_params:
      model: openai/deepseek-r1
      api_base: http://llamacpp:8080/v1
      api_key: "not-required"
      
  # Fallback to cloud models
  - model_name: gemini-2.5-flash
    litellm_params:
      model: gemini/gemini-2.5-flash
      api_key: os.environ/GOOGLE_API_KEY

general_settings:
  fallbacks:
    - deepseek-r1-local: [gemini-2.5-flash]
    - gemini-2.5-flash: [deepseek-r1-local]
```

### Model Selection Strategy
1. **Primary**: DeepSeek-R1-0528-Qwen3-8B-UD-Q8_K_XL.gguf (~10GB VRAM - fits in 16GB)
2. **Alternative**: DeepSeek-R1-0528-Qwen3-8B-UD-Q4_K_M.gguf (~5GB VRAM for higher performance)
3. **Lightweight**: DeepSeek-R1-0528-Qwen3-8B-UD-Q2_K.gguf (~3GB VRAM for testing)
4. **Fallback**: Google Gemini 2.5 Flash for high-complexity tasks

### Available DeepSeek R1 GGUF Models for llama.cpp
- `unsloth/DeepSeek-R1-0528-Qwen3-8B-GGUF:Q8_K_XL` ✅ Primary Choice (~10GB VRAM)
- `unsloth/DeepSeek-R1-0528-Qwen3-8B-GGUF:Q4_K_M` ✅ Balanced performance (~5GB VRAM)
- `unsloth/DeepSeek-R1-0528-Qwen3-8B-GGUF:Q2_K` ✅ Lightweight option (~3GB VRAM)
- `unsloth/DeepSeek-R1-GGUF:Q8_0` ✅ Full model variant (if VRAM allows)
- All Unsloth quantization variants supported ✅

## Consequences

### Positive
- **Latest Models**: Access to cutting-edge GGUF models including Unsloth variants
- **Proven Function Calling**: OpenAI-compatible endpoints for agent applications  
- **Cost Reduction**: Reduced dependency on cloud APIs
- **Quantization Flexibility**: Multiple quantization levels for optimal VRAM usage
- **Mature Technology**: llama.cpp is stable and battle-tested
- **Community Support**: Extensive model ecosystem and community

### Negative
- **Performance Trade-off**: ~22% slower than vLLM (11.5 vs 14.8 tokens/s)
- **Setup Complexity**: More complex than Ollama but simpler than vLLM
- **Model Management**: Manual GGUF file management required
- **Memory Usage**: Large models still require significant VRAM

### Risks and Mitigations
- **GPU Memory**: Risk of OOM with Q8_K_XL models
  - *Mitigation*: Start with Q4_K_M, monitor VRAM usage, use CPU offloading
- **Setup Complexity**: Docker/GPU configuration and model downloads
  - *Mitigation*: Comprehensive documentation and automated setup scripts
- **Model Loading Time**: GGUF models can have longer load times
  - *Mitigation*: Keep models warm, implement health checks
- **Performance**: Slower than vLLM but faster than broken Ollama
  - *Mitigation*: Optimize batch sizes and context lengths, acceptable trade-off for latest models

## Alternatives Considered

### vLLM + Safetensors Models
- **Pros**: 22% faster performance, excellent function calling
- **Cons**: No GGUF support, cannot use latest Unsloth models
- **Decision**: Rejected due to requirement for latest GGUF models

### Wait for Ollama Fix
- **Pros**: Simpler setup, existing integration
- **Cons**: No timeline for fix, blocking Nova's local inference goals
- **Decision**: Rejected due to business impact and function calling issues

### Wait for vLLM GGUF Support  
- **Pros**: Would provide best performance with latest models
- **Cons**: No timeline for transformers library support, indefinite wait
- **Decision**: Rejected - cannot wait indefinitely for upstream fixes

### Text Generation WebUI
- **Pros**: Supports DeepSeek GGUF models, good UI
- **Cons**: Less suitable for API integration, more complex for headless deployment
- **Decision**: Considered but llama.cpp server is better for API use

### OpenLLM / TensorRT-LLM
- **Pros**: High performance alternatives
- **Cons**: Less mature LiteLLM integration, limited GGUF support
- **Decision**: Consider for future evaluation

## Implementation Timeline

- **Week 1**: Docker service setup and basic integration
- **Week 2**: LiteLLM configuration and function calling validation
- **Week 3**: Performance optimization and monitoring
- **Week 4**: Documentation and production deployment

## Success Criteria

1. **Function Calling**: 100% success rate for Nova's tools (memory, email, tasks)
2. **Performance**: <2s response time for typical agent queries
3. **Reliability**: 99.9% uptime for local inference service
4. **Resource Usage**: Efficient use of 16GB VRAM without OOM errors
5. **Integration**: Seamless switching between local and cloud models

## References

- [vLLM Documentation](https://docs.vllm.ai/)
- [LiteLLM vLLM Integration](https://docs.litellm.ai/docs/providers/vllm)
- [DeepSeek R1 Hardware Requirements](https://apxml.com/posts/gpu-requirements-deepseek-r1)
- [Ollama Function Calling Issues](https://github.com/ollama/ollama/issues/8517)