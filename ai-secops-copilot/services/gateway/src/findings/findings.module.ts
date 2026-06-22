import { Module } from '@nestjs/common';

import { GatewayModule } from '../gateway/gateway.module';
import { FindingsController } from './findings.controller';
import { FindingsService } from './findings.service';

@Module({
  imports: [GatewayModule],
  controllers: [FindingsController],
  providers: [FindingsService],
})
export class FindingsModule {}
