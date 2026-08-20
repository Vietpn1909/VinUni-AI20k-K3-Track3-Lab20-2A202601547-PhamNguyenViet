# Benchmark Report

Generated: 2026-08-20 05:05 UTC

## Results Summary

| Run | Latency (s) | Cost (USD) | Quality | Citation cov. | Failure rate | Notes |
|---|---:|---:|---:|---:|---:|---|
| baseline | 12.23 | 0.0004 | 6.0 |  | 0% |  |
| multi-agent | 30.17 | 0.0016 | 10.0 | 100% | 0% | route_history=['researcher', 'analyst', 'writer', 'done'] |

## Analysis

- **Latency**: Multi-agent is 2.5x slower than baseline (30.17s vs 12.23s).
- **Quality**: Multi-agent scores +4.0 points higher than baseline (10.0 vs 6.0).
- **Cost**: Multi-agent costs 3.9x more than baseline ($0.0016 vs $0.0004).
- **Citation coverage**: 100% of sources cited in multi-agent output.

## Failure Modes & Observations

- **Infinite loops**: Mitigated by `max_iterations` guardrail in SupervisorAgent. Workflow completed in 4/6 allowed iterations.
- **Context loss**: Shared `ResearchState` ensures all agents can access prior work. No context was lost between handoffs.
- **Cost overhead**: Multi-agent makes 4+ LLM calls vs 1 for baseline -- higher cost is expected.
- **Quality trade-off**: Multi-agent scores higher on structure and citations but costs more time and tokens.
- **API credit exhaustion**: Encountered `402 Payment Required` from OpenRouter when credits ran low. The system's retry mechanism (tenacity, 3 retries) correctly surfaced the error after exhausting retries. **Fix**: monitor credit balance or set `max_tokens` lower to stay within budget.

## When to Use Multi-Agent

- [YES] Complex research queries requiring multiple perspectives
- [YES] Tasks where citation quality and source analysis matter
- [NO] Simple Q&A where latency and cost are priorities
- [NO] Time-critical applications with strict SLA requirements
