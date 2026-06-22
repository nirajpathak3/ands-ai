import { LlmUsage } from './llm.types';

/**
 * Approximate public list prices in USD per 1K tokens. These are configurable
 * estimates used for cost tracking on the dashboard, not billing. Update as
 * provider pricing changes.
 */
interface ModelPrice {
  inputPer1k: number;
  outputPer1k: number;
}

const PRICE_TABLE: Record<string, ModelPrice> = {
  'gpt-4o-mini': { inputPer1k: 0.00015, outputPer1k: 0.0006 },
  'gpt-4o': { inputPer1k: 0.005, outputPer1k: 0.015 },
  'claude-3-5-sonnet-latest': { inputPer1k: 0.003, outputPer1k: 0.015 },
  'claude-3-5-haiku-latest': { inputPer1k: 0.0008, outputPer1k: 0.004 },
};

const DEFAULT_PRICE: ModelPrice = { inputPer1k: 0.001, outputPer1k: 0.002 };

export function estimateCostUsd(model: string, usage: LlmUsage): number {
  const price = PRICE_TABLE[model] ?? DEFAULT_PRICE;
  const cost =
    (usage.promptTokens / 1000) * price.inputPer1k +
    (usage.completionTokens / 1000) * price.outputPer1k;
  // Round to 6 dp to keep small per-call costs meaningful.
  return Math.round(cost * 1e6) / 1e6;
}
