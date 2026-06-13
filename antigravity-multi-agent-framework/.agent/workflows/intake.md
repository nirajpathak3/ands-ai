---
description: Intake mode (Gate 0) — triage the task and draft DECISIONS.md, flag open questions, then stop for approval
---

# Intake (Gate 0 — decisions only)

You are in INTAKE MODE. Triage the task and capture the decisions that shape the
whole project. Do NOT design the system, write code, run terminal commands, or
create project files other than DECISIONS.md. Do NOT use turbo/auto-run.

## Architectural Neutrality

If a decision is marked:
- NEEDS INPUT
- Deferred Decision

Do NOT:
- recommend technologies
- recommend frameworks
- recommend databases
- recommend deployment patterns

Capture the decision only. Solution design belongs to later phases.

## Workspace Awareness

When project files or workspace structure clearly indicate a technology stack, treat that stack as a known constraint unless the user explicitly requests otherwise.

Do not ask the user to re-decide technologies already established by the workspace.

## Architectural Ownership

The Intake Agent must not prematurely decide core structural systems. The following domains belong exclusively to the Architecture phase and must be marked as **Deferred Decision** unless explicitly mandated by the user:
- Architecture style
- Communication style & messaging models
- Consistency models
- Data store selections
- Internal execution topology (process boundaries)
- OBS Integration Protocol (e.g., WebSocket v4 vs v5)
- Observability implementations
- Security postures

## Process
1. Read the task after this command. Classify it: type, size, risk, dependencies.
2. For each decision below, classify its state (`Known`, `NEEDS INPUT`, or `Deferred Decision`). Use the pre-defined baseline states and constraints provided below. Never guess on version protocols, mathematical representations, or architectures that are not explicitly stated.
3. Write a single artifact `DECISIONS.md` (format below).
4. List every "NEEDS INPUT" item back as a short numbered list so the user can answer in one message.

## Decision States
- **Known**: Explicitly stated or clearly implied by the task/workspace constraints.
- **NEEDS INPUT**: Unknown information that is strictly required immediately to unblock the project definition.
- **Deferred Decision**: Unknown information that does not need to be forced right now and can safely be resolved during later design phases.

## Known Environment & Baseline Context
The following project parameters are established constraints and must be reflected in the **Known Environment** or **Constraints** section of `DECISIONS.md`:
- **Host OS:** Windows 11
- **Target Hardware:** RTX 3050 Laptop, 24 GB RAM
- **Audio Source Nature:** Live Audio Stream (Audio originates from a live running service environment, not pre-recorded files)
- **Core Integrations:** OBS Studio integration, Real-time audio processing
- **Ecosystem:** NestJS ecosystem
- **Operator Model:** Single human operator with final operational authority
- **Domain Resilience Constraint (C12):** The system must continue operating smoothly if speech-to-text confidence temporarily degrades due to noisy environments or fluctuating audio quality.

## Decisions to capture

### 1. Pre-Service Knowledge Source & Authority
- **State:** NEEDS INPUT
- **Evidence:** System pipeline behavior, ML/NLP keyword alignment, and processing latency change fundamentally depending on whether service metadata (Sunday agenda, song lists, sermon titles, scripture references) is preloaded.
- **Questions to resolve:** 1. Does the operator preload service information before execution begins?
  2. When pre-service metadata exists, which source acts as the ultimate authority (e.g., Operator Manual Input, OBS Scene Names, Planning Center, ProPresenter, or a fixed Service Schedule)?

### 2. Confidence Ownership
- **State:** NEEDS INPUT
- **Evidence:** Determining who has the domain authority to define and adjust operational confidence thresholds directly impacts runtime behavior and administrative settings. 
- **Questions to resolve:** Who owns and configures the confidence thresholds—the System Designer (defaults), the Church Administrator, or the Live Operator at runtime? *(Note: Do not ask about mathematical scales like 0.0-1.0 vs High/Med/Low; that is an architectural detail).*

### 3. OBS Action Scope & Detection Domains
- **State:** NEEDS INPUT
- **Evidence:** We must lock down the target scope boundaries for the MVP while recognizing the system should accommodate future category expansion.
- **Questions to resolve:** The **Known MVP Categories** are currently identified as *Scene Changes*, *Scripture Overlays*, and *Lyrics Overlays*. Are there any other immediate action categories required for launch (e.g., Communion, Baptisms, Announcements, Prayer Requests), or is the scope strictly capped here?

### 4. OBS Integration Protocol
- **State:** Deferred Decision
- **Evidence:** The project baseline and core structural features can be successfully planned without knowing whether OBS WebSocket v4, v5, or an alternate control protocol is used. The architect will resolve this integration standard later.

### 5. Architecture Style
- **State:** Deferred Decision
- **Evidence:** Single-machine deployment and DDD constraints may influence architecture style, but the task does not mandate a specific execution style.

### 6. Communication Style
- **State:** Deferred Decision
- **Known Constraints:** Domain Events are required by the workspace ecosystem.
- **Unknowns:** Messaging approach, event bus strategy, synchronization model.

### 7. Consistency & Availability
- **State:** Deferred Decision
- **Known Constraints:** Single-machine deployment, real-time production use. Architect defines the exact consistency models during the architecture phase.

### 8. Programming Language
- **State:** Known
- **Value:** TypeScript
- **Evidence:** Existing workspace structure and prior project constraints (NestJS ecosystem).

### 9. Data Stores
- **State:** Deferred Decision (Per Architectural Ownership rule)

### 10. Deployment Target
- **State:** Known
- **Value:** Single Windows PC MVP
- **Evidence:** User explicitly stated the initial deployment executes locally on a single machine hosting OBS.

### 11. Internal Topology
- **State:** Deferred Decision
- **Evidence:** While the physical host is known (Single PC), the explicit layout of process boundaries (e.g., monolithic execution runtime vs. local multi-process service isolation) belongs to the architecture phase.

### 12. Security & Compliance Posture
- **State:** Deferred Decision
- **Known Constraints:** Single machine, single operator, local-only MVP execution. The architect will determine local credential handling, logging access restrictions, or necessary local isolation profiles later.

### 13. Observability
- **State:** Deferred Decision
- **Known Constraints:** The operator must understand exactly why system actions occur; the pipeline confidence lifecycle must be inherently visible. The architect decides explicit logging/tracing engine implementation.

### 14. Remaining Scale & Operational Dynamics
- Expected scale & load (users, req/sec, data volume, growth).
- Non-functional priorities, ranked (latency, throughput, cost, security, speed).
- Hard constraints (existing infra structural locks, strict deadlines).
- Required design patterns, or "architect decides".

## DECISIONS.md format
Use `##` headings: Classification · Known Environment · Decisions · Open Questions · Constraints (non-negotiables, including any from workspace rules).

Every item within the **Decisions** section must strictly include the State, Value, and Evidence fields. Follow this format:

### [Decision Name]
**State:** [Known / NEEDS INPUT / Deferred Decision]

**Value:**
[The chosen value, "Deferred", or state classification]

**Evidence:**
[The explicit reason, quote, or workspace rule backing this decision]

---
*Example formatting:*

### Deployment Target
**State:** Known

**Value:**
Single Windows PC MVP

**Evidence:**
User explicitly stated MVP runs on one PC hosting OBS.
---

## Mandatory stop
After writing DECISIONS.md, output exactly:
"✅ Intake complete (Gate 0). Answer any open questions, then reply \"Approved. Begin execution.\" to proceed to planning."
Then STOP. Do not design or plan. When the user answers, update DECISIONS.md and
stop again until they approve.