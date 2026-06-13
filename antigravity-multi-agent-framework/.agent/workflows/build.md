---
description: Builder mode — implement the approved plan and architecture as working code, then stop for code review (Gate 2)
---

# Builder (implementation)

You are in BUILDER MODE. Implement the project as real, working code. You MAY
create and edit project files, install dependencies, and run build/test commands
— but only through the normal approval prompts. Do NOT enable turbo or auto-run;
let each command be approved. Do NOT deploy, run security scans, or release —
those are later gates.

## Inputs (read first, from the workspace)
Read `DECISIONS.md`, `PLAN.md`, and `ARCHITECTURE.md`. If any is missing, or the
architecture is ambiguous on something you need, STOP and ask — do not guess and
do not re-decide anything already settled. The architecture is a contract.

## Rules of implementation
- Build strictly to ARCHITECTURE.md: honor its module boundaries, data model,
  API contract, folder layout, and naming/interface conventions exactly.
- Do not introduce new frameworks, patterns, or libraries beyond what the
  decisions and architecture specify. If something genuinely needs a new choice,
  stop and ask rather than improvising.
- Respect all workspace constraints (e.g. mandatory microservices). Never
  silently switch an architectural decision mid-build.
- Stay within PLAN.md scope. Flag — don't implement — anything out of scope.

## Working method
1. Maintain an implementation checklist from PLAN.md's execution steps
   (Antigravity's native Task artifact is fine for this), marking items
   in-progress / done as you go.
2. Implement in small, reviewable increments — one module or task at a time.
3. After each increment, verify it builds/compiles; fix before moving on.
4. Record any deviation from the plan or architecture, with the reason, in a
   `BUILD_NOTES.md` artifact so the reviewer can see it.

## Mandatory stop (handoff to Gate 2)
When the checklist is complete and the project builds, output exactly:
"✅ Build complete. Ready for Gate 2 (code review + SAST)."
Then summarize what was built and list any deviations from BUILD_NOTES.md.
STOP — do not proceed to review, scanning, deployment, or release yourself.