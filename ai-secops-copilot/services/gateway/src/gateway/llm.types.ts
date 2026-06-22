export type LlmRole = 'system' | 'user' | 'assistant';

export interface LlmMessage {
  role: LlmRole;
  content: string;
}

export interface LlmRequest {
  messages: LlmMessage[];
  temperature?: number;
  maxTokens?: number;
  /** Optional JSON schema for structured-output enforcement (ADR-010). */
  jsonSchema?: Record<string, unknown>;
}

export interface LlmUsage {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
}

export interface LlmResponse {
  content: string;
  provider: string;
  model: string;
  usage: LlmUsage;
}

/** A single LLM provider behind the Gateway (OpenAI primary, Claude fallback). */
export interface LlmProvider {
  readonly name: string;
  isConfigured(): boolean;
  complete(req: LlmRequest): Promise<LlmResponse>;
}

export class ProviderNotConfiguredError extends Error {
  constructor(provider: string) {
    super(`Provider '${provider}' is not configured (missing API key).`);
    this.name = 'ProviderNotConfiguredError';
  }
}

/** Result the Gateway returns to callers, enriched with observability data. */
export interface GatewayResult {
  response: LlmResponse;
  provider: string;
  latencyMs: number;
  costUsd: number;
  cacheHit: boolean;
  /** Providers attempted, in order, with outcome (for tracing/fallback story). */
  attempts: Array<{ provider: string; ok: boolean; error?: string }>;
}
