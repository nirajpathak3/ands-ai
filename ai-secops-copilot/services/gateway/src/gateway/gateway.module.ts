import { Module } from '@nestjs/common';

import { GatewayController } from './gateway.controller';
import { GatewayService, LLM_PROVIDERS } from './gateway.service';
import { LlmProvider } from './llm.types';
import { AnthropicProvider } from './providers/anthropic.provider';
import { OpenAiProvider } from './providers/openai.provider';

@Module({
  controllers: [GatewayController],
  providers: [
    OpenAiProvider,
    AnthropicProvider,
    {
      // Ordered provider chain: primary first, fallback second (ADR-006).
      provide: LLM_PROVIDERS,
      useFactory: (primary: OpenAiProvider, fallback: AnthropicProvider): LlmProvider[] => [
        primary,
        fallback,
      ],
      inject: [OpenAiProvider, AnthropicProvider],
    },
    GatewayService,
  ],
  exports: [GatewayService],
})
export class GatewayModule {}
