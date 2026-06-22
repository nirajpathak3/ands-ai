import { Controller, Get } from '@nestjs/common';

import { GatewayService } from './gateway.service';

@Controller('gateway')
export class GatewayController {
  constructor(private readonly gateway: GatewayService) {}

  /** Cost / latency / token / fallback counters for the dashboard. */
  @Get('metrics')
  metrics(): ReturnType<GatewayService['getMetrics']> {
    return this.gateway.getMetrics();
  }
}
