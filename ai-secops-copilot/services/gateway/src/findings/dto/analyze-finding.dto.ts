import { Type } from 'class-transformer';
import {
  IsInt,
  IsObject,
  IsOptional,
  IsString,
  Min,
  ValidateNested,
} from 'class-validator';

/** Normalized SARIF/Semgrep-style finding (ADR-007), validated at the edge. */
export class FindingDto {
  @IsString() id!: string;
  @IsOptional() @IsString() scanner?: string;
  @IsString() ruleId!: string;
  @IsString() title!: string;
  @IsString() message!: string;
  @IsString() file!: string;

  @IsOptional() @IsInt() @Min(0) startLine?: number;
  @IsOptional() @IsInt() @Min(0) endLine?: number;
  @IsOptional() @IsString() codeSnippet?: string;
  @IsOptional() @IsString() cwe?: string;
  @IsOptional() @IsString() owasp?: string;
  @IsOptional() @IsString() scannerSeverity?: string;
}

export class AnalyzeFindingDto {
  @IsObject()
  @ValidateNested()
  @Type(() => FindingDto)
  finding!: FindingDto;
}
