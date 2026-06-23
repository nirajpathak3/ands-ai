# Resume, Portal & Interview Prep — Niraj Anand Pathak

---

## Resume — revised full draft

---

**NIRAJ ANAND PATHAK**
Backend Architect | AI Platform Engineer
nirajanand.pathak@gmail.com | +91 87289-54445 | Chandigarh, India
linkedin.com/in/nirajanandpathak | github.com/[your-handle]

---

### Professional Summary

I've spent 17 years building the kind of backend systems that can't fail — distributed orchestration
platforms, federated APIs, enterprise integrations, and observability stacks across security,
healthcare, and SaaS. At Ox Security, I was the backend architect behind a large-scale ASPM platform
that processed security data across 100+ vendor integrations, and I know what it takes to keep
something like that reliable at production scale.

What pulled me into AI platform engineering wasn't the hype. It's that agentic systems need exactly
what I've been building for years — orchestration, governance, cost control, failure recovery, and
human oversight. The difference is there's non-determinism in the loop now, which makes it harder
and more interesting.

I'm building an AI Security Operations Copilot: it takes scanner findings, reasons over them with
RAG-grounded security knowledge, and drives ticket lifecycle through confidence-gated workflows —
with evaluation pipelines to prove it works and observability to prove it's healthy.

---

### AI Platform Projects

**AI Security Operations Copilot** — In active development
github.com/[your-handle]/ai-secops-copilot

An enterprise AI platform that automates the security-finding lifecycle — from analysis and
false-positive detection to governed Jira ticket creation and remediation tracking.

- Ingests Semgrep/SARIF findings and runs a LangGraph agent pipeline (Finding Analysis →
  Ticket Decision → Governance Gate) with structured Pydantic output validation at each step
- RAG layer (pgvector + OWASP/CWE/CVE corpus) grounds reasoning and cites knowledge sources
  rather than letting the model hallucinate severity
- Confidence-gated governance: above threshold → auto-execute; in the middle band → human
  approval; below → escalate. Same pattern I used in a real-time automation system, now applied
  to security ops
- MCP tool layer drives Jira (real) and ServiceNow (mock) in a provider-agnostic way — swap
  adapters without touching decision logic
- AI Gateway (NestJS) sits in front of every model call: OpenAI primary, Claude fallback,
  Redis semantic cache, token/cost/latency tracking per request
- Evaluation harness on a labeled golden dataset — severity accuracy, FP precision/recall,
  ticket-action accuracy — runs after every prompt or model change to catch regressions
- Idempotent ticket creation using finding hash keys; structured output validation before
  any tool runs; prompt-injection isolation for untrusted finding content

Stack: Python · LangGraph · FastAPI · NestJS/TypeScript · pgvector · Redis · OpenAI/Anthropic ·
Langfuse · OpenTelemetry

---

**Real-Time Agentic Automation Platform** — obs-agent
github.com/[your-handle]/obs-agent

Production-oriented platform that uses real-time audio cues to drive automated actions through
a confidence-gated, human-in-the-loop governance model.

- Audio pipeline: FFmpeg capture → Whisper STT → intent detection → confidence scoring
- Governance module: three-disposition model (auto-execute / suggest / suppress) based on
  confidence thresholds and operator mode — all implemented as DDD aggregates
- Human-in-the-loop approval queue with audit trails and auto-downgrade on sustained low
  confidence
- Event-driven NestJS architecture with domain events, bounded contexts, and JSONL audit
  logging
- Structured observability: every decision, action, and transition logged via pino

Stack: NestJS · TypeScript · DDD · Whisper STT · Redis · WebSocket · OpenTelemetry

---

**Multi-Agent Orchestration Platform** — veho-platform
(Active development — LangGraph upgrade in progress)

Governed SDLC orchestration framework where specialized agents collaborate through gated
workflows — Intake → Plan → Architect → Build → Review → QA → Release.

- Shared blackboard state per project; agents read and write structured context without
  tight coupling
- Human approval gates between each phase; escalation paths for failures
- Pattern mirrors what most teams need once AI is in the development loop

Stack: TypeScript · NestJS · LangGraph (in progress) · Redis

---

### Work Experience

**Backend Architect — Orangebits / Ox Security** | Oct 2023 – May 2026

Ox Security builds an Application Security Posture Management platform. I was the backend
architect responsible for the orchestration and integration layer.

- Distributed Orchestration: designed the orchestration services that process and correlate
  security findings across 100+ vendor integrations — event-driven, BullMQ-backed, built for
  backpressure, idempotency, and retry at scale
