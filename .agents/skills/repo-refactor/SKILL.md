---
description: Use when reorganizing the repository into a senior structure, extracting modules, moving legacy folders, or preserving behavior while refactoring.
---

# Repository Refactor Skill

## Goal
Refactor the current learning-oriented repo into a clean senior delivery repo without breaking the project.

## Use this skill when
- Moving files into `infra/`, `lambda/`, `models/`, `scripts/`, or `docs/`.
- Splitting the monolithic Lambda file.
- Replacing SAM with Terraform.
- Creating migration commits.
- Keeping old code temporarily while new code is introduced.

## Refactor principles
- Preserve behavior before improving behavior.
- Move first, then modify.
- Keep commits small and reviewable.
- Add tests around critical behavior before major changes.
- Keep legacy folders until the replacement is validated, then remove with a clear migration note.

## Recommended migration phases

### Phase 1 — Baseline and safety
- Add `CLAUDE.md` and `.claude/skills/`.
- Add `.gitignore` coverage for Terraform state, `.tfvars`, virtualenv, build artifacts, and secrets.
- Add secret scanning.
- Document current architecture.

### Phase 2 — Terraform structure
- Create `infra/` structure.
- Move/refactor `TERRAFORM_Code` into `infra/modules/ec2-workload` and `infra/envs/dev`.
- Create backend configuration.
- Add common tags and variable validation.

### Phase 3 — SAM migration
- Convert `AIOPs_SAM/template.yaml` into Terraform modules.
- Keep Lambda code behavior initially unchanged.
- Deploy Lambda from zip through Terraform.

### Phase 4 — Lambda refactor
- Create `lambda/src/aiops/` package.
- Extract modules from `AIOPs_SAM/app.py`.
- Add unit tests.
- Package through Jenkins.

### Phase 5 — ModelOps integration
- Move model workflows under `models/` or create wrappers that call legacy scripts.
- Add artifact metadata and validation.
- Make Terraform consume model artifact URIs.

### Phase 6 — Jenkins delivery
- Add root `Jenkinsfile`.
- Add scripts used by Jenkins.
- Add smoke tests.

### Phase 7 — Production hardening
- Remove hardcoded credentials.
- Remove public SSH.
- Scope IAM.
- Add alarms, dashboards, runbooks, and cleanup workflow.

## File move guidance
When moving files:

- Use `git mv` where possible.
- Preserve original names in commit message.
- Update imports and paths immediately.
- Update README and docs after each phase.
- Run tests after every phase.

## Documentation updates required
Every refactor should update at least one of:

- `README.md`
- `docs/architecture.md`
- `docs/deployment.md`
- `docs/operations-runbook.md`
- `docs/security.md`

## Acceptance criteria
A refactor is complete when:

- The old and new behavior are compared.
- Tests pass.
- Jenkins pipeline still works or has a documented temporary limitation.
- README does not point users to obsolete deployment steps.
- The repo remains understandable to a new engineer.
