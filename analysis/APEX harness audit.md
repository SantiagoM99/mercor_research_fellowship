# Public APEX scoring-configuration audit

Static inspection of Mercor's public example at commit `6cbf3f43156bf332329abe76ed4a695fc71ec5b0`, compared with the downloaded dataset card at revision `e0db9513115f8d0449591fac3d77d4bdc1a98fef`. This is not an audit of Mercor's production service and does not establish that its published leaderboard is incorrect.

## Reproduction-sensitive differences

| Component | Dataset-card description | Pinned public example | Consequence for this proposal |
|---|---|---|---|
| Judge | Gemini 2.5 Pro, thinking on | `GRADING_MODEL = "gemini-2.5-flash"`; grading config passes temperature and token limit | Set and log the judge and reasoning settings explicitly. Confirm which configuration Mercor wants reproduced. |
| Grading context | Task prompt and source documents accompany the rubric | `grade(response, rubric_json)` supplies response and rubric; the default template interpolates only criterion description and response | Document context available to the judge. Filenames in a criterion's sources field are not equivalent to passing source contents. |
| Repeated solver runs | Eight | `NUMBER_OF_RUNS = 1` | Treat this as an example default, not a leaderboard reproduction. |
| Aggregation | Mean over runs | `calculate_statistics` computes median per task, then averages across tasks | State the aggregation rule and report sensitivity where repeats exist. With one run the two summaries coincide. |

Primary source: [dataset card](https://huggingface.co/datasets/mercor/APEX-v1-extended/blob/e0db9513115f8d0449591fac3d77d4bdc1a98fef/README.md). Public code: [example runner](https://github.com/Mercor-Intelligence/apex-evals/blob/6cbf3f43156bf332329abe76ed4a695fc71ec5b0/apex-evals-v1-extended/examples/run_with_hf.py), [grading prompt](https://github.com/Mercor-Intelligence/apex-evals/blob/6cbf3f43156bf332329abe76ed4a695fc71ec5b0/apex-evals-v1-extended/prompt/grading_prompt.txt).

## Two additional scoring behaviors to record

**Every criterion contributes one point.** The executor counts passing `autorating` values and divides by the number of criterion results. The `weight` field is retained as descriptive metadata, but does not numerically weight the aggregate. This supports an additional diagnostic comparing primary objectives with supporting requirements. It does not establish that equal weighting is inappropriate.

**Exhausted grading failures can contribute a failed criterion.** After retries, the executor creates a result with `grading_success=False` and `autorating=False`. Its aggregate includes those result objects. The example's `grade` helper checks that results exist, but does not reject each unsuccessful grading result. For a language-invariance study, explicitly track and retry or exclude infrastructure failures under a preregistered rule; otherwise technical failure may enter the language comparison. This behavior was identified by code inspection; no failure rate or actual leaderboard impact has been measured.

Source: [grading executor](https://github.com/Mercor-Intelligence/apex-evals/blob/6cbf3f43156bf332329abe76ed4a695fc71ec5b0/apex-evals-v1-extended/src/grading/executor.py). Local reference copies and hashes are in `data/apex-harness-reference/manifest.json`; these files have not been edited.

## Application-safe wording

> I audited the public development data and example harness, finding configuration differences that must be resolved before comparing languages. My first milestone is a versioned reference run whose model, context, aggregation, and failure handling are explicit.

Do not write that Mercor uses the wrong judge, that production omits evidence, or that these static observations already explain a model-score gap.
