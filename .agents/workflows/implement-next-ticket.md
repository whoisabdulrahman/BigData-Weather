# /implement-next-ticket

Implement the next dependency-ready feature ticket for the National Weather Big Data Analytics Platform.

## Step 1 — Recover context
Read:
- `AGENTS.md`
- `docs/IMPLEMENTATION_STATE.md`
- `docs/DECISIONS.md`
- `docs/CHANGELOG.md`

Then read relevant sections of:
- `docs/01_PRD.md`
- `docs/02_Technical_Architecture.md`
- `docs/03_Security_Access_Governance.md`
- `docs/04_Frontend_Specification.md`
- `docs/05_Feature_Ticket_List.md`

## Step 2 — Inspect repository
Check:
- Git status
- current branch
- relevant source files
- tests
- dependencies
- existing implementation

Do not rewrite working code unnecessarily.

## Step 3 — Select work
Identify the highest-priority unfinished ticket whose dependencies are satisfied.
If the state file names the current ticket, continue it unless blocked.

## Step 4 — Implement
Implement the smallest complete unit satisfying the ticket.
Do not create fake functionality.
Follow architecture and security rules.

## Step 5 — Validate
Run relevant:
- tests
- type checks
- lint
- build
- migration checks
- integration checks

## Step 6 — Review
Check:
- security
- error handling
- data contracts
- authorization
- documentation impact
- acceptance criteria

## Step 7 — Persist state
Update `docs/IMPLEMENTATION_STATE.md` with completed/current ticket, files, tests, DB/API/frontend changes, issues, and next task.
Update `docs/CHANGELOG.md`.
Update `docs/DECISIONS.md` only when a meaningful technical decision was made.

## Step 8 — Git checkpoint
If complete and tests pass, create a meaningful commit unless a different Git workflow is configured.
Do not rewrite history.

## Step 9 — Continue
Continue to another dependency-ready ticket only when context and risk allow.
If context is constrained, stop after the current safe unit and update state.

## Final response
Report:
- completed ticket
- files changed
- tests run
- known issues
- next ticket