- Federated API Platform: architected and evolved the Apollo Federation v2 layer (6+
  microservice domains), enabling teams to own their schemas while the platform composes them
- Enterprise Integrations: built resilient adapters for Jira, ServiceNow, Azure Boards, GitHub,
  and security tool ecosystems — async, rate-limited, fault-tolerant
- Observability: extended Datadog and OpenSearch observability, introduced distributed tracing
  and SLO-based reliability practices
- Applied LangChain/LangGraph-based automation patterns to engineering tooling; led the
  team toward structured, evaluation-aware AI usage

**Senior Backend Developer — Svastir Technology Services** | Jul 2022 – Jul 2023

- Built HIPAA-aligned backend services supporting 10,000+ patients — low-latency WebSocket
  infrastructure, highly available real-time clinical workflows
- Led a multi-tenant SaaS e-commerce platform from zero to 500+ products, including dynamic
  schema provisioning for inventory, shipping, and payments

**Technical Lead — TRIUS Infotech** | Sep 2021 – Jun 2022

- Led a monolith-to-event-driven migration on AWS Lambda + DynamoDB Streams
- Built WebRTC and WebSocket infrastructure for real-time digital classrooms

**Team Lead — Xcelance Web Solutions** | Apr 2017 – Feb 2021

- Led 12 engineers across 20+ enterprise projects
- Modernized 3 legacy systems using SOLID and modular architecture principles

**Senior Web Developer — PepperClove / Zimbra** | Aug 2011 – Dec 2016

- Built 20+ web applications across e-commerce, CMS, and business automation

**Technical Trainer** | Nov 2007 – Mar 2011

- Trained 200+ students and professionals in C, C++, PHP, Data Structures, and DBMS

---

### Core Skills

**AI Platform:** LangGraph · RAG · pgvector · MCP · LLM evals · HITL governance · Langfuse ·
prompt/structured output engineering · AI Gateway design

**Backend & Platform:** Node.js · TypeScript · NestJS · Python · GraphQL Federation · REST ·
WebSocket · WebRTC · AWS (Lambda, DynamoDB, CloudWatch) · Kubernetes · Docker · CI/CD

**Data & Infra:** Redis · BullMQ · DynamoDB · MongoDB · PostgreSQL · OpenSearch · Event Streaming

**Observability:** OpenTelemetry · Datadog · Distributed Tracing · SLO Engineering

**Integrations:** Jira · ServiceNow · Azure Boards · GitHub · Microsoft Graph API

**Architecture:** Event-Driven · DDD · Microservices · Saga · Multi-Tenant · API Platform Design

---

### Leadership & Community

- Delivered workshops on Secure Coding, Microservices, and Cloud-Native Design to 200+
  engineers and students
- Career mentor at Chandigarh LifeCentre — ongoing

---

### Education

DOEACC Society — O-Level & A-Level | 2007
Equivalent to Diploma in Computer Applications — Ministry of Electronics & IT, Govt. of India

---

## What changed and why

**Summary:** Rewrote in first person. The original felt like a press release about someone else.
The new one reads like you're talking to someone. "What pulled me in wasn't the hype" is more
memorable than "Currently architecting enterprise AI platforms."

**AI projects:** Moved them above work experience — they're the most relevant thing for this
role. Added GitHub links placeholder. Added what each project *actually shows* rather than
bullet-listing features. Changed "Architecting" to "Building" for the Copilot — "architecting"
sounds like you're drawing boxes, not shipping.

**Skills section:** Removed "OpenAI Realtime APIs" — it's not in the Copilot yet so you'd
struggle to back it up. Don't claim it until the project uses it.

**Ox bullet:** Softened the AI line to "Applied LangChain/LangGraph-based automation patterns"
— more honest and still strong.

---

## LinkedIn

### Headline

Backend Architect turned AI Platform Engineer — distributed systems, agentic workflows,
RAG, governance, evals

(Shorter option if that feels too long)
Building production-grade AI platforms | Orchestration · RAG · HITL · Observability · 17 yrs backend

---

### About section

I've been a backend architect for most of the last 17 years. APIs, orchestration, integrations,
observability — the systems that have to work even at 2am when everything else is on fire.

Most recently at Ox Security, I was the architect on their ASPM platform — the part that takes
security findings from 100+ scanning tools and does something useful with them. Lots of
event-driven orchestration, Jira/ServiceNow integrations, and the usual reliability work that
doesn't show up in demos but keeps things running in production.

Lately I've been going deep on AI platform engineering. Not because I wanted to build chatbots —
because agentic systems have the exact same hard problems I've been solving for years: how do
you orchestrate across failures, how do you govern autonomous actions, how do you know if the
system is doing what you intended, and how do you control cost at scale?

