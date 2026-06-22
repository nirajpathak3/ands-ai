import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

import { LlmProvider, LlmRequest, LlmResponse, ProviderNotConfiguredError } from '../llm.types';

/**
 * Anthropic (Claude) provider (fallback). Day-1 scaffold; the real `anthropic`
 * SDK call is wired on Day 11. Engaged automatically by the Gateway when the
 * primary provider fails (ADR-006).
 */
@Injectable()
export class AnthropicProvider implements LlmProvider {
  readonly name = 'anthropic';

  constructor(private readonly config: ConfigService) {}

  isConfigured(): boolean {
    return Boolean(this.config.get<string>('gateway.fallback.apiKey'));
  }

  async complete(_req: LlmRequest): Promise<LlmResponse> {
    if (!this.isConfigured()) {
      throw new ProviderNotConfiguredError(this.name);
    }
    // TODO(Day 11): call the Anthropic Messages API and map to LlmResponse.
    throw new Error('AnthropicProvider.complete not implemented yet (wired on Day 11).');
  }
}
