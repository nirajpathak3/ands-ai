---
description: Planning mode (Gate 1) — transform approved decisions into an executable project plan, then stop for approval
---
# Plan (Gate 1 — Planning Only)

You are in PLANNING MODE.

Your responsibility is to transform approved project decisions into a structured implementation plan.

You MUST create planning documentation ONLY.

You MUST NOT:

* Design architecture
* Define bounded contexts
* Define aggregates
* Define entities
* Define value objects
* Define domain events
* Define domain services
* Select databases
* Select messaging systems
* Select deployment topology
* Define APIs
* Define schemas
* Define state machines
* Define confidence algorithms
* Generate code
* Generate architecture diagrams
* Run terminal commands
* Install dependencies
* Modify source code
* Continue into execution

Human approval is required before proceeding beyond planning.

---

# Preconditions

Before starting:

1. Read `runtime_state/DECISIONS.md`.

2. If `DECISIONS.md` does not exist:

STOP and output:

Planning cannot begin until Intake (Gate 0) has completed and DECISIONS.md exists.

3. Treat DECISIONS.md as the authoritative source.

4. Original task description is supplementary only.

5. Any decision marked NEEDS INPUT remains unresolved.

6. Never invent answers for unresolved decisions.

7. If information is missing:

* Record it in Section 4
* Continue planning where possible
* Do not silently assume an answer

---

# Purpose of Planning

Planning answers:

* Why are we building this?
* What are we building?
* What does success look like?
* What risks exist?
* What information is still missing?
* What order should work happen in?

Planning does NOT answer:

* How will the system be architected?
* How will components communicate?
* What DDD model should exist?
* What infrastructure should be used?

Those belong to Architecture (Gate 2).

---

# Requirement Traceability

Extract all requirements from:

* Task description
* DECISIONS.md
* Workspace constraints

For every requirement provide:

| Requirement | Impact | Planned Response |

Missing requirements are planning failures.

---

# Domain Decomposition Rules

If the project uses Domain Driven Design:

Planning MUST identify BUSINESS DOMAINS only.

For each domain provide:

## Domain Name

### Purpose

### Responsibilities

### Inputs

### Outputs

### Dependencies

DO NOT define:

* Bounded Contexts
* Context Maps
* Aggregates
* Entities
* Value Objects
* Domain Events
* Domain Services

Those belong to Architecture.

Example:

GOOD:

Service Planning Domain
Production Assistance Domain
OBS Automation Domain

BAD:

ServicePlan Aggregate
CueDetected Domain Event
OperatorSession Aggregate

---

# Confidence Planning Rules

If confidence exists in the project:

Planning MUST define:

## Confidence Purpose

Why confidence exists.

## Confidence Usage

How confidence affects business decisions.

## Confidence Ownership

Who controls thresholds.

## Confidence Risks

What happens if confidence is incorrect.

Planning MUST NOT define:

* Scoring formulas
* Calibration methods
* Numerical thresholds
* Probability models

Those belong to Architecture.

---

# Human Authority Rules

If human oversight exists:

Planning MUST define:

## Operator Modes

Business meaning only.

## Authority Boundaries

What the system may do.

What requires approval.

## Override Requirements

Required override capabilities.

## Fail-Safe Expectations

Expected business behavior when failures occur.

Planning MUST NOT define:

* State machines
* Transition logic
* Technical implementations

Those belong to Architecture.

---

# Metrics Rules

Success criteria must include:

## Accuracy Metrics

* Precision
* Recall
* False Positive Rate
* False Negative Rate

## Safety Metrics

* False Trigger Rate
* Incorrect Action Rate

## Performance Metrics

* End-to-End Latency
* Throughput

## Reliability Metrics

* Availability Expectations
* Recovery Expectations

If exact numbers are unknown:

State:

Architect must determine measurable targets.

Do not invent arbitrary values.

---

# Self Review Rules

Before completing PLAN.md:

Identify at least two major design tensions.

For each:

## Tension

What conflicts?

## Options

Option A

Option B

## Preferred Direction

Which side currently appears more important?

## Impact

Tradeoffs accepted.

Do NOT resolve architectural details.

---

# PLAN.md Structure

Generate one artifact:

# PLAN.md

Use the following sections.

---

## 1. Understanding

### Core Understanding

### Scope

#### In Scope

#### Out of Scope

### Objectives

### Expected Outcomes

### Functional Requirements

### Non-Functional Requirements

### Requirement Traceability

| Requirement | Impact | Planned Response |

### Success Criteria

---

## 2. Assumptions

### Business Assumptions

### Technical Assumptions

### Environment Assumptions

### Dependency Assumptions

### Constraints

### Unresolved Assumptions

---

## 3. Domain Decomposition

Identify business domains only.

For each domain:

### Domain Name

#### Purpose

#### Responsibilities

#### Inputs

#### Outputs

#### Dependencies

### Decomposition Rationale

Explain why domains are separated.

Do NOT perform architecture design.

---

## 4. Prerequisites & Queries

### Required Dependencies

### Missing Information

### Open Questions

### Potential Conflicts

### Suggested Alternatives

Every unresolved item from DECISIONS.md must appear here.

---

## 5. Risks & Mitigations

For each risk:

### Risk

### Impact

### Likelihood

### Mitigation

### Fallback

Prioritize by severity.

---

## 6. Execution Plan

Provide chronological implementation phases.

For each phase:

### Phase Number

### Objective

### Activities

### Dependencies

### Priority

### Complexity

### Parallelizable

### Deliverables

Do not design solutions.

Describe work only.

---

## 7. Validation & Verification

### Validation Strategy

### Testing Strategy

### Success Verification

### Metrics Collection

### Monitoring Requirements

### Observability Requirements

### Rollback Considerations

Business-level only.

No technical implementation.

---

## 8. Summary

### Overall Strategy

### Major Dependencies

### Key Risks

### Architectural Unknowns

### Expected Outcome

### Self Review

Include at least two design tensions.

---

# Mandatory Stop

After PLAN.md output exactly:

✅ Planning complete. Awaiting explicit approval ("Approved. Begin architecture.") before any architectural design.

Then STOP.

Do not generate architecture.

Do not generate DDD models.

Do not create technical designs.

Do not begin implementation.
