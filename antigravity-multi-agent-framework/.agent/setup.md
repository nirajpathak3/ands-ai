# Antigravity 2.0 Workflow Engine Directory Structure

This document outlines the detailed folder structure and configuration layout for the Autonomous Multi-Agent Orchestration Platform. All files are positioned relative to the root `.agent/` directory on the active execution branch.

## Directory Tree Layout

```text
E:\ands-agentic\EL-AI\obs-agent\.agent\
├── setup.md                             # Global agent platform configuration file
├── workflows\                           # Active core operational workflows
│   ├── intake.md                        # Gate 0 triage configuration
│   ├── plan.md                          # Planning-only engine instruction spec
│   ├── architect.md                     # Gate 1 design engine contract
│   ├── team_lead.md                     # Workload parsing and queue coordination
│   ├── build.md                         # Sandboxed execution instructions
│   ├── review.md                        # Gate 2 static analysis and code review spec
│   ├── qa.md                            # Gate 3 dynamic test execution runtime
│   └── release_manager.md               # Gate 4 & 5 deployment and promotion engine
│
├── templates\                           # Immutable schemas and structural templates
│   ├── decisions_template.md            # Structural skeleton for DECISIONS.md
│   ├── plan_template.md                 # 8-section formatting blueprint for PLAN.md
│   ├── architecture_template.md         # Design contract specification schema
│   └── review_template.md               # Verdict parsing pattern for REVIEW.md
│
└── runtime_state\                       # Blackboard memory layer (Ephemeral / Git-tracked)
    ├── DECISIONS.md                     # Current project classification and constraints
    ├── PLAN.md                          # Formulated and approved implementation plan
    ├── ARCHITECTURE.md                  # System design contract and interface boundaries
    ├── TASKS.json                       # Active task queue and context boundaries
    ├── BUILD_NOTES.md                   # Real-time implementation adjustments
    ├── REVIEW.md                        # Active code review verdicts and findings
    ├── QA_REPORT.md                     # Test runtime traces and metric output
    └── QA_METRICS.json                  # Parsable telemetry dataset for analytics tracking