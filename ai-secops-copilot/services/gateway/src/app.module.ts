import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';

import configuration from './config/configuration';
import { FindingsModule } from './findings/findings.module';
import { GatewayModule } from './gateway/gateway.module';
import { HealthController } from './health/health.controller';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true, load: [configuration] }),
    GatewayModule,
    FindingsModule,
  ],
  controllers: [HealthController],
})
export class AppModule {}
