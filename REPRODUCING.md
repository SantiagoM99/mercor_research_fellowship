# Reproducing the preliminary evidence

Run commands from the repository root. The [evidence guide](analysis/README.md) explains which proposal claims each result supports. The commands below use checked-in data and recorded model responses; they do not call a model or require API credentials.

## Numerical checks and recorded-response analysis

Python 3 is sufficient for the audits, four recorded-response reports, parser controls and tests:

```sh
python3 scripts/audit_apex.py
python3 scripts/build_pilot_fixture.py
python3 scripts/measure_sensitivity.py
python3 scripts/verify_beta.py
python3 scripts/verify_followup_sources.py
python3 scripts/model_comparison.py report
python3 scripts/numeric_intervention.py report
python3 scripts/content_paraphrase.py report
python3 scripts/report_boundary_format.py
python3 scripts/check_extraction_controls.py
python3 scripts/check_extraction_scope.py
python3 -m unittest discover -s tests
```

Reports are written under analysis/. These commands preserve frozen requests and raw model outputs under runs/. The test suite covers numerical reproduction, response parsing, paired controls, missing results and acceptance-bound calculations.

## Figures and readable reports

Install the figure dependencies in a virtual environment:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-figures.txt
.venv/bin/python scripts/plot_acceptance_summary.py
.venv/bin/python scripts/plot_boundary_format.py
.venv/bin/python scripts/plot_comparison.py
.venv/bin/python scripts/plot_intervention.py
.venv/bin/python scripts/plot_content_paraphrase.py
python3 scripts/report_comparison.py
python3 scripts/report_intervention.py
python3 scripts/report_content_paraphrase.py
python3 scripts/write_boundary_report.py
python3 scripts/verify_content_results.py
```

The first two plotting commands regenerate the figures used in the proposal PDFs. The remaining plots support the detailed study reports. The content-study verifier checks frozen inputs, raw responses, model identity and independently recalculated metrics, then writes a current artifact inventory.

## Statistical implementation study

```sh
.venv/bin/python scripts/family_acceptance.py run
```

This reruns the seeded 24-scenario simulation in experiments/family-acceptance-v1.json using NumPy. It writes analysis/family-acceptance-v1.json. Simulations check the implementation under specified scenarios; they do not establish the sampling assumptions for a real APEX acceptance audit.

## New inference runs

Recomputing the recorded results does not require Ollama or model weights. New model runs do require a local Ollama server and the matching model configuration. The study entry points are scripts/model_comparison.py, scripts/numeric_intervention.py, scripts/content_paraphrase.py and scripts/boundary_format.py; each exposes its options through --help. Use a separate output directory for new inference so the submitted execution record remains intact. Changes to weights or runtime can change outputs even with the same prompts.

The data manifest records public-source URLs and SHA-256 hashes. scripts/fetch_apex.py can restore source data when needed, but fetching requires network access. The archived studies use the checked-in grading templates and selected public cases, not Mercor's private reference configuration.
