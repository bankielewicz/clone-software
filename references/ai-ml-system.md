# AI and ML system playbook

Use this playbook when model inference, retrieval, ranking, generation, training, evaluation, or model lifecycle defines observable behavior.

## Capture and specify

- Freeze model and tokenizer identifiers/digests, serving configuration, prompt/template version, tools, retrieval corpus/index, random seed, sampling parameters, hardware class, and safety policy.
- Record input/output schemas, context limits, truncation, batching, streaming, tool calls, citations, refusal/error behavior, latency budgets, and data retention.
- Define an evaluation set independent of the implementation, with dataset provenance, contamination controls, metrics, thresholds, variance policy, and adversarial cases.
- Pin privacy, tenant isolation, prompt-injection boundaries, model/data licenses, human review, fallback, rollback, and monitoring contracts.

## Minimum MVP and proof

Implement one complete inference or training journey with real state and explicit degraded/failure behavior. Verify deterministic contracts exactly and stochastic contracts with pinned repeated-run statistics. Test malformed inputs, injection, unsafe output, unavailable model/dependency, timeout, cancellation, and data-isolation paths. Never claim model or quality parity from a few favorable examples.
