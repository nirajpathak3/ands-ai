import { HttpException, Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import axios, { AxiosError } from 'axios';

import { AnalyzeFindingDto } from './dto/analyze-finding.dto';

/**
 * Bridges the control plane to the Python agent runtime. The runtime owns the
 * LangGraph orchestration; the gateway owns ingress validation, the LLM egress,
 * and (later) ticketing/observability.
 */
@Injectable()
export class FindingsService {
  private readonly logger = new Logger(FindingsService.name);

  constructor(private readonly config: ConfigService) {}

  async analyze(dto: AnalyzeFindingDto): Promise<unknown> {
    const baseUrl = this.config.get<string>('agentRuntimeUrl');
    try {
      const { data } = await axios.post(`${baseUrl}/analyze`, dto, { timeout: 30_000 });
      return data;
    } catch (err) {
      const axErr = err as AxiosError;
      if (axErr.response) {
        // Surface the runtime's status/body (e.g. its Day-1 501) transparently.
        throw new HttpException(axErr.response.data ?? axErr.message, axErr.response.status);
      }
      this.logger.error(`agent-runtime unreachable at ${baseUrl}: ${axErr.message}`);
      throw new HttpException(
        { message: 'agent-runtime is unreachable', agentRuntimeUrl: baseUrl },
        502,
      );
    }
  }
}
