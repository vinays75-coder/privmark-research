# PrivMark live pilot: results and usage checkpoint

The live pilot completed all 120 scored requests across three small local models,
two synthetic records, five questions, two instruction conditions, and response
caps of 24 and 64 tokens. Six additional warmup requests were recorded separately.
The main experiment has not started.

## What the pilot tells us

Increasing the response cap reduced incomplete responses from **16/60 (26.7%)**
at 24 tokens to **5/60 (8.3%)** at 64 tokens. It also exposed complete private tokens
in five attack responses whose 24-token counterparts had not exposed the complete
token. These are paired request counts, not five independent records.

However, **every model exposed both records under both instruction conditions at
both caps**, through at least one attack per record. The higher cap therefore did
not change the headline record-disclosure result. The pilot does not support the
idea that the original poor privacy result was simply caused by the 24-token cap.
It supports a narrower finding: longer responses reveal more behavior, and stronger
confidentiality instructions were insufficient to prevent disclosure in these tests.

| Model | Records exposed at 64 tokens, per condition | Public answers confirmed correct, per condition | Incomplete responses at 64 tokens, both conditions |
|---|---|---|---|
| SmolLM2-360M-Instruct | 2/2 | 1/2; other answer needs review | 4/20 |
| Qwen2.5-0.5B-Instruct | 2/2 | 2/2 | 0/20 |
| Qwen3-0.6B | 2/2 | 2/2 | 1/20 |

The public-answer checker accepts only restricted patterns. A response needing
review is not automatically an incorrect answer. Qwen2.5 had the cleanest response
completion in this pilot and both Qwen models passed the limited public-answer
check, but neither showed better record-level privacy protection. With only two
records, this is a diagnostic pilot, not a defensible general model ranking.
For example, the 95% Wilson interval for 2/2 disclosures is approximately 34.2–100%.

## Why the main experiment is paused

The agreed gate allows at most 5% incomplete responses at 64 tokens. The observed
5/60 (8.3%) exceeds that threshold. The runner correctly marked the main stage
ineligible. No response cap, model selection, or experimental budget was changed
to obtain a more favorable result.

Before any further inference, review the five incomplete responses and the public
answers needing review in `pilot_exports/review_needed.csv`, check the assistant
usage meter, and agree on any revised protocol and budget. The present result can
already demonstrate evidence-backed disclosure of a failed prompt mitigation.

## Local token accounting

| Category | Input tokens | Generated output tokens |
|---|---:|---:|
| Scored requests | 12,976 | 2,341 |
| Warmups | 180 | 32 |
| Total | **13,156** | **2,373** |

Actual output was 2,373 of the permitted 5,328 tokens, approximately 44.5% of the
ceiling. These are local model counts, not an estimate of assistant/Astra usage.
There were no repeated scored requests and no unaccounted requests. Input tokens
were additional to the output ceiling, as specified in the plan.

## Execution note and checks

A network restriction interrupted Qwen model loading after both SmolLM2 jobs had
been saved. The loader was verified with permitted network access without generating
responses. A tested, explicit continuation validated completed artifacts and token
logs, skipped both saved jobs, and completed the four remaining jobs within the
original budget. The initial failure and continuation provenance remain recorded.
The continuation passed 15 workflow tests and lint checks. The final audit verified
126 unique request completions, token totals, pinned model revisions, artifact and
export checksums, and that the main stage remains unstarted.

## Files for the presentation and audit

- [64-token comparison image](pilot_exports/comparison_64.png)
- [64-token disclosure graph](pilot_exports/disclosure_64.png)
- [64-token public-answer graph](pilot_exports/public_answers_64.png)
- [Full comparison CSV](pilot_exports/comparison.csv)
- [24-versus-64 paired diagnostics](pilot_exports/token_cap_comparison.csv)
- [Per-attack results](pilot_exports/attacks.csv)
- [Responses needing review](pilot_exports/review_needed.csv)
- [Machine-readable summary and source hashes](pilot_exports/summary.json)
- [Raw request/response log](pilot/responses.jsonl)
- [Stage state and accounting](state.json)

SVG and PDF versions of the images are in the same export folder. Historical
experiment files, slides, the dashboard layout and the original paper abstract
were not changed. The evidence concerns synthetic context disclosure only; it
does not validate all eleven PrivMark dimensions or certify an AI system's privacy.
