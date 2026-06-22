import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

import { LlmProvider, LlmRequest, LlmResponse, ProviderNotConfiguredError } from '../llm.types';

/**
 * OpenAI provider (primary). Day-1 scaffold: reports configuration state and
 * defines the contract. The real `openai` SDK call is wired on Day 11.
 */
@Injectable()
export class OpenAiProvider implements LlmProvider {
  readonly name = 'openai';

  constructor(private readonly config: ConfigService) {}

  isConfigured(): boolean {
    return Boolean(this.config.get<string>('gateway.primary.apiKey'));
  }

  async complete(_req: LlmRequest): Promise<LlmResponse> {
    if (!this.isConfigured()) {
      throw new ProviderNotConfiguredError(this.name);
    }
    // TODO(Day 11): call the OpenAI Chat Completions / Responses API with
    // structured-output (json_schema) and return the validated content + usage.
    throw new Error('OpenAiProvider.complete not implemented yet (wired on Day 11).');
  }
}
