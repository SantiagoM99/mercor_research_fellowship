# Family-level acceptance bounds

Specified and tested on 13 September 2026, before reference-judge or expert outcomes. Implementation: `scripts/family_acceptance.py`; simulation configuration: `experiments/family-acceptance-v1.json`; results: `analysis/family-acceptance-v1.json`. The procedure is conservative and conditional on the sampling assumptions below.

## Target and sampling

For a fixed judge configuration, the primary target is the equal-family mean false-approval or false-rejection fraction in each scoring class. An eligible family has at least one expert-labeled item in the corresponding class and label stratum. False approvals use unmet labels; false rejections use met labels. The number of eligible families can therefore be smaller than the total test-family count.

Before collecting an acceptance audit, freeze the target task distribution, family sampling and authoring procedure, agent-response selection, expert-label rules, judge configuration, repeat aggregation and class assignments. Eligible families must be independent draws from the same declared distribution; repeated criteria and responses within one family may be arbitrarily dependent. A convenience sample of public tasks, fixed domain quotas pooled without a stratified analysis, or families sharing a common task template do not establish this assumption. Those samples support descriptive diagnostics, not this population guarantee. If the generation and sampling process cannot justify independent families, retain review and report the observed rates without an acceptance claim.

Choose the single configuration to be considered for automatic acceptance on calibration data. Report other configurations as exploratory comparisons. If acceptance is offered for any of four test-evaluated configurations, the multiplicity factor increases from 6 to 24, or selection must be followed by a fresh independent audit. Do not add configurations, inspect results and then reuse the original threshold. Use a fixed audit size; repeated optional stopping is not covered.

## Conservative bound

Within each eligible family i, let R_i be the error fraction in one class and label stratum, and let Z_i indicate whether there is any such error. Then 0 <= R_i <= Z_i <= 1. Consequently E[R_i] <= E[Z_i]. Under the sampling assumptions, the Z_i are independent Bernoulli observations even if all criteria within a family fail together.

For n eligible families with k positive Z_i, compute an exact one-sided Clopper–Pearson upper bound U on E[Z_i]. This also upper-bounds the desired E[R_i]. It can be loose: a family with one error among ten items contributes an event of one, not an error fraction of one. Report the empirical equal-family mean separately and never label the event rate as the criterion error rate.

For one configuration, allocate alpha = 0.05 / 6 across three classes and two error types. The union bound gives simultaneous coverage of at least 95% across the six limits, without requiring independence between the six analyses. Adopt automatic grading for a class only when its false-approval upper bound is at most 2% and its false-rejection upper bound is at most 5%, or other limits agreed with Mercor before testing. Classes with no eligible families receive upper bound 1 and remain in review.

The exact binomial inversion follows the [NIST reference](https://www.itl.nist.gov/div898/software/dataplot/refman2/auxillar/exacbici.htm). Applying it to family events and using R_i <= Z_i is the conservative construction used here. This is distinct from the accepted-verdict risk in [Badshah et al.](https://arxiv.org/html/2608.17994), whose calibration guarantees also depend on independent observations.

## Precision and budget consequence

With zero errors, U = 1 - alpha^(1/n). At 45 eligible test families, U is 6.44% for a single unadjusted bound and 10.09% for the six simultaneous bounds. Even in this best case, the 60-family proposal with 45 test families cannot support 2%/5% automatic acceptance through this conservative procedure.

| Proposed limit | One bound | Six bounds, one judge | 24 bounds, four judges |
|---|---:|---:|---:|
| 2% false approvals | 149 | 237 | 306 |
| 5% false rejections | 59 | 94 | 121 |

Entries are minimum **independent eligible families with zero errors**, not criteria or model calls. Observed errors increase the required sample. These are sufficient counts for this construction, not information-theoretic lower bounds for every possible method. The funded core study therefore delivers diagnostics and regression evidence; strict automatic acceptance requires a separately scoped audit, different agreed limits, or a justified sharper procedure. No extra expert budget is assumed to be approved.

## Implementation checks and simulation

The numerical implementation was checked against the analytic zero-error expression, exact binomial coverage on a probability grid, monotonicity and inversion, and invariance to multiplying the number of repeated observations within a family.

The frozen simulation has 24 scenarios: 16, 45 or 150 families; true mean error of 1%, 2%, 5% or 10%; and independent or perfectly correlated errors among ten criteria per family. Each scenario has 5,000 replications with seed 20260913. Simulated labels are not model judgments and are excluded from empirical study totals.

The largest unadjusted family-event undercoverage was 5.02%, within the pre-specified 6% simulation failure threshold and consistent with Monte Carlo variation around the nominal 5% limit. The naive pooled-criterion method missed the true error rate in 72.9% of replications in the worst scenario (16 families, 2% error, perfect within-family dependence). Passing these scenarios checks the implementation; the mathematical argument and real-world sampling assumptions carry the guarantee.