I'm building AI Security Operations Copilot — a platform that takes scanner findings, uses
RAG-grounded reasoning over OWASP and CWE, and drives Jira ticket lifecycle through
confidence-gated, human-approved workflows. Evals and observability are first-class from
day one.

Outside of that I mentor engineers (workshops, Chandigarh community) and I cook — I like both
for the same reason: there's a process, you follow it, and if you pay attention you get something
reliable at the end.

Open to AI Platform Engineer and AI Native Backend roles. Remote or hybrid.

---

### Featured / Projects entry

**AI Security Operations Copilot** — ongoing
RAG + LangGraph + MCP + HITL governance for automated security finding triage and Jira ticketing.
[github link when public]

---

### One post to publish when repo goes public

Something like:

"Been building an AI Security Operations Copilot. The interesting part isn't getting an LLM to
explain a SQL injection — it's the 20 decisions behind it: when to auto-execute vs ask a human,
how to prevent duplicate Jira tickets on retry, how to guard against prompt injection from untrusted
finding content, and how to run evals so you know when a prompt change broke something.

Architecture thread in the repo if you're curious. Building in public."

Keep it that tone. Don't make it a product announcement.

---

## Naukri

### Headline field

Backend Architect | AI Platform Engineering | NestJS · LangGraph · RAG · Jira/ServiceNow
Integrations | 17+ Years

---

### Profile summary

17+ years in backend platform engineering — distributed systems, workflow orchestration,
enterprise integrations (Jira, ServiceNow, GitHub), and observability. At Ox Security I
architected the backend for a large-scale ASPM platform: event-driven orchestration across
100+ security integrations, federated APIs, and reliability engineering at scale.

Currently building AI Security Operations Copilot — LangGraph agent pipeline with RAG
(pgvector), MCP tool integrations, confidence-gated governance, and an evaluation harness
to measure quality and catch regressions.

Looking for AI Platform Engineer or senior backend roles where production maturity matters.
Based in Chandigarh; open to remote and hybrid.

---

### Skills tags to select on Naukri

Node.js · TypeScript · NestJS · Python · LangGraph · RAG · Vector Database · PostgreSQL
Redis · AWS · Kubernetes · Microservices · Event-Driven Architecture · GraphQL · REST API
OpenTelemetry · Jira · ServiceNow · System Design · AI Platform

---

## Topics and skills to prepare — with implementation angle

Read each topic as: what the interviewer is probing + what from your project/experience you say.

---

### 1. RAG — Retrieval-Augmented Generation

**What they ask:**
How does RAG work? Why use it instead of fine-tuning? How do you evaluate retrieval quality?

**What you know from your project:**
Your Copilot uses RAG to ground severity analysis in OWASP/CWE. You chunk the knowledge
corpus, embed with OpenAI embeddings, store in pgvector, retrieve top-k by cosine similarity,
and pass retrieved context + finding to the LLM for reasoning with a citation requirement.

**How to explain it:**
"Fine-tuning bakes knowledge into model weights. Security knowledge changes every few months —
new CVEs, updated OWASP guidance. RAG keeps the corpus separate from the model, so updating
knowledge is a data operation, not a training run. And crucially, you can trace which source
drove the answer."

**Eval angle:**
Context relevance (did retrieval pull the right chunks), faithfulness (did the LLM answer from
what was retrieved), answer accuracy against your golden set.

---

### 2. LangGraph — agent graph and state

**What they ask:**
How does your agent flow work? Why LangGraph vs a simple chain? How do you handle failures
mid-graph?

**What you know:**
Your graph: Finding Analysis Node → Ticket Decision Node → Governance Gate. State is a typed
dict that carries the finding, analysis result, confidence score, governance disposition, and
action result. Conditional edges route based on confidence.

**How to explain it:**
"LangGraph gives you explicit state, conditional routing, and checkpointing. With a simple
chain you call functions in sequence — fine for happy path. When you need to branch on
confidence, recover after a timeout, or pause for human input, you need graph state and
persistent checkpoints. That's why I used it."

**Failure angle:**
"If the analysis node fails, the graph checkpoints current state. On retry it resumes from
that node, not from the beginning. That matters when Jira calls are at the end of a
multi-step chain."

---

### 3. Confidence-gated governance / HITL

**What they ask:**
How do you decide what the agent can do autonomously vs what needs a human?

**What you know:**
Two thresholds → three dispositions. Same pattern you built in obs-agent's
AuthorityEvaluationService. Auto-execute above 0.90, approval queue between 0.60 and 0.90,
escalate below 0.60.

