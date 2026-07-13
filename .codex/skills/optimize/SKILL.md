---
name: optimize
description: Make one measured, minimal optimization to Insight_Extractor's regex, dynamic-stemmer, state, or keyword-expansion paths without changing public behavior or lazy model loading.
---

# Codex optimizer

This is a measured optimization workflow, not a broad refactor.

## Scope

Start from \`main\`, read \`CLAUDE.md\`, and trace every caller before changing a shared helper. Candidate hot paths are:

- \`InsightExtractor.extract_regex_entities\`;
- \`DynamicKeywordStemmer\` compilation and matching;
- \`KeywordPatternRegistry.extract_all\`;
- repeated state serialization/loading;
- TF-IDF candidate selection in \`update_thread_keywords\`.

Do not optimize BERT behavior without a reproducible model-backed benchmark. Do not add dependencies, change public signatures, alter thresholds, remove lazy loading, or change report/state formats as part of an optimization.

## Loop

1. Establish a baseline with the relevant unit tests and a deterministic model-free \`timeit\` or repeated-input benchmark.
2. Identify the actual allocation, repeated scan, or recompilation causing the cost.
3. Make the smallest local change that preserves exact output order, deduplication, match spans, and exception behavior.
4. Add or update one focused unit test for the preserved behavior.
5. Re-run the baseline benchmark, \`preflight\`, and \`verify-no-model\`.
6. Keep the change only when the measurement is reproducible and the diff is smaller than the operational complexity it introduces.

Use a \`# ponytail:\` comment when deliberately accepting a known ceiling, for example: \`# ponytail: linear scan retained; build an indexed matcher only after profiling proves it matters\`.

## Evidence

Report:

- benchmark input and repetitions;
- before/after timing or allocation result;
- tests and gates run;
- model/integration checks skipped and why;
- any remaining ceiling.

If the baseline does not show a meaningful bottleneck, stop and report “no safe optimization identified.” Do not manufacture a cache, abstraction, configuration knob, or money-mode behavior to create a diff.