import { Inject, Injectable, Logger, ServiceUnavailableException } from '@nestjs/common';

import { estimateCostUsd } from './cost';
import { GatewayResult, LlmProvider, LlmRequest, ProviderNotConfiguredError } from './llm.types';

export const LLM_PROVIDERS = 'LLM_PROVIDERS';

interface GatewayMetrics {
  totalRequests: number;
  totalFailures: number;
  fallbackUsed: number;
  cacheHits: number;
  totalCostUsd: number;
  totalTokens: number;
  totalLatencyMs: number;
  byProvider: Record<string, number>;
}

/**
 * AI Gateway: the single egress for all LLM calls (ADR-006).
 *
 * Responsibilities (kept deliberately thin): provider routing with ordered
 * fallback (OpenAI -> Claude), cost/latency/token tracking, and a semantic-cache
 * hook. Apps never call providers directly, so cost control and observability
 * live in exactly one place.
 */
@Injectable()
export class GatewayService {
  private readonly logger = new Logger(GatewayService.name);

  private readonly metrics: GatewayMetrics = {
    totalRequests: 0,
    totalFailures: 0,
    fallbackUsed: 0,
    cacheHits: 0,
    totalCostUsd: 0,
    totalTokens: 0,
    totalLatencyMs: 0,
    byProvider: {},
  };

  constructor(@Inject(LLM_PROVIDERS) private readonly providers: LlmProvider[]) {}

  /**
   * Complete a request, trying providers in order until one succeeds.
   * Throws ServiceUnavailable only when every configured provider fails.
   */
  async complete(req: LlmRequest): Promise<GatewayResult> {
    this.metrics.totalRequests += 1;
    const attempts: GatewayResult['attempts'] = [];
    const start = Date.now();

    for (let i = 0; i < this.providers.length; i += 1) {
      const provider = this.providers[i];
      if (!provider.isConfigured()) {
        attempts.push({ provider: provider.name, ok: false, error: 'not_configured' });
        continue;
      }
      try {
        const response = await provider.complete(req);
        const latencyMs = Date.now() - start;
        const costUsd = estimateCostUsd(response.model, response.usage);

        attempts.push({ provider: provider.name, ok: true });
        if (i > 0) this.metrics.fallbackUsed += 1;
        this.record(provider.name, latencyMs, costUsd, response.usage.totalTokens);

        return { response, provider: provider.name, latencyMs, costUsd, cacheHit: false, attempts };
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        const reason = err instanceof ProviderNotConfiguredError ? 'not_configured' : message;
        attempts.push({ provider: provider.name, ok: false, error: reason });
        this.logger.warn(`provider '${provider.name}' failed: ${reason}`);
      }
    }

    this.metrics.totalFailures += 1;
    throw new ServiceUnavailableException({
      message: 'All LLM providers are unavailable.',
      attempts,
    });
  }

  getMetrics(): GatewayMetrics & { meanLatencyMs: number; costPerRequestUsd: number } {
    const n = this.metrics.totalRequests || 1;
    return {
      ...this.metrics,
      meanLatencyMs: this.metrics.totalLatencyMs / n,
      costPerRequestUsd: this.metrics.totalCostUsd / n,
    };
  }

  private record(provider: string, latencyMs: number, costUsd: number, tokens: number): void {
    this.metrics.totalLatencyMs += latencyMs;
    this.metrics.totalCostUsd += costUsd;
    this.metrics.totalTokens += tokens;
    this.metrics.byProvider[provider] = (this.metrics.byProvider[provider] ?? 0) + 1;
  }
}
