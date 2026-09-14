# Boundary and numeric-format protocol

Extracted on 14 September 2026 from the planning entries recorded on 13 September before the corresponding runs. The original manifest identifier is DESIGN.md C4. This extract preserves those predictions and controls; it is not a new preregistration.

## Boundary and notation study

Extend the six source-reproduced numeric criteria in C3 with nominal, inclusive lower/upper endpoints, and one unit of stated precision inside/outside each endpoint. Deduplicate coincident values within each criterion while retaining all boundary-role tags; narrow intervals make several positions identical. Cross each distinct value with ordinary decimal and equivalent scientific notation, English only, three same-condition repeats, Qwen 3 4B and Gemma 3 4B, using the unchanged public grading template. Freeze prompts, configuration and source hashes before judging. Prediction: at least one model has greater error on endpoint/just-inside cells than on nominal cells. Refutation: neither model shows that increase; any comparison with a shared nominal/inside value reports the overlap. Numeric-format invariance predicts unchanged majority verdicts, refuted by any paired change on this finite test suite; report repeat disagreement as its control. These are instrument hypotheses, not H4 on Mercor's judge or population claims.

A conservative deterministic extractor reads only response text and a declared unit, never the stimulus's expected value or label; it then checks the declared interval. Prediction: correct verdicts on all unambiguous constructed numeric cells, and abstention on missing, conflicting or unsupported-unit responses in an additional offline control set. Any wrong verdict or unsafe non-abstention refutes this engineering prediction. This is a restricted extraction test, not H6 on natural held-out responses. An always-pass and an always-fail judge must be exposed by separate error denominators. Runtime failures remain missing, never failed criteria. Frozen requests and raw outputs will be preserved; three selected families do not support population intervals.

## Quantity-alignment scope check

Before interpreting the restricted checker's success on numeric syntax, test whether it verifies which quantity the response describes. Keep the frozen checker unchanged. For each of the six criteria, compare its original correct response with a twin reporting the same numeric value and unit for a different named target: Gen Z to Millennials, Fixed Price to Performance Based, and KatNip to AnotherCo. A target-mismatched response is expected not to satisfy the requested criterion under this constructed control; independent expert validation remains pending. Prediction: this parser, which receives only text, bounds and unit, will incorrectly approve at least one mismatched target. Refutation: it rejects or abstains on every mismatch while accepting the original controls. These twelve offline checks assess the prototype's scope; they add no model judgments and do not test H6 on natural deliverables.

## Execution records

See the [frozen study configuration](../../experiments/boundary-format-v1.json), [requests and manifests](../../runs/boundary-format-v1/) and [results report](../../analysis/Boundary%20and%20format%20results.md). The six unresolved requests and prompt reuse are reported alongside the observed outcomes.
