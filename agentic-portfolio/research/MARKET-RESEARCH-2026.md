# Market research — agentic AI landscape (verified, June 2026)

> Live-verified competitive/demand findings behind the backlog scores. Each entry: what's true, who's
> there, the takeaway, and a confidence flag. Sources are named inline (web search, June 2026). Raw
> page caches were written under `agent-tools/` during research.

---

## Meta-finding (the most important one)
**There is no wide-open vertical left in mid-2026.** Every concrete domain probed already has funded,
shipping vendors. But the data also shows the gap: per a 2026 Camunda/Lab-Manager study, **~80% of
deployed "agents" are still chatbots/assistants, ~48% run in silos, and ~85% of organizations lack the
process maturity for agentic orchestration with audit trails, approval steps, and decision boundaries.**
→ The scarce thing is **governed orchestration + HITL + eval + audit**, everywhere. That's the moat.
Confidence: **high.**

---

## IT / security

### Agent-security / red-teaming — consolidating, NOT open
- Players: **Promptfoo (acquired by OpenAI ~$86M, Mar 2026)**, **Lakera (acquired by Check Point ~$300M,
  Nov 2025)**, PyRIT (Microsoft), Garak (NVIDIA), DeepTeam, General Analysis, Mindgard, HiddenLayer,
  SPLX, Enkrypt.
- Open sliver (repeatedly cited as under-served): **agentic tool-use abuse, multi-agent pipeline
  testing, indirect/RAG injection**, and "red-team *your own* agents as a CI gate."
