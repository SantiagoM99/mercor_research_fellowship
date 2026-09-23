# APEX-Invariance: who grades the grader?

This repository contains my proposal and reproducible preliminary experiments for the Mercor Research Fellowship in Novel Evaluation Methodology. I am Santiago Martínez Novoa from Universidad de los Andes in Bogotá.

**Which kinds of work will a new APEX judge grade more reliably, and where will it introduce errors?** I propose following rubric criteria through controlled changes to professional deliverables, then testing whether those comparisons lead to more reliable grading or lower review cost.

## Read the proposal

- Start with the [one-page pitch (PDF)](submission/APEX-Invariance%20-%20One-Page%20Pitch.pdf) for the question, preliminary evidence and proposed collaboration.
- Read the [full proposal (PDF)](submission/APEX-Invariance%20-%20Full%20Proposal.pdf) for the methodology, results, workplan, hypotheses and sixteen references.
- Consult the [research hypotheses](proposal/Hypotheses.md) and [references](proposal/References.md) directly in the repository.

## Check the supporting evidence

The [evidence guide](analysis/README.md) connects the proposal's numerical claims to recorded results and reproduction scripts. I audited 100 public tasks, reproduced 19 numeric criteria from source files and collected 2,394 valid local judgments across four studies.

![Equal total error can conceal opposite grading errors](figures/acceptance_single.png)

These studies use constructed controls and local Qwen and Gemma judges. They establish test cases and expose limitations in the evaluation method; they do not establish failures in Mercor's reference judge. The complete records retain negative results, repeated calls and failed attempts. During the fellowship, I would work with Mercor's experts to validate the method independently and test it on natural agent responses.

## Reproduce the results

See [REPRODUCING.md](REPRODUCING.md) for offline analysis, figure generation and verification. Recomputing results from recorded outputs requires no model calls or API credentials.

| Directory | Supporting material |
|---|---|
| [submission/](submission/) | The two proposal PDFs |
| [proposal/](proposal/) | Hypotheses, cited bibliography and experimental protocols |
| [analysis/](analysis/) | Claim-to-evidence guide, reports and numerical results |
| [experiments/](experiments/) | Study configurations and prompt variants |
| [runs/](runs/) | Frozen requests, raw responses, manifests and model identities |
| [data/](data/) | Pinned public APEX development data, source files and upstream harness excerpts |
| [scripts/](scripts/), [tests/](tests/) | Experiment and analysis code with verification tests |
| [figures/](figures/) | Figures supporting the proposal and detailed reports |

The public development data come from [Mercor's APEX-v1-extended release](https://huggingface.co/datasets/mercor/APEX-v1-extended), revision e0db9513115f8d0449591fac3d77d4bdc1a98fef. Original attribution, source manifests and the upstream harness license are retained under data/. No hidden evaluation cases or internal Mercor trajectories are included.

## License and citation

Code under `scripts/` and `tests/` is licensed under the [MIT License](LICENSE). The proposal, pitch, protocols, reports and figures are licensed under [CC BY-NC-ND 4.0](LICENSE-CONTENT.md). You may share those materials unchanged with attribution; derivative works and commercial use require permission. Redistributed APEX data and Mercor's public scoring code retain their own terms, which are included alongside them. Use [CITATION.cff](CITATION.cff) to cite this work. The first public version was released on 14 September 2026, and the commit history records subsequent changes.
