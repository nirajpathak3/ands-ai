# Decisions log & discussion

> Running record of what's decided, what's open, the reasoning framework, corrections to earlier
> analysis, and the 5-year thesis. Chronological-ish; newest context at top of each section.

---

## Decided
- **Build the substrate, not worker agents.** My moat is governed-automation infra (HITL, eval, audit,
  cost, orchestration), not a domain. Confirmed by research: trust — not model capability — is the
  universal bottleneck.
- **Project 1 = Forge** (multi-agent orchestration platform). Flagship + the factory I build others with.
- **Project 3 = Trainable domain-expert**, re-aimed at *auditable process + memory + verifiable method*
  (not "deeper than ChatGPT"). Built later, as a Forge tenant.
- **Two-layer plan:** Layer-1 IT base now (identity + factory) → Layer-2 governed vertical operators in
  underexploited audit-heavy domains, built via the factory.
- **OPS direction endorsed:** lean toward operations/operator products (governed autonomous operators),
  in IT now and non-IT later.
- **Portfolio kept separate** from the `ai-secops-copilot` repo (this folder).

## Open
- **Project 2** — undecided. Recommended: **agent-security verifier**. Alternatives: change-risk/release
  gate; triage plane (demo-only); oversight plane (too Forge-overlapping for a 2nd demo). See
  [`ROADMAP.md`](ROADMAP.md#project-2).
- **Which non-IT Layer-2 wedge first** — recommended life-sciences lab/research ops; special-ed/IEP and
  education-ops are alternates. Full future-vision docs to be written when we start Layer-2.

---

## The selection lens (use for any domain, esp. non-IT)
A domain is a good bet only when most hold:
1. **Agentic-necessity** — long-horizon, multi-actor, stateful, accountability required.
2. **Low domain AI/process maturity** — incumbents ship chatbots; nobody built the governed operator.
3. **Solo-accessible data/access** — demoable on synthetic/public data, no hard EHR/HIPAA/payer wall.
4. **Audit/trust intrinsic** — so my governance substrate is the moat, not overhead.
5. **A wedge** — personal affinity, design partner, or distribution.
Filter 1 and the moat are constant across domains; choose on 2–5.

## Corrections to earlier analysis (and to the external take I was asked to verify)
- Agent-security is **consolidating, not "wide open"** (Promptfoo→OpenAI, Lakera→Check Point). Re-scope
  to the agentic gap. (Prior backlog had Crowd 5/5.)
- Triage/correlation is a **commodity ASPM feature** (incl. Ox). Great demo, weak product. (Prior had
  Crowd 4 / Moat 5.)
- **AI Incident Commander is NOT "early"** — it's one of the most crowded agentic categories
  (PagerDuty/Resolve/Cleric/Rootly/incident.io). Integration-heavy, low real reuse, hard to demo
  offline, overlaps Forge → **dropped as a Project-2 candidate.** (The external doc ranked it #1/P2 and
  claimed 90% reuse — both wrong.)
- **Change-risk agent is not "very novel"** (Koalr/DeployWhisper/PRism exist) but is a reasonable P2
  alternative.
- **Reuse %s in the external doc were inflated** (90–95% across the board); realistic numbers are in the
  backlog.
- **Neuroscience "cognitive architecture" pivot = trap:** brain-region→agent mapping is a decades-old
  metaphor; consumer mental-health is crowded **and** newly regulated (Vermont Act 156; EU AI Act).
  Keep neuroscience as ONE Project-3 skill pack, not a product identity.
- **Non-IT verticals all have funded vendors** — but most ship shallow tools; the governed-operator gap
  is real. The external doc's own thesis ("build managers, not workers") **contradicted** its later
  push toward domain worker-agents (construction/healthcare/neuroscience). Trust the thesis half.
- **Career-identity point (valid):** avoid being filed as "security engineer using AI." Fix via
  *horizontal/platform framing* (Forge, oversight, agent security, release-eng) and a non-IT Layer-2
  operator — NOT by building in a random vertical with no edge.

---

## 5-year thesis (condensed)
- **Trajectory:** assist (now) → coordinate/approve (~18mo) → execute/audit (~3yr) → AI supervises AI,
  humans supervise exceptions (~5yr). The org inverts: many agents, few human verifiers.
- **Most exposed roles:** L1 support, coordinators, first-draft analysts, ticket-pushers, offshore
  back-office, junior devs. **Least exposed / compounding:** builders of the substrate agents run on —
  orchestration, governance, eval, observability, security, identity. (= platform engineer.)
- **Durable, commodity-proof categories (ranked):** oversight/verifier/governance plane → agent security
  → agent identity/authz → governed orchestration/supervisors → eval+observability (already crowded) →
  trust/audit infra (cross-cutting).
- **Commoditizes:** chat wrappers, prompt-craft, simple RAG, single-agent copilots, thin vertical
  wrappers, framework-primitive wars, "find an empty vertical."
- **Endures:** as autonomy rises, the bottleneck shifts permanently from "can the model do it?" to "can
  I prove it did it right, safely, and who's accountable?" — my home turf.
- **One-liner:** *"Models are getting commoditized; trust isn't. I build the layer that makes autonomous
  agents safe to deploy — governance, eval, audit, identity, security — and the factory that ships it."*
