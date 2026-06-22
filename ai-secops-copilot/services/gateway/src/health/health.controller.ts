import { Controller, Get } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

@Controller()
export class HealthController {
  constructor(private readonly config: ConfigService) {}

  @Get()
  root(): { name: string; status: string } {
    return { name: 'ai-secops-gateway', status: 'ok' };
  }

  @Get('health')
  health(): Record<string, unknown> {
    return {
      status: 'ok',
      service: 'gateway',
      environment: this.config.get<string>('environment'),
      agentRuntimeUrl: this.config.get<string>('agentRuntimeUrl'),
      gateway: {
        // Report configuration *presence*, never the secret values.
        primaryConfigured: Boolean(this.config.get('gateway.primary.apiKey')),
        fallbackConfigured: Boolean(this.config.get('gateway.fallback.apiKey')),
        cacheEnabled: this.config.get<boolean>('gateway.cacheEnabled'),
      },
    };
  }
}