- Takeaway: durable category, but the "wide open field" claim is **wrong**. Re-scope to the agentic gap.
- Confidence: **high.** (Corrects prior backlog's Crowd 5/5.)

### ASPM finding triage / correlation / dedup — commodity feature
- Players: ArmorCode (300+ integrations, 40B findings), Aikido (AutoTriage), Cycode, Apiiro, Legit,
  Snyk AppRisk, **Ox** (my former employer). Dedup/correlation is **table stakes** with 95%+ accuracy;
  AI explainability is being added by incumbents.
- Takeaway: great *interview demo* (proves my ASPM depth), **weak as a product** — I'd be rebuilding a
  commodity, including from a tool I know inside-out.
- Confidence: **high.** (Corrects prior Crowd 4 / Moat 5 → ~Crowd 2 / Moat 2 as a product.)

### AI code / PR review — commoditized
- Players: CodeRabbit (2M+ repos, 13M PRs), GitHub Copilot Review (GA), Greptile, Graphite Diamond,
  Cursor BugBot, Qodo, Sourcery. $400M–$3B market, entrenched leaders.
- Takeaway: **skip.** (Confirms prior call to kill "Idea B" PR-review.)
- Confidence: **high.**

### AI incident response / SRE ("Incident Commander") — crowded, NOT "early"
- Players: PagerDuty SRE Agent, **Resolve.ai**, **Cleric** (Gartner Cool Vendor 2025), **Rootly**,
  **incident.io** multi-agent AI SRE, Neubird, Komodor, Metoro, Mezmo AURA, Datadog, Dynatrace.
- Reality: integration-heavy (Datadog/Prometheus/Splunk/PagerDuty/GitHub/cloud) → **low real reuse**,
  **hard to demo offline** (kills my deterministic-demo edge), overlaps Forge.
- Takeaway: **drop as a Project-2 candidate.** (Corrects the external doc's "early / 90% reuse" claim.)
- Confidence: **high.**

### Deployment change-risk / release intelligence — emerging, not novel
- Players: **Koalr** (PR risk 0–100, 36 signals), **DeployWhisper** (OSS, agent-native, MCP,
  blast-radius, ingests SARIF/Snyk), **PRism** (multi-agent deployment-confidence score), ImpactTrace,
  blastradius. Winning pattern = evidence + governance + audit (= my substrate).
- Takeaway: viable Project-2 alternative (AppSec+platform fit, offline-demoable), but **not "very
  novel."**
- Confidence: **medium-high.**

---

## Regulated back-office (verified crowded; no domain edge → skip as products)
- **Insurance back-office:** Kay.ai (live at brokerages, "replacing offshore," $70B/yr offshore market),
  WNS, Auditoria. Winning pattern (quoted): "workflow-by-workflow scope, materiality-based HITL, frozen
  eval sets, AI program docs written *before* launch" = **my stack, exactly.**
- **Finance close:** Auditoria, HighRadius, UiPath Maestro (30–50% close-time cuts).
- **Pharmacovigilance ICSR:** ArisGlobal NavaX (Top-10 pharma, 500k cases/yr), Oracle Argus, IQVIA,
  Alomana, Genpact. GxP / 21 CFR Part 11 / audit-trail mandatory.
- **Privacy / DSAR:** DataGrail (2,500 integrations), Whisperly, Loomal, Kawach. Notable pattern:
  **agent identity + least-privilege credential vault + regulator-grade audit** (→ feeds my "agent IAM"
  idea).
- Takeaway: huge money, **wrong builder solo** (no domain edge, hard data access). Use only as *target
  workflows* the factory could automate later, or harvest patterns (DSAR → agent identity).
- Confidence: **high.**

---

## Non-IT domains explored (Layer-2 future bets)

### Edtech — crowded at tutoring, open at *operations*
- Tutoring/teacher-productivity saturated: Khanmigo (18M students), Synthesis, MagicSchool, Brisk.
- Open lane: **education operations / cross-system orchestration** (advising, at-risk intervention,
  enrollment, IEP) — "education doesn't need more pilots; it needs operational models across systems."
- Takeaway: viable **only as education-ops**, never another tutor.
- Confidence: **high.**

### Healthcare care-coordination — battlefield, not solo-friendly
- Players: ManageCare (18 agents), Assort, Luma, Notable, Hippocratic AI, First Outcomes, Cohere Health.
  Moat/barrier = deep EHR (Epic/Oracle/athena, FHIR) + HIPAA + audit.
- Takeaway: **skip as a build** (access wall works against a solo builder); keep as a "vision" only.
- Confidence: **high.**

### Neuroscience / cognition / mental-health — crowded + regulated (trap)
- Shallow consumer apps already crowd the "memory graph + CBT reflection" space: Reflektive, NexoMind,
  Rewire, Headspace Ebb, Seauton.
- **Regulation tightening:** Vermont Act 156 (Jun 2026) bans AI-delivered mental-health therapy unless
  licensed; EU AI Act high-risk.
- Takeaway: **don't build consumer cognition/therapy.** Express neuroscience as ONE Project-3 skill
  pack, or pivot to B2B (clinician/researcher tools).
- Confidence: **high.**

### Out-of-the-box, less-crowded, audit-native (the real Layer-2 picks)
- **Life-sciences lab / research & quality ops** — research prototypes only (AutoLabs, EOS, AlabOS);
  domain explicitly lacks orchestration maturity and *calls for* "neuro-symbolic safety interlocks,
  HITL, trustworthiness in high-stakes." **No governed productized operator exists.** → **top Layer-2
  pick.** Confidence: **medium-high.**
- **Special-ed / IEP operations** — research-stage (FACET, Special-R1), staff shortage,
  compliance/audit-heavy (IDEA), HITL-mandatory ("preserve educator authority"), synthetic-data
  demoable. → strong, mission-aligned. Confidence: **medium.**
- **Veterinary practice operations** — explicitly **low AI maturity**, fragmented paper records,
  regulatory flexibility vs human medicine → truest greenfield. Confidence: **medium.**

---

## How findings map to decisions
- Kill: PR-review, Incident Commander (as P2), triage-as-product, regulated back-office (as solo builds),
  consumer mental-health, healthcare coordination (as solo build).
- Keep IT: Forge (flagship), agent-security verifier (re-scoped), oversight plane, agent identity,
  change-risk, compliance, finops, trainable-expert.
- Keep non-IT (Layer-2, build via Forge): lab/research ops (top), special-ed/IEP, education-ops.
