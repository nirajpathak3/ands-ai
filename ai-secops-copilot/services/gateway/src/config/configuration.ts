export interface ProviderConfig {
  apiKey?: string;
  model: string;
}

export interface AppConfig {
  port: number;
  environment: string;
  agentRuntimeUrl: string;
  gateway: {
    primary: ProviderConfig;
    fallback: ProviderConfig;
    cacheEnabled: boolean;
  };
}

export default (): AppConfig => ({
  port: parseInt(process.env.PORT ?? '3000', 10),
  environment: process.env.NODE_ENV ?? 'development',
  agentRuntimeUrl: process.env.AGENT_RUNTIME_URL ?? 'http://localhost:8088',
  gateway: {
    // OpenAI is primary; Claude is the fallback (ADR-006). No sophisticated router.
    primary: {
      apiKey: process.env.OPENAI_API_KEY,
      model: process.env.OPENAI_MODEL ?? 'gpt-4o-mini',
    },
    fallback: {
      apiKey: process.env.ANTHROPIC_API_KEY,
      model: process.env.ANTHROPIC_MODEL ?? 'claude-3-5-sonnet-latest',
    },
    cacheEnabled: (process.env.GATEWAY_CACHE_ENABLED ?? 'false') === 'true',
  },
});