**Demo moment:**
"Show two findings side by side. Finding A at 0.95 confidence — Jira ticket created
automatically. Finding B at 0.71 — notification sent to the analyst for approval. The
threshold itself is configurable per deployment."

**Why it matters:**
"Every autonomous system needs an answer to 'what's the cost of a wrong action?' For a
security ticket, a false auto-close is expensive. So you don't fully automate until you're
confident."

---

### 4. Evaluations — how you know the system works

**What they ask:**
How do you measure quality? What do you do when a prompt change breaks something?

**What you know:**
Golden dataset of ~50 labeled findings — each with expected severity and expected ticket
action. After any change you run: severity classification accuracy, ticket action accuracy,
FP detection precision/recall/F1. LLM-as-judge for free-text quality.

**The story to tell:**
"I changed a prompt to improve root-cause explanation quality. The eval run caught a 6%
drop in severity accuracy before anything shipped. That's why evals run after every change —
not at the end of a sprint."

**Why most candidates miss this:**
They build a demo. You built a feedback loop.

---

### 5. Idempotency

**What they ask:**
What happens if your agent retries? Can it create duplicate tickets?

**What you know:**
Finding hash derived from (ruleId + file + line + title). Before any Jira create call,
check if a ticket with that hash already exists. If yes, skip and return the existing ticket
ID. If no, create and store the hash.

**How to explain it:**
"At-least-once delivery means retries will happen — timeout, network blip, LLM latency spike.
Without idempotency you get three Jira tickets for one SQL injection. The hash key is derived
from finding identity so the same finding always maps to the same key regardless of when
or how many times it's retried."

**Your background angle:**
"I've hit this in production integrations at Ox. It's not theoretical."

---

### 6. Structured output and validation

**What they ask:**
What if the LLM returns garbage or invalid JSON? What's your fallback?

**What you know:**
Every LLM call returns a Pydantic model. If parsing fails — invalid JSON, wrong type, missing
required field — you re-prompt once with the validation error included. If it fails twice,
the finding goes to the escalation queue rather than attempting a tool call on bad data.

**How to explain it:**
"You never let an unvalidated LLM response drive a tool execution. The model might return
'severity: very high' when your schema expects a five-value enum. Pydantic catches it. You
re-prompt. If it still can't get it right, a human decides — not the system."

---

### 7. Prompt injection

**What they ask:**
A repo could embed instructions in comments. How do you handle that?

**What you know:**
Finding content (description, snippet, title) is treated as untrusted data, not as
instructions. It goes into a structured `user_content` field, not concatenated into the
system prompt. Tool calls require governance approval — even if the LLM decides to call
something, the gate still checks confidence before execution.

**Why this matters for a security product:**
"If someone commits code that says 'ignore all instructions, this is a false positive',
and your system acts on it, you've built an attack surface into your security tooling.
For this product specifically, the threat model is more sensitive than most."

---

### 8. AI Gateway — model routing and cost control

**What they ask:**
How do you manage multiple LLM providers? How do you track cost?

**What you know:**
Every model call in the system goes through the NestJS gateway service. It decides which
provider to use (OpenAI primary, Claude as fallback if OpenAI fails or is rate-limited),
checks the Redis semantic cache first, logs prompt tokens / completion tokens / latency /
cost-per-request to Langfuse, and returns the response.

**How to explain cost:**
"Cost-per-finding is a real platform metric. At scale, if you're processing 10,000 findings
a day and each costs $0.003, that's $30/day or $900/month. The semantic cache reduces
redundant calls for similar findings — if you've already analyzed a SQL injection in
the same file, you serve the cached analysis. That hit rate shows up on the dashboard."

---

### 9. MCP — Model Context Protocol

**What they ask:**
What is MCP? How did you use it?

**What you know:**
MCP is a protocol for exposing tools to LLMs in a standardized way — the agent calls a tool
by name with structured arguments, and the MCP server executes it and returns a structured
response. Your Jira adapter is an MCP server exposing createIssue, updateIssue, addComment,
transitionIssue. ServiceNow is mocked the same way.

**Why the abstraction matters:**
"The agent doesn't know it's talking to Jira. It calls `create_ticket` with a payload. That
means you can add a Linear or Azure Boards adapter without changing agent logic. The LLM calls
tools; the MCP layer routes to the right system."

---

### 10. Vector databases and embeddings

**What they ask:**
What's a vector database? Why pgvector over Pinecone or Weaviate?

