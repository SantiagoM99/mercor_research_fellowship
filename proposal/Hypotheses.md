# Research hypotheses

These are the prospective tests in Appendix A of the [full proposal](../submission/APEX-Invariance%20-%20Full%20Proposal.pdf).

The following thresholds were recorded before collecting any reference-judge results or independent expert judgments. They are tests of specific claims, not substitutes for the [family acceptance procedure](protocols/Family%20acceptance%20bounds.md). All reference-judge and expert studies below are proposed fellowship work.

| Test | Prediction and evidence against it |
|---|---|
| H8: concentration by class | At least one class has an error rate at least twice the global rate for the same error type. The claim is refuted if every class is within 1.5 times the global rate for both error types. Ratios between 1.5 and 2 are inconclusive, and ratios are undefined when the global error rate is zero. Absolute rates and uncertainty would accompany every comparison. |
| H4: numeric boundaries | Reference-judge error on inclusive endpoints and just-inside values exceeds 5%. The refutation condition is error at or below 5% with an interval upper bound at or below 10%. This does not imply acceptance at a stricter limit. |
| H5b: propagation | In at least one of five pilot families, an error changes an expert-verified label outside the declared dependents, and the judge follows that change. Refutation requires all verified propagated changes to fall within declared descendant sets in all five families. This concerns tested interventions, not graph completeness or annotation defects. |
| H6: numeric intervention | After quantity alignment and extraction, the checker lowers error by at least two percentage points at coverage of at least 70% on held-out families. A gain below two points or coverage below 70% refutes the claim. Both methods would be compared on the same selected cases, with review cost reported. |
| H7: feasibility | Task construction and independent solving take at most eight expert hours per family. Grading takes at most twenty minutes per response per grader. Pilot medians above twelve hours or thirty minutes refute those feasibility assumptions. Intermediate costs require budget revision. |
| H2 / H3: optional language transfer | Equivalent Spanish responses or Spanish grading add at least three percentage points of disagreement beyond same-condition repeats. A 95% family-bootstrap interval entirely below that threshold refutes the effect; an interval crossing it is inconclusive. Small disagreement does not establish acceptable absolute error. |

## Measurement conventions

The false-approval rate is measured among criteria with unmet reference labels. The false-rejection rate is measured among criteria with met reference labels. The primary analysis averages within-family rates equally across eligible task families. All criteria, responses, transformations and repeats from a task stay together through calibration, testing and resampling.

Local development results and the negative findings are documented in the [evidence guide](../analysis/README.md). They do not resolve these prospective tests on Mercor's reference judge.
