import { ServiceUnavailableException } from '@nestjs/common';

import { GatewayService } from './gateway.service';
import { LlmProvider, LlmRequest, LlmResponse } from './llm.types';

function makeProvider(
  name: string,
  opts: { configured?: boolean; fail?: boolean } = {},
): LlmProvider {
  const { configured = true, fail = false } = opts;
  return {
    name,
    isConfigured: () => configured,
    complete: async (_req: LlmRequest): Promise<LlmResponse> => {
      if (fail) throw new Error(`${name} boom`);
      return {
        content: `{"ok": true, "from": "${name}"}`,
        provider: name,
        model: 'gpt-4o-mini',
        usage: { promptTokens: 100, completionTokens: 50, totalTokens: 150 },
      };
    },
  };
}

const REQ: LlmRequest = { messages: [{ role: 'user', content: 'hi' }] };

describe('GatewayService', () => {
  it('uses the primary provider when it succeeds', async () => {
    const svc = new GatewayService([makeProvider('openai'), makeProvider('anthropic')]);
    const result = await svc.complete(REQ);
    expect(result.provider).toBe('openai');
    expect(result.costUsd).toBeGreaterThan(0);
    expect(result.attempts).toEqual([{ provider: 'openai', ok: true }]);
  });

  it('falls back to the secondary provider when the primary fails', async () => {
    const svc = new GatewayService([
      makeProvider('openai', { fail: true }),
      makeProvider('anthropic'),
    ]);
    const result = await svc.complete(REQ);
    expect(result.provider).toBe('anthropic');
    expect(svc.getMetrics().fallbackUsed).toBe(1);
    expect(result.attempts[0]).toEqual({ provider: 'openai', ok: false, error: 'openai boom' });
  });

  it('skips unconfigured providers', async () => {
    const svc = new GatewayService([
      makeProvider('openai', { configured: false }),
      makeProvider('anthropic'),
    ]);
    const result = await svc.complete(REQ);
    expect(result.provider).toBe('anthropic');
    expect(result.attempts[0]).toEqual({ provider: 'openai', ok: false, error: 'not_configured' });
  });

  it('throws ServiceUnavailable when every provider fails', async () => {
    const svc = new GatewayService([
      makeProvider('openai', { fail: true }),
      makeProvider('anthropic', { fail: true }),
    ]);
    await expect(svc.complete(REQ)).rejects.toBeInstanceOf(ServiceUnavailableException);
    expect(svc.getMetrics().totalFailures).toBe(1);
  });

  it('tracks cost and latency metrics', async () => {
    const svc = new GatewayService([makeProvider('openai')]);
    await svc.complete(REQ);
    const m = svc.getMetrics();
    expect(m.totalRequests).toBe(1);
    expect(m.totalTokens).toBe(150);
    expect(m.costPerRequestUsd).toBeGreaterThan(0);
  });
});
