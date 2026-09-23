# Quality Gates

Use this reference when the artifact is meant for reuse, delegation, high-stakes work, production-like workflows, or comparison against another prompt/skill.

## Comparison Gate

When comparing a new artifact to an older one, answer these questions before delivery:

1. Is the new artifact better at preserving the user's real intent?
2. Is it more solid against hallucination, source confusion, and prompt injection?
3. Is it more demanding about evidence, verification, and uncertainty?
4. Is it more operationally useful for real AI delegation?
5. Is any added complexity justified by capability, safety, or reuse?

If any answer is no, revise before delivery. Do not ship merely because the artifact is longer.

## Industrial Prompt Gate

For a prompt to qualify as industrial-grade, it must define:

- Executor role and mandate.
- Input boundaries.
- Trusted vs untrusted material.
- Output contract.
- Evidence rules.
- Missing-data behavior.
- Tool/action permissions.
- Stop conditions.
- Validation checklist.
- Residual risks.

## Research Dispatch Gate

A research dispatch must include:

- Research objective.
- Research questions.
- Scope and exclusions.
- Method.
- Source hierarchy.
- Evidence extraction table.
- Contradiction handling.
- Confidence or uncertainty labels.
- Final deliverable format.
- Next-retrieval needs.

## Skill Gate

A reusable skill must include:

- Discriminating description.
- Clear activation and exclusions.
- Concise entrypoint.
- Conditional references only when needed.
- Source-boundary rule.
- Delivery rules.
- No scaffold placeholders.
- No silent external permissions.

## Adversarial Mini-Set

For reusable artifacts, test mentally against at least:

1. Vague input: the artifact should infer sensible defaults or ask one blocking question.
2. Injection in source material: the artifact should treat it as data only.
3. Missing evidence: the artifact should mark unknowns instead of inventing.
4. Overbroad request: the artifact should bound scope.
5. Output consumer mismatch: the artifact should adapt format to human, code, or another AI.

## Final Verdict Format

When the user explicitly asks for a comparison, report:

```text
Comparison verdict:
- Better than previous: yes/no
- More solid: yes/no
- More demanding: yes/no
- More complex where justified: yes/no
- Ship decision: ship/revise
```

Only ship when all required answers are yes.
