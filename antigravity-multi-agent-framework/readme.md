# Antigravity 2.0: Autonomous Engineering Runtime

This project operates on a governed, multi-agent software development lifecycle (SDLC). Agents do not execute in a single continuous stream; instead, they operate in isolated modes, reading from and writing to a shared blackboard (`.agent/runtime_state/`).

Human-in-the-loop (HITL) approval is required at predefined validation gates.

## Step-by-Step Initiation Guide

To implement a new feature or service, follow this exact sequence using your environment's slash commands or agent triggers.

### Step 1: Triage & Decisions (Gate 0)
**Command:** Invoke the Intake Agent (e.g., `/intake [Task Description]`)
*   **What happens:** The agent triages the request, defines architectural constraints, and identifies missing information.
*   **Output:** Generates `DECISIONS.md` in `runtime_state/`.
*   **Human Action:** Answer any "Open Questions" listed in the file. Once satisfied, reply: `"Approved. Begin execution."`

### Step 2: Strategic Planning
**Command:** Invoke the Planning Agent (e.g., `/plan`)
*   **What happens:** The agent reads `DECISIONS.md` and generates an 8-section execution roadmap.
*   **Output:** Generates `PLAN.md` in `runtime_state/`.
*   **Human Action:** Review the risk mitigations and step decomposition. Reply: `"Approved. Begin execution."`

### Step 3: System Architecture (Gate 1)
**Command:** Invoke the Architect Agent (e.g., `/architect`)
*   **What happens:** Translates the plan into a strict technical contract, defining data schemas, API interfaces, and module boundaries.
*   **Output:** Generates `ARCHITECTURE.md` in `runtime_state/`.
*   **Human Action:** Sign off on the technical contract. Reply: `"Approved. Begin execution."`

### Step 4: Task Breakdown & Orchestration
**Command:** Invoke the Team Lead Agent (e.g., `/team_lead`)
*   **What happens:** Slices the architecture into isolated execution tasks, capping context to prevent builders from being overwhelmed.
*   **Output:** Populates `TASKS.json` or your execution queue.
*   **Human Action:** None required unless a breakdown conflict is flagged.

### Step 5: Implementation
**Command:** Invoke the Builder Agent (e.g., `/build`)
*   **What happens:** The builder reads the architecture contract and tasks, writing actual code. It tracks any necessary deviations.
*   **Output:** Modifies project source code and generates `BUILD_NOTES.md`.
*   **Human Action:** Watch the build log. Once the builder stops and signals readiness, proceed to review.

### Step 6: Code Review & SAST (Gate 2)
**Command:** Invoke the Reviewer Agent (e.g., `/review`)
*   **What happens:** Performs static analysis, checks code against `ARCHITECTURE.md`, and scans for security vulnerabilities.
*   **Output:** Generates `REVIEW.md` (PASS or FAIL).
*   **Human Action:** 
    *   If **FAIL**: Route back to `/build` to fix the findings. (Escalates to you after 3 consecutive fails).
    *   If **PASS**: Proceed to QA.

### Step 7: Dynamic Verification (Gate 3)
**Command:** Invoke the QA Agent (e.g., `/qa`)
*   **What happens:** Executes unit, integration, and regression test suites deterministically.
*   **Output:** Generates `QA_REPORT.md` and `QA_METRICS.json`.
*   **Human Action:** Review failures if any. If passed, proceed to Release.

### Step 8: Release Management (Gates 4 & 5)
**Command:** Invoke the Release Manager (e.g., `/release`)
*   **What happens:** Final compliance check, verification of rollback paths, and preparation of deployment artifacts.
*   **Output:** Deployment trigger or failure escalation.
*   **Human Action:** Final sign-off for production environment promotion.

---

## Multi-Project Orchestration Guide

To initialize and run multiple parallel projects/POCs without state collisions, follow this folder structure and setup sequence:

### 1. Folder Structure Standard
Ensure your new project is created parallel to other projects, and contains a local `.agent_state/` directory to store its specific blackboard history:
```text
your-workspace/
├── .agent/                             # Global Orchestration Code / Workflows
├── project-a/                          # Project A Workspace
│   └── .agent_state/                   # Project A State Memory (Local)
└── project-b/                          # Project B Workspace
    └── .agent_state/                   # Project B State Memory (Local)
```

### 2. Onboarding Steps for a New Project
When starting a new project, follow these commands to set up the context boundaries:

1. **Create the Project Directory:**
   Create the directory `<workspace-path>/<new-project-name>/.agent_state/`.
2. **Execute Gate 0 (Intake):**
   Prompt the agent:
   > *"Initialize Intake for project `<new-project-name>`. Please analyze the workspace and write `DECISIONS.md` directly inside `<workspace-path>/<new-project-name>/.agent_state/DECISIONS.md`."*
3. **Execute Gate 1 (Planning & Architecture):**
   Prompt the agent:
   > *"Read `DECISIONS.md` from the `<new-project-name>` local state directory, then generate `PLAN.md` and `ARCHITECTURE.md` inside `<workspace-path>/<new-project-name>/.agent_state/`."*
4. **Execute Build Commands:**
   All compilation, code writes, and test runs must set their current working directory (`Cwd`) to your specific project workspace path (e.g., `<workspace-path>/<new-project-name>`), keeping operations isolated from other workspaces.

### 3. Local Script Configuration Note
> [!IMPORTANT]
> The setup automation helper script `.agent/init-agent-project.ps1` contains hardcoded absolute path pointers targeting local directories.
> If you are setting up this system in your own workspace, update the `$GlobalAgentDir` and `$TargetProjectDir` path variables in [.agent/init-agent-project.ps1](file:///e:/ands-agentic/antigravity-multi-agent-framework/.agent/init-agent-project.ps1) to point to your own local directories.