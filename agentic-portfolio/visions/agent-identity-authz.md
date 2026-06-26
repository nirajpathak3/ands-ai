# Backlog #5 (NEW) — Agent identity & authorization control plane ("IAM for agents")

> The deepest, most platform-engineer-proof bet in the portfolio: *who is this agent, what is it allowed
> to call, with whose authority, scoped how, and audited how?* Peers: early movers around scoped
> credentials and MCP/tool authz, but **no default exists**. One-line: *least-privilege identity,
> delegated authority, and tamper-evident audit for autonomous agents and their tool calls.*
>
> Rationale (2026 verification): named as a durable category in the thesis, and validated obliquely by
> privacy/DSAR agents (DataGrail/Loomal) whose own pitch centers on "agent identity holds every
> credential, least-privilege enforced by architecture, regulator-grade audit." That pattern wants to be
> a *horizontal primitive*, not re-built per vertical.

---

## Problem
Agents are getting credentials and tool access faster than anyone is governing *which* credentials,
*whose* authority they act under, and *what* they may do with them. Today this is hardcoded API keys in
env vars, broad scopes, and no record of "agent X used principal Y's authority to call tool Z." As
agents gain autonomy and chain tools (incl. MCP), this becomes the top unsolved security/identity gap:
over-privilege, confused-deputy, credential exfiltration, and no accountability chain.

## Why agentic (not a chatbot)
It mediates an agent's live tool/credential use: resolve agent identity → resolve delegated principal →
evaluate least-privilege policy for the requested tool+scope → issue short-lived scoped credential or
deny → record a tamper-evident authority/usage event. Stateful, decisioning, enforced at runtime in the
agent's action loop — pure control-plane logic, not conversation.

## Target user / buyer
AI-platform + security/identity teams running fleets of agents; the same buyer as Forge and the
oversight plane. Buyer is measured on least-privilege posture, incident blast-radius, and audit.

## What's new vs. my secops stack
This is the most net-new conceptually (reuse ~40% of code, but ~100% conceptual fit with a platform
engineer's core skills: authz, multi-tenancy, distributed systems, secrets). The substrate I reuse is
the *governance/audit/policy/multi-tenancy* scaffolding; the new core is an **agent identity model +
delegated-authority + scoped-credential broker.**

## Why my stack fits (reuse ~40%, fit ~100%)
- **Multi-tenant isolation + auth (API key/JWT → Principal)** → extend Principal to agent identities
  and delegation chains (`auth.py`, `tenancy.py`).
- **Policy-as-code (first-match)** → least-privilege tool/scope rules (`policy.py`).
- **Append-only audit + reasonCode** → tamper-evident authority/usage record (`AuditRecord`).
- **AI Gateway single-egress pattern** → the model for a single, mediated tool/credential egress.
- **Observability + rate limiting** → per-agent usage limits and traces.
- New: agent identity registry, delegation/consent model, short-lived scoped-credential broker, tool
  authz policy language, "agent IAM" UI.

## Architecture sketch
```mermaid
flowchart LR
    AG[Agent\n(identity + delegated principal)] -->|request tool+scope| BR[Authz broker]
    BR --> ID[identity + delegation resolve]
    BR --> POL[least-privilege policy]
    POL -->|allow| CRED[short-lived scoped credential]
    POL -->|deny| DENY[deny + reason]
    CRED --> TOOL[tool / MCP server]
    CRED & DENY --> LOG[(tamper-evident\nauthority + usage audit)]
    LOG --> DASH[agent-IAM posture dashboard]
```
The broker sits in the agent's tool-call path (mirrors the AI Gateway's single-egress idea, applied to
*authority* instead of *model calls*).

## v1 scope — DEMOABLE
Register two agents with different scopes; a "researcher" agent may call `web_search` + `rag_search`
only, an "ops" agent may call `write_file` within a path. Show: a least-privilege **allow** with a
short-lived scoped token; a **deny** when the researcher tries `write_file` (confused-deputy blocked);
a full **authority audit** ("agent R acted under principal P, was issued scope S for 60s"). Demo a
revocation. Optionally wire to a real MCP server to show tool-level scoping.

## Demo script + "wow"
1. Two agents, two scopes, one policy. The ops agent writes a file (allowed, short-lived token).
2. The researcher agent tries the same write → **denied, audited, reason-coded** (least privilege).
3. Revoke the ops agent's scope live → next call denied — "credentials are short-lived and revocable."
4. Open the authority audit: the full delegation chain. *"This is IAM, but for agents and their tools —
   the accountability layer that's missing when an agent acts under a human's authority."*

## Success metric
Every tool call carries an identity + delegation + scope + audit record; over-privileged calls are
denied by default; credentials are short-lived and revocable; zero standing broad-scope secrets in the
demo.

## 5-year evolution
Agent IAM → the identity/authz/accountability backbone for agent-to-agent systems (agents authenticating
to *each other*, delegated chains, consent). Among the most durable and least commoditizable categories;
a base model never solves authority and accountability.

## Key risk
Hardest to demo flashily and lowest immediate reuse — it's an infrastructure bet, not a quick win.
Mitigation: scope v1 tiny (two agents, one policy, MCP tool-scoping), lean on the platform-engineer
narrative, and position it as the deep moat *behind* Forge + the oversight plane rather than a
standalone fortnight demo. Build it later via the factory once the flagship lands.
