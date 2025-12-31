# ADR-009: Hybrid LLM Architecture with LiteLLM Gateway

> **Status**: ARCHIVED - SUPERSEDED
> **Archived Date**: 2025-12-31
> **Superseded By**: [ADR-011: LiteLLM-First Model Management Architecture](../011-simplified-model-management-system.md)
> **Reason**: The hybrid provider approach with separate provider selection has been replaced by a unified LiteLLM-first architecture where all LLM requests route through LiteLLM as the single gateway.

---

*Original content preserved below for historical reference:*

---

**Date**: 2025-07-11
**Status**: Superseded by ADR-011

## Context

Nova initially relied exclusively on Google's Gemini API, creating dependencies related to rate limiting, cost, internet reliability, and data privacy. The goal was to introduce a hybrid architecture supporting both cloud and local LLMs to mitigate these issues.

After extensive research, we discovered that Ollama had broken function calling templates for DeepSeek R1 and other models crucial for agent applications. This led us to adopt llama.cpp as our local inference engine, integrated through LiteLLM as a unified gateway.

## Decision

We implemented a **unified LLM architecture** using **LiteLLM** as the central gateway for ALL LLM requests. This proxy service routes requests to either:
- **Local Models**: DeepSeek R1 via llama.cpp with GPU acceleration
- **Cloud Models**: Google Gemini via API

## What Changed in ADR-011

ADR-011 evolved this architecture to be truly "LiteLLM-first":

1. **Memory System Migration**: Graphiti memory was migrated from hardcoded Gemini to LiteLLM routing via OpenAI-compatible clients
2. **Simplified Configuration**: Models are now dynamically discovered rather than statically configured
3. **User-Configurable Models**: Separate settings for chat, memory, and embedding models
4. **Provider Agnostic**: No longer requires specific provider clients - everything goes through LiteLLM's OpenAI-compatible API

## Key Learnings

- LiteLLM provides excellent abstraction over multiple LLM providers
- llama.cpp with CUDA provides reliable local inference with proper function calling
- Dynamic model registration is superior to static YAML configuration
- Memory systems should not be locked to specific providers

See ADR-011 for the current LiteLLM-first architecture.
