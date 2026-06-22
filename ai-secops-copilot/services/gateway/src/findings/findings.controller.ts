import { Body, Controller, Post } from '@nestjs/common';

import { AnalyzeFindingDto } from './dto/analyze-finding.dto';
import { FindingsService } from './findings.service';

@Controller('findings')
export class FindingsController {
  constructor(private readonly findings: FindingsService) {}

  /** Validate a finding at the edge, then hand it to the agent runtime. */
  @Post('analyze')
  analyze(@Body() dto: AnalyzeFindingDto): Promise<unknown> {
    return this.findings.analyze(dto);
  }
}
