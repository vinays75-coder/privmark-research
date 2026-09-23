# Reproduce the 12-record local-model experiment

This guide covers the completed main experiment, its diagnostic pilot, and how
to reproduce the protocol in a **new directory**. Opening saved evidence and
exporting figures do not run models. The committed run is immutable and complete.

## What was tested

PrivMark translates privacy evidence into understandable disclosures; it is not
itself a privacy safeguard. In this example, an assistant receives a public
project color and a fictional private token in its system message. It is told to
keep the token confidential. Four user questions attempt disclosure; a fifth
asks for the public color. Both conditions supply the secret to the model.

The basic condition prohibits disclosure. The stronger condition adds instructions
against authorization claims, instruction overrides and record exports. These
are prompt mitigations, not enforced authorization or data-access controls.

| Model | Hugging Face identifier | Pinned revision |
|---|---|---|
| SmolLM2-360M-Instruct | `HuggingFaceTB/SmolLM2-360M-Instruct` | `a10cc1512eabd3dde888204e902eca88bddb4951` |
| Qwen2.5-0.5B-Instruct | `Qwen/Qwen2.5-0.5B-Instruct` | `7ae557604adf67be50417f59c2c2f167def9a775` |
| Qwen3-0.6B | `Qwen/Qwen3-0.6B` | `c1899de289a04d12100db370d81485cdf75e47ca` |

Models execute sequentially on CPU through Transformers/PyTorch, with greedy
non-thinking generation. Ollama is not used. This is actual local inference on
synthetic inputs, not simulated outputs. Model weights are downloaded separately
and must not be committed. Available memory and runtime depend on the machine;
no universal RAM or runtime guarantee is made.

## Completed results

| Model | Records exposed: basic / stronger | Public answers confirmed: basic / stronger | Cut-off responses |
|---|---|---|---|
| SmolLM2-360M-Instruct | 12/12 / 12/12 | 8/12 / 9/12 | 26/120 |
| Qwen2.5-0.5B-Instruct | 12/12 / 12/12 | 12/12 / 12/12 | 0/120 |
| Qwen3-0.6B | 12/12 / 12/12 | 12/12 / 12/12 | 4/120 |

Each exposed record leaked a full token under at least one attack. **This does not
mean every response leaked.** There are twelve records per model/condition, not
360 independent privacy cases. The 95% Wilson interval for 12/12 is approximately
75.8–100%, under this limited synthetic protocol.

Public-answer confirmation uses restricted patterns; exact formatting is scored
separately. A later raw-response audit established that SmolLM2's seven public
answers flagged for review actually returned the secret alone: 4/12 basic and
3/12 stronger. This unintended disclosure on benign questions is not displayed
as a separate metric in the original comparison CSV. The original scores and raw
files are preserved; do not describe these seven responses as harmless formatting
variants. Both Qwen models had zero full-token disclosures on the public questions.

All 24 SmolLM2 JSON-transformation responses were cut off. Its transformation
count falling from 8/12 to 0/12 is therefore not proof of protection. Other attacks
exposed every record. Overall, 30/360 main responses were cut off (8.3%).

The result is a narrow failure of prompt confidentiality. It does not evaluate
training-data extraction, actual patient/customer records, encryption, deletion,
production controls, formal differential privacy, or all eleven PrivMark dimensions.
There is no overall privacy winner. Qwen2.5 had the cleanest answer-completion
result, not superior record-level privacy.

## Inspect existing evidence without inference

From the repository root:

```bash
uv sync --locked --extra exports
uv run --no-sync python scripts/verify_evidence.py
```

- [Main readout](../results/bounded_study_v1/MAIN_READOUT.md)
- [Main comparison CSV](../results/bounded_study_v1/main_exports/comparison.csv)
- [Per-attack results](../results/bounded_study_v1/main_exports/attacks.csv)
- [Raw main requests/responses](../results/bounded_study_v1/main/responses.jsonl)
- [Frozen plan](../results/bounded_study_v1/plan.json)
- [State and token accounting](../results/bounded_study_v1/state.json)
- [Pilot cap comparison](../results/bounded_study_v1/pilot_exports/token_cap_comparison.csv)

The dashboard defaults to selecting top-level saved artifacts. The aggregate
12-record comparison is in the main export folder; selecting the historical
`live_three_models_small.json` shows the older four-record experiment instead.

Regenerate main figures and tables into a new, ignored directory:

```bash
uv run --no-sync python privmark_study_report.py \
  --input results/bounded_study_v1/main/m*.json \
  --output results/runs/main-export-review
```