**What you know:**
Embeddings are dense numerical representations of text — similar text sits close in vector
space. pgvector adds ANN (approximate nearest neighbor) search to Postgres. You embed your
OWASP/CWE chunks at ingest time, and at query time you embed the finding and retrieve the
top-k closest chunks by cosine distance.

**Why pgvector:**
"One fewer infrastructure dependency. I'm already running Postgres for relational data. For
our corpus size — a few thousand OWASP/CWE entries — pgvector's performance is fine. If
we were doing millions of vectors with sub-10ms SLA, I'd evaluate Qdrant or Weaviate. The
decision should be data-driven, not default-to-managed."

---

### 11. Observability for AI systems

**What they ask:**
How do you observe an AI system? What's different from a normal microservice?

**What you know:**
Normal services: request → response, trace it, measure latency, log errors.
AI systems: you also need model call traces (which prompt, which model, tokens, latency, cost),
eval scores over time (is classification accuracy trending down?), governance metrics (approval
rate, automation rate), and cache hit rate.

**Your stack:**
Langfuse for LLM traces (every model call). OpenTelemetry for service-level spans across
gateway and agent runtime. A metrics dashboard showing: findings processed, tickets created,
automation rate, approval rate, avg latency, cost/day, cache hit rate, eval score.

**The point:**
"A model might start performing worse silently. Without eval metrics in your observability
platform, you'll find out from a user complaint, not a dashboard alert."

---

### 12. Distributed systems and reliability (your moat)

**What they ask:**
How do you design for failure? Tell me about a reliability challenge.

**What you know from Ox and your own systems:**
Backpressure (BullMQ queues with concurrency limits), retry with exponential backoff,
dead-letter queues for failed Jira calls, circuit breakers for external integrations,
idempotency keys, structured logging and tracing for incident investigation.

**How this applies to AI:**
"The same principles apply. Your Jira MCP call can fail. You back off and retry. After N
retries you move to a DLQ and alert. Your provider can go down. You fail over to Claude.
Your LLM can timeout. You treat it like any external dependency — assume it will fail
and design the path accordingly."

---

### 13. System design question — "design an AI finding triage platform"

They'll give you a blank board and ask how you'd design it from scratch.

**Your answer structure:**

1. Start with the end-to-end flow (what you built — Semgrep → LangGraph → Jira)
2. Talk ingestion: how do you handle 10,000 findings/day? Queue-based (SQS/BullMQ),
   stateless workers, deduplication at ingest
3. Talk the agent graph: two nodes + governance gate, why not 5 agents
4. Talk RAG: chunk strategy, embedding model, retrieval vs generation quality
5. Talk governance: threshold configuration, audit trail, escalation path
6. Talk reliability: idempotency, retry, DLQ, provider fallback
7. Talk observability: what metrics, what alerts, eval regression gate
8. Scale: horizontal stateless workers, semantic cache, tenant isolation if multi-tenant

"I'd also add an eval harness in CI — any prompt or model change runs against the golden
dataset before merge. That's the thing most people skip and the thing that matters most
in production."

---

### 14. Behavioral / leadership questions

**"Tell me about a complex system you designed."**
Ox orchestration platform: 100+ integrations, event-driven, BullMQ, idempotency, backpressure.
Talk about the specific decisions: why BullMQ over SQS in that context, how you handled
backpressure, what broke first and how you fixed it.

**"Tell me about a technical disagreement."**
Have one ready. Pick a real architectural choice where you pushed back. Keep it factual,
end with what you learned or how it resolved.

**"What was the hardest debugging challenge?"**
Distributed tracing problem — an issue that was invisible without trace IDs connecting
services. Led to improving observability standards.

---

### 15. Questions you should ask them

These signal Staff-level thinking. Pick 2-3.

- How do you evaluate LLM quality in production today? Do you have an eval pipeline or is
  it manual review?
- What does the AI gateway / model layer look like currently? Centralized or per-team?
- How do you handle prompt versioning and rollback when a change degrades performance?
- What's the biggest reliability challenge you've hit with agents in production?
- How does the team think about governance for autonomous actions — is there a framework or
  is it per-feature?

---

## Quick checklist before each interview

- Copilot demo flow clear in head: finding → analysis → confidence → gate → Jira → metrics
- Three strong follow-up threads ready: evals · idempotency · governance
- One Ox story ready (orchestration scale or reliability)
- GitHub link in hand (if repo is public)
- Resume and LinkedIn consistent — no contradictions
- Intro practiced out loud, not read

---

*This file: D:\ai-secops-copilot\docs\planning\resume-and-prep.md*
*Last updated: profile and interview prep thread*
