# Audit / Upgrade

Use this mode when the user gives an existing prompt, system directive, skill, or AI workflow and asks to improve it.

## Audit Priorities

Lead with defects that change behavior:

- unclear objective,
- missing output contract,
- source/instruction confusion,
- hallucination surface,
- stale or unverifiable claims,
- unsafe tool/action permissions,
- missing stop conditions,
- hidden chain-of-thought requests,
- over-engineering,
- template scarring,
- no evaluation path.

## Upgrade Procedure

1. Identify the artifact's intended use.
2. Diagnose the current failure modes.
3. Remove ornamental or dangerous instructions.
4. Preserve useful owner intent.
5. Add evidence, validation, and output contracts.
6. Deliver the upgraded artifact.

## Audit Output

For small upgrades, return:

- Verdict: keep / revise / replace.
- Top defects.
- Upgraded artifact.

For larger systems, return:

- Findings by severity.
- Design decisions.
- Upgraded prompt or skill.
- Remaining risks.