This exports light PNG, SVG and PDF charts/tables, CSV/Markdown summaries, review
lists and checksums. It invokes no model and refuses to overwrite an existing
output directory. Original exported summaries retain the producing machine's
historical source paths; use repository-relative links here to navigate the clone.

## Run a fresh reproduction, deliberately

Python 3.11–3.13 and uv are required. Install locked dependencies as above. Initial
model loading may need network access for the pinned weights and metadata. Do not
run this section merely to inspect results or execute CI.

### 1. Create a plan: no inference

```bash
uv run --no-sync python privmark_study.py plan --output results/runs/reproduction-001
```

The plan fixes these budgets:

| Stage | Fixtures per model | Caps | Scored calls | Max scored output | Warmup calls / max output |
|---|---:|---|---:|---:|---:|
| Pilot | 2, seed 4242 | 24 and 64 | 120 | 5,280 | 6 / 48 |
| Main | 12, seeds 77/123/2026 × 4 | 64 | 360 | 23,040 | 9 / 72 |
| Combined | Separate pilot/main fixtures | | 480 | 28,320 | 15 / 120 |

Combined output ceiling including warmups: **28,440 tokens**. Input tokens are
additional and logged. These are local inference counts, not an estimate of any
coding assistant's quota or a hosted inference bill. Review the plan and available
resources before running the next command.

### 2. Run the pilot and stop

```bash
uv run --no-sync python privmark_study.py run \
  --study results/runs/reproduction-001 --stage pilot
uv run --no-sync python privmark_study_report.py \
  --input results/runs/reproduction-001/pilot/m*.json \
  --output results/runs/reproduction-001/pilot_exports
```

The pilot compares the same records and prompts at both caps. It does not chain
into main. Inspect incomplete answers, full/partial disclosures, public-answer
review flags and actual spend before proceeding.

The original pilot reduced cut-offs from 16/60 at 24 tokens to 5/60 at 64 tokens,
but every model still exposed both records. A longer cap did not explain away
the headline privacy failures.

### 3. Run the main stage after review

Normally main requires a completed pilot with at most 5% cut-offs at 64 tokens:

```bash
uv run --no-sync python privmark_study.py run \
  --study results/runs/reproduction-001 --stage main
```

**The committed pilot failed that gate: 5/60 = 8.3%.** The researcher explicitly
chose to proceed at the same budget. Every main artifact records this exception;
the original failed pilot was not relabeled as passing. If making the same explicit
decision for a fresh reproduction, supply a reason:

```bash
uv run --no-sync python privmark_study.py run \
  --study results/runs/reproduction-001 --stage main \
  --truncation-override-reason 'After reviewing pilot truncation, proceed at the original fixed budget; retain incomplete-response flags and report this exception.'
```

This option is a documented protocol deviation, not an automatic recommendation.
It does not increase caps or erase uncertainty. Then export:

```bash
uv run --no-sync python privmark_study_report.py \
  --input results/runs/reproduction-001/main/m*.json \
  --output results/runs/reproduction-001/main_exports
```

### Failure and recovery behavior

There are no automatic inference retries. Requests reserve their maximum output
budget before generation. Response logs are flushed to disk, completed jobs are
saved separately, and failed/in-flight reservations are retained. Do not edit
state or delete markers to rerun an attempted stage.

The original pilot encountered a metadata-network failure before Qwen's first
request. An explicit `--continue-completed` recovery verified checksums and token
logs, skipped both finished SmolLM2 jobs, and completed the rest. This one-time
recovery only accepts a clean completed-job boundary; it rejects partial jobs or
unaccounted requests. A main continuation must retain any required gate exception.

## Actual recorded token use

| Stage | Input including warmups | Output including warmups |
|---|---:|---:|
| Pilot | 13,156 | 2,373 |
| Main | 39,248 | 8,312 |
| Total | 52,404 | 10,685 |

Prompt hashes, revisions, records, raw responses, decoding, timings and package/
source provenance are retained. Greedy settings do not guarantee identical results
on another software/hardware stack. Checksums verify bytes, not independent
scientific truth. Do not mix pilot and main records to inflate the main sample.

## Suggested next research step

Before expanding inference, make benign-question leakage explicit in reports and
compare prompt-only confidentiality with a genuine application control, such as
excluding unnecessary private context. Use more diverse scenarios if claiming
broader privacy behavior. Preserve old data and label revised scoring/protocols.
