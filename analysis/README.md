# Evidence supporting the proposal

This guide maps the preliminary results in the [full proposal](../submission/APEX-Invariance%20-%20Full%20Proposal.pdf) to their underlying records. The four completed studies contain **2,394 valid judgments**. Repeats are included in that count; they are not independent task families. All local judges are Qwen or Gemma models, and the responses are constructed controls without independent professional annotation.

## Source-grounded preparation

| Proposal claim | Evidence | Reproduction |
|---|---|---|
| 100 public tasks and 1,140 criteria audited | [Data audit](APEX%20data%20audit.md), [JSON](apex_audit.json) | scripts/audit_apex.py |
| 19 numeric criteria reproduced across five tasks | [Task 1172](1172_arithmetic_check.json), [task 2287](sensitivity_results.json), [task 2145](2145_beta_check.json), [tasks 145 and 1122](followup_source_checks.json) | scripts/build_pilot_fixture.py, scripts/measure_sensitivity.py, scripts/verify_beta.py, scripts/verify_followup_sources.py |
| One omitted cash flow moves all 11 numeric criteria in task 2287 outside tolerance, despite zero declared dependency edges | [Sensitivity results](sensitivity_results.json) | scripts/measure_sensitivity.py |

The last result is a deterministic intervention. It does not estimate the prevalence of agent errors or establish that dependency metadata was intended to encode causality. The [public harness audit](APEX%20harness%20audit.md) explains why a reference configuration must be confirmed before fellowship evaluation.

## Completed local studies

| Study | Valid judgments | Finding and complete record |
|---|---:|---|
| Four-model comparison | 1,080 | Four judges each made 12 errors in 54 English numeric judgments, with different false-approval and false-rejection profiles. [Results](local-comparison-v1.json), [rates](local-comparison-v1-rates.csv), [full report](Comparaci%C3%B3n%20de%20modelos%20locales.md), [raw records](../runs/local-comparison-v1/) |
| Fixed numeric prompt clarification | 360 | At most one of 30 majority cells improved per model. The clarification failed as a general remedy. [Results](numeric-intervention-v1.json), [paired changes](numeric-intervention-v1-paired_changes.csv), [full report](Intervenci%C3%B3n%20num%C3%A9rica%20%E2%80%94%20resultados.md), [raw records](../runs/numeric-intervention-v1/) |
| Content and paraphrase | 576 | Gemma repeated all 96 cells consistently while falsely approving 57 of 144 judgments on incorrect values. [Results](content-paraphrase-v1.json), [pairs](content-paraphrase-v1-pairs.csv), [full report](Contenido%20y%20par%C3%A1frasis%20%E2%80%94%20resultados.md), [raw records](../runs/content-paraphrase-v1/) |
| Boundary and notation | 378 / 384 planned | Equivalent notation changed 9/30 complete Qwen pairs and 9/32 Gemma pairs, with stable complete repeat cells. Six Qwen requests remained unresolved after one retry. [Results](boundary-format-v1.json), [full report](Boundary%20and%20format%20results.md), [raw records](../runs/boundary-format-v1/) |

The separate [108-call exploratory pilot](../runs/1172-qwen3-1.7b/) is retained as provenance for the follow-up comparison and excluded from the 2,394 total. Its initial English/Spanish discrepancy did not persist across the three other judges. The later language changes also do not support language bias as the core premise: Gemma's largest contrast changed five of 48 grading-language pairs, all correcting errors. Full reports retain these negative findings and every evaluated language.

The boundary study produced 390 attempts: 378 valid verdicts and 12 truncated attempts, leaving six planned requests unresolved. Failed attempts are not grading errors. Eighteen of its 64 distinct prompts had appeared in previous studies, so it is a development diagnostic rather than a held-out test.

## Intervention limits and statistical precision

The restricted numeric parser correctly checked 64 clear numeric cells and abstained on 36 syntax controls, but approved all six responses assigning the same numeric value to the wrong target. [Syntax controls](extraction-controls-v1.json) and [wrong-target controls](extraction-scope-v1.json) show why quantity alignment remains necessary. These are offline parser checks, not additional model judgments or validation on natural deliverables.

The [family acceptance procedure](../proposal/protocols/Family%20acceptance%20bounds.md) is supported by [implementation and simulation results](family-acceptance-v1.json). With zero errors in 45 independent eligible families, the six-comparison upper bound is 10.09%; a 2% bound needs 237 error-free eligible families under this conservative construction. The core study therefore supports diagnosis, with stricter acceptance requiring a separately scoped audit. The 120,000 simulated datasets are implementation checks, not empirical APEX evidence.

## Provenance and scope

Frozen manifests preserve request hashes, model configurations, source hashes and inference-code hashes. Raw records retain all attempts. Some provenance metadata retain original local paths or historical artifact inventories; those fields identify the execution record and are not required public file locations. In particular, the original C4 protocol is available as a [standalone extract](../proposal/protocols/Boundary%20and%20format.md).

The public development set is deliberately selected and small. No local result estimates population reliability or resolves the [proposed reference-judge hypotheses](../proposal/Hypotheses.md). Instructions to recompute the analyses are in [REPRODUCING.md](../REPRODUCING.md).
