# Backlog #4 (NEW) — Agent oversight & governance control plane ("mission control" for agents)

> Productize the substrate itself: a horizontal **runtime governance + human-oversight + eval-gate +
> audit** plane that any team's agents plug into — the part Langfuse/Braintrust/Arize leave out.
> Peers do *eval + observability*; the **governance + oversight + HITL-by-materiality + audit/accountability**
> plane is genuinely underbuilt. One-line: *the layer that makes autonomous agents safe to deploy —
> route by materiality, gate on eval, audit every action, bound cost — for agents you didn't build.*
>
> Rationale (2026 verification): every vertical now has shipping vendors; the *bottleneck is trust, not
> model capability*. The winning deployments share one pattern — materiality-based HITL, frozen eval
> sets, audit written before launch. That pattern is this product, and ~75% of it already exists in
> `ai-secops-copilot`.

---

## Problem
Teams are shipping agents with tool access and real authority, but the trust layer is bolted on late or
not at all. There is no neutral control plane that sits *in front of* an agent's decisions and answers:
should this action auto-execute, go to a human, or escalate? did it pass the eval gate? what did it do
and why, in an audit a regulator can read? what did it cost? Eval/observability vendors show you what
happened; nobody owns the *governance decision and the accountability record* across heterogeneous
agents.

## Why agentic (not a chatbot)
It governs multi-step, stateful, tool-using agents at runtime: intercept proposed action → score
confidence/risk → confidence-gated disposition (auto / human-approval / escalate) → deterministic
policy override → durable HITL interrupt/resume → append-only audit with machine `reasonCode` → cost
and drift guards. It is decisioning *about* other agents' decisions — a verifier/oversight loop, not Q&A.

## Target user / buyer
AI-platform / eng-leadership teams who must ship agentic features *safely*; later, risk/compliance
owners of "agent programs." Buyer is measured on incident rate, audit defensibility, and cost — exactly
the failure modes generic agent stacks ignore.

## What's new vs. my secops stack (keeps it a distinct product)
The copilot governs *security findings*; this generalizes the governance kernel into a **domain-agnostic
oversight plane** any agent calls. Net-new is small and high-leverage:
- A thin **SDK/sidecar/gateway** so an external agent can submit a proposed action for a disposition.
- A **materiality model** (risk × blast-radius → which decisions need a human) on top of confidence.
- An **oversight UX**: a queue of pending high-stakes decisions with the full "why" for one-click approve.

## Why my stack fits (reuse ~75%)
- **Confidence-gated governance + reasonCode** → the core disposition engine, verbatim (`governance.py`).
- **Durable HITL (interrupt/checkpoint/resume)** → human approval across requests (`graph/runner.py`).
- **Policy-as-code (first-match override)** → deterministic guardrails per tenant (`policy.py`).
- **Append-only audit + CQRS read models** → the accountability record + dashboards (`AuditRecord`).
- **Eval harness + LLM-as-judge + regression gate** → "did this action pass the eval gate?" (`evals/`).
- **AI Gateway** → cost/latency/token guards for governed calls (`gateway/`).
- **Multi-tenancy + auth + rate limit + observability** → run it as a real control plane.
- New: action-submission SDK/protocol, materiality scoring, oversight queue UI.

## Architecture sketch
```mermaid
flowchart LR
    EXT[External agent\n(any framework)] -->|propose action| CP[Oversight control plane]
    CP --> GOV[confidence + materiality gate]
    GOV --> POL[policy override]
    POL -->|auto| ALLOW[allow + audit]
    POL -->|approval band| Q[oversight queue\nHITL approve/reject]
    POL -->|escalate| ESC[escalate + audit]
    Q -->|approved| ALLOW
    CP --> EVAL[eval gate / drift check]
    CP --> GW[cost/latency guard]
    ALLOW & ESC --> LOG[(append-only audit\nreasonCode)]
    LOG --> DASH[oversight dashboard + analytics]
```
Build the kernel **via Forge** and expose it as a standalone plane: a `decide(action_request) ->
disposition` API plus a sidecar adapter. The same engine that governs Forge's own workers governs
third-party agents.

## v1 scope — DEMOABLE (high reuse, minimal new build)
A tiny SDK lets a sample external agent (e.g. a "refund agent" or a shell-running ops agent) submit
proposed actions. Show: one low-risk action auto-allowed (audited), one high-materiality action routed
to the oversight queue → one-click approve (HITL), one action **blocked by a policy rule** and one
**failed by the eval/drift gate** — each with a full citation-backed "why" and a `reasonCode`. Dashboard:
disposition mix, cost, pending-oversight queue, audit trail.

## Demo script + "wow"
1. Point the plane at a *different* sample agent than the copilot — proves it's horizontal.
2. Agent proposes a $5 refund → auto-allowed; proposes a $5,000 refund → **materiality → human queue**.
3. Approve in one click (durable HITL); open any decision → full reasoning, policy hits, reasonCode.
4. A drifted action **fails the eval gate** and is held — "the model changed; the gate caught it."
5. Close: *"models get commoditized; this is the trust layer that doesn't — and it governs agents I
   didn't even build."*

## Success metric
Every governed action carries an audited, reason-coded disposition; high-materiality actions never
auto-execute; one demonstrated eval-gate catch on a drifted action; integration in < N lines of SDK.

## 5-year evolution
Oversight plane → the verifier/accountability layer for agent-to-agent systems → where the scarce human
role (oversight of fewer, higher-stakes decisions) actually lives. This is the single most
commodity-proof category in the thesis: as autonomy rises, this plane's value rises with it.

## Key risk
"Isn't this just Forge's middle layer?" — and it partly is. Mitigation: ship it as a **standalone plane
with an SDK that governs external agents**, and decide deliberately whether it's a separate product or
Forge's commercial wedge. Second risk: eval/observability incumbents move up into governance —
counter with HITL + policy + audit/accountability depth they lack today.
