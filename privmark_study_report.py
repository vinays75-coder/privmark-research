"""Export auditable comparison tables and light scientific figures without inference."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
from pathlib import Path

from privmark import load_artifact, provenance
from privmark_assessment import STUDY_ASSESSMENT_VERSION, assess_response
from privmark_metrics import paired_difference, rate_summary, summarize_trials

SCOPE = ("Controlled synthetic context disclosure only. Four fixed attack families; "
         "stronger instructions are a prompt mitigation, not an access-control guarantee. "
         "This does not validate all eleven PrivMark dimensions or establish a general model ranking.")


def collect(paths):
    groups = {}
    sources = []
    stage_set = set()
    for path in paths:
        artifact = load_artifact(path)
        if artifact["mode"] != "measured":
            raise ValueError("Slide exports require measured artifacts, not simulated demonstrations.")
        stage = artifact["config"].get("stage", "historical")
        stage_set.add(stage)
        sources.append({"path": str(path.resolve()), "run_id": artifact["run_id"],
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "pilot_gate_decision": artifact["config"].get("pilot_gate_decision")})
        for model in artifact["models"]:
            if model["status"] != "complete":
                raise ValueError("Cannot export a complete comparison from a failed model artifact.")
            cap = model["metadata"].get("max_new_tokens", artifact["config"].get("max_new_tokens"))
            if not isinstance(cap, int):
                raise ValueError("Response-token cap missing from artifact")
            key = (model["model_id"], cap)
            group = groups.setdefault(key, {"model_id": key[0], "cap": cap, "records": {},
                "conditions": {"baseline": [], "hardened": []},
                "revision": model["metadata"].get("resolved_revision"), "settings": None})
            settings = {k: model["metadata"].get(k) for k in
                        ("resolved_revision", "device", "dtype", "decoding")}
            if group["settings"] is not None and settings != group["settings"]:
                raise ValueError("Cannot pool different model revisions or inference settings")
            group["settings"] = settings
            record_map = {}
            for record in artifact["records"]:
                # Same records shared by models and caps; independent seed batches pool once.
                identity = record["secret"]
                if identity in group["records"]:
                    raise ValueError("Duplicate records would inflate the effective sample size")
                group["records"][identity] = record
                record_map[record["record_id"]] = identity
            for condition, entry in model["conditions"].items():
                for trial in entry["trials"]:
                    identity = record_map[trial["record_id"]]
                    group["conditions"][condition].append({**trial, "record_id": identity,
                        "source_run": artifact["run_id"], "source_record_id": trial["record_id"],
                        "assessment": assess_response(trial["text"], group["records"][identity],
                                                      trial["truncated"])})
    if len(stage_set) != 1 or not groups:
        raise ValueError("Report one nonempty stage at a time; never pool pilot and main")
    # Comparisons require identical fixtures for every model and token cap.
    fixtures = [g["records"] for g in groups.values()]
    if any(records != fixtures[0] for records in fixtures[1:]):
        raise ValueError("Compared models/caps do not have the same synthetic records")
    return groups, sources, next(iter(stage_set))


def summarize(groups):
    rows, attack_rows, review, pairs = [], [], [], []
    for (model_id, cap), group in sorted(groups.items()):
        for condition, trials in group["conditions"].items():
            summary = summarize_trials(trials)
            public = [t for t in trials if t["attack"] == "utility"]
            answer = rate_summary([t["assessment"]["public_answer"] == "confirmed_correct"
                                   for t in public])
            row = {"model": model_id, "cap": cap, "condition": condition,
                   "records": len(group["records"]),
                   "disclosed_records": summary["leakage"]["successes"],
                   "disclosure_rate": summary["leakage"]["rate"],
                   "disclosure_low": summary["leakage"]["low"],
                   "disclosure_high": summary["leakage"]["high"],
                   "public_confirmed_correct": answer["successes"],
                   "public_correct_rate": answer["rate"],
                   "public_correct_low": answer["low"], "public_correct_high": answer["high"],
                   "public_confirmed_incorrect": sum(t["assessment"]["public_answer"] ==
                                                      "confirmed_incorrect" for t in public),
                   "public_needs_review": sum(t["assessment"]["public_answer"] == "needs_review"
                                              for t in public),
                   "exact_format_correct": sum(t["utility_ok"] for t in public),
                   "partial_flags": sum(t["assessment"]["partial_disclosure_flag"] for t in trials),
                   "truncated": summary["truncated"], "responses": len(trials),
                   "output_tokens": sum(t["new_tokens"] for t in trials),
                   "input_tokens": sum(t["prompt_tokens"] for t in trials)
                                    if all("prompt_tokens" in t for t in trials) else None,
                   "median_latency_s": statistics.median(t["latency_s"] for t in trials)}
            rows.append(row)
            for attack, result in summary["by_attack"].items():
                attack_rows.append({"model": model_id, "cap": cap, "condition": condition,
                                    "attack": attack, **result})
            for trial in trials:
                assessment = trial["assessment"]
                if (assessment["partial_disclosure_flag"] or trial["truncated"] or
                        (trial["attack"] == "utility" and
                         assessment["public_answer"] == "needs_review")):
                    review.append({"model": model_id, "cap": cap, "condition": condition,
                                   "source_run": trial["source_run"],
                                   "record_id": trial["source_record_id"], "attack": trial["attack"],
                                   "text": trial["text"], **assessment})
        baseline, hardened = (group["conditions"][c] for c in ("baseline", "hardened"))
        pairs.append({"model": model_id, "cap": cap, "metric": "record disclosure",
                      **paired_difference(baseline, hardened, 2026)})
        public_arms = [[{**t, "attack": "public_correct",
                        "leaked": t["assessment"]["public_answer"] == "confirmed_correct"}
                       for t in arm if t["attack"] == "utility"] for arm in (baseline, hardened)]
        pairs.append({"model": model_id, "cap": cap, "metric": "confirmed public answers",
                      **paired_difference(*public_arms, 2026)})
    return rows, attack_rows, review, pairs


def write_csv(path, rows, fallback):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else fallback)
        writer.writeheader()
        writer.writerows(rows)


def cap_comparison(groups):
    """Within-record diagnostics for the pilot's 24 versus 64 token comparison."""
    changes = []
    for model in sorted({key[0] for key in groups}):
        if (model, 24) not in groups or (model, 64) not in groups:
            continue
        for condition in ("baseline", "hardened"):
            left, right = (groups[(model, cap)]["conditions"][condition] for cap in (24, 64))
            short = {(t["record_id"], t["attack"]): t for t in left}
            longer = {(t["record_id"], t["attack"]): t for t in right}
            changes.append({"model": model, "condition": condition, "responses": len(left),
                "truncated_24": sum(t["truncated"] for t in left),
                "truncated_64": sum(t["truncated"] for t in right),
                "new_full_disclosures_at_64": sum(not short[k]["leaked"] and longer[k]["leaked"]
                                                   for k in short if k[1] != "utility"),
                "full_disclosures_only_at_24": sum(short[k]["leaked"] and not longer[k]["leaked"]
                                                   for k in short if k[1] != "utility"),
                "public_confirmed_24": sum(t["assessment"]["public_answer"] == "confirmed_correct"
                                             for t in left if t["attack"] == "utility"),
                "public_confirmed_64": sum(t["assessment"]["public_answer"] == "confirmed_correct"
                                             for t in right if t["attack"] == "utility")})
    return changes


def figures(directory, rows, stage):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    for cap in sorted({r["cap"] for r in rows}):
        selected = [r for r in rows if r["cap"] == cap]
        names = sorted({r["model"] for r in selected})
        n = selected[0]["records"]
        for metric, title, fields in (
            ("disclosure", "Did the system reveal the complete private token?",
             ("disclosure_rate", "disclosure_low", "disclosure_high", "disclosed_records")),
            ("public_answers", "Could it still answer the public question?",
             ("public_correct_rate", "public_correct_low", "public_correct_high",
              "public_confirmed_correct")),
        ):
            fig, ax = plt.subplots(figsize=(11, 5.6), layout="constrained")
            for index, (condition, label, color) in enumerate((
                ("baseline", "Basic confidentiality instruction", "#78909c"),
                ("hardened", "Stronger confidentiality instruction", "#007f86"),
            )):
                data = [next(r for r in selected if r["model"] == name and
                             r["condition"] == condition) for name in names]
                values = np.array([r[fields[0]] for r in data]) * 100
                errors = np.array([[max(0, r[fields[0]] - r[fields[1]]) * 100 for r in data],
                                   [max(0, r[fields[2]] - r[fields[0]]) * 100 for r in data]])
                x = np.arange(len(names)) + (index - 0.5) * .36
                ax.bar(x, values, .34, color=color, label=label, yerr=errors, capsize=4)
                for point, value, row in zip(x, values, data, strict=True):
                    ax.text(point, value + 4, f"{row[fields[3]]}/{n}", ha="center", fontsize=11)
            ax.set_xticks(np.arange(len(names)), [name.split("/")[-1] for name in names])
            ax.set_ylim(0, 130)
            ax.set_yticks([0, 25, 50, 75, 100])
            ax.set_ylabel("Records (%)")
            ax.set_title(f"{title}\n{stage.capitalize()}: {n} records per model; {cap}-token cap",
                         loc="left", fontsize=15, pad=12)
            ax.legend(loc="upper center", ncol=2, fontsize=9)
            ax.spines[["top", "right"]].set_visible(False)
            fig.supxlabel("95% Wilson intervals; synthetic context only. Public answers use restricted patterns.\n"
                          "See comparison table for incomplete responses and cases needing review.", fontsize=9)
            for extension in ("png", "svg", "pdf"):
                fig.savefig(directory / f"{metric}_{cap}.{extension}", dpi=300, facecolor="white")
            plt.close(fig)
        cells = [[r["model"].split("/")[-1], "Basic" if r["condition"] == "baseline" else "Stronger",
                  f"{r['disclosed_records']}/{n}", f"{r['public_confirmed_correct']}/{n}",
                  str(r["public_needs_review"]), f"{r['truncated']}/{r['responses']}"] for r in selected]
        fig, ax = plt.subplots(figsize=(13, 4.5), layout="constrained")
        ax.axis("off")
        table = ax.table(cellText=cells, colLabels=["Model", "Instruction", "Disclosed", "Public correct*",
                                                  "Public review", "Truncated"], loc="center",
                         colWidths=[.29, .14, .13, .16, .14, .14], cellLoc="center")
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 2)
        for (r, c), cell in table.get_celld().items():
            cell.set_facecolor("#e1eff0" if r == 0 else "white")
            cell.set_edgecolor("#cbd5db")
        ax.set_title(f"PrivMark evidence summary — {stage}, {cap}-token cap", loc="left", fontsize=16)
        fig.supxlabel("*Confirmed by restricted answer patterns. Partial flags and uncertainty are in comparison.csv.\n"
                      "Synthetic context experiment; no overall privacy score or certification.", fontsize=9)
        for extension in ("png", "svg", "pdf"):
            fig.savefig(directory / f"comparison_{cap}.{extension}", dpi=300, facecolor="white")
        plt.close(fig)


def export_report(paths, output):
    paths = [Path(p) for p in paths]
    groups, sources, stage = collect(paths)
    rows, attacks, review, pairs = summarize(groups)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    write_csv(output / "comparison.csv", rows, [])
    write_csv(output / "attacks.csv", attacks, [])
    write_csv(output / "review_needed.csv", review, ["model", "record_id", "text"])
    write_csv(output / "paired_changes.csv", pairs, [])
    cap_changes = cap_comparison(groups)
    if cap_changes:
        write_csv(output / "token_cap_comparison.csv", cap_changes, [])
    summary = {"stage": stage, "assessment_version": STUDY_ASSESSMENT_VERSION,
               "scope": SCOPE, "sources": sources, "provenance": provenance(),
               "comparison": rows, "paired_changes": pairs, "token_cap_comparison": cap_changes}
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = [f"# PrivMark: {stage} evidence", "", SCOPE, "",
             "Positive disclosure changes mean more leakage with stronger instructions. "
             "Positive public-answer changes mean more confirmed correct answers. "
             "Paired intervals use 2,000 record bootstrap samples. Degenerate intervals do not "
             "mean zero population uncertainty. Seeds create different synthetic fixtures, "
             "not repeated evidence from the same records.", "",
             "A longer answer budget can reveal previously cut-off behavior; it cannot guarantee "
             "a better outcome. If all models leak, the supported finding is that these prompt "
             "mitigations were insufficient in this scenario. Do not select a winner from ties.", "",
             "| Model | Cap | Instruction | Complete token exposed | Public answer confirmed | "
             "Needs review | Partial flags | Truncated |", "|---|---:|---|---:|---:|---:|---:|---:|"]
    for row in rows:
        n = row["records"]
        lines.append(f"| {row['model']} | {row['cap']} | {row['condition']} | "
                     f"{row['disclosed_records']}/{n} | {row['public_confirmed_correct']}/{n} | "
                     f"{row['public_needs_review']} | {row['partial_flags']} | "
                     f"{row['truncated']}/{row['responses']} |")
    lines += ["", "See comparison.csv for 95% Wilson intervals, formatting, input/output tokens "
              "and latency. Missing historical input-token counts remain blank. Warmups are "
              "excluded here and accounted separately in the study state and JSONL logs.", "",
              "Full normalized-token matching can miss encoded disclosures. Partial flags are "
              "a prefix heuristic, not a comprehensive detector. Unrecognized or truncated public "
              "answers need review; they are not automatically declared wrong.", "", "## Sources", ""]
    lines += [f"- `{s['path']}` — SHA256 `{s['sha256']}`" for s in sources]
    deviations = {json.dumps(s["pilot_gate_decision"], sort_keys=True) for s in sources
                  if s.get("pilot_gate_decision") and not s["pilot_gate_decision"]["passed"]}
    if deviations:
        lines += ["", "## Pilot gate exception", "",
                  "This main experiment proceeded by explicit decision despite the pilot exceeding "
                  "the truncation threshold. The fixed output budget was retained. Incomplete "
                  "responses remain flagged; absence of a detected disclosure is not proof of safety."]
        for entry in sorted(deviations):
            decision = json.loads(entry)
            lines.append(f"- Pilot truncation: {decision['observed_truncation']:.1%}; "
                         f"threshold: {decision['threshold']:.1%}. "
                         f"Recorded reason: {decision['override_reason']}")
    (output / "summary.md").write_text("\n".join(lines) + "\n")
    table_start = next(i for i, line in enumerate(lines) if line.startswith("| Model |"))
    (output / "comparison.md").write_text(
        "\n".join(lines[table_start:table_start + len(rows) + 2]) + "\n")
    figures(output, rows, stage)
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(output.iterdir())}
    (output / "checksums.json").write_text(json.dumps(hashes, indent=2) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, nargs="+", required=True,
                        help="Complete measured artifact files from ONE stage")
    parser.add_argument("--output", type=Path, required=True, help="A new export directory")
    args = parser.parse_args()
    export_report(args.input, args.output)
    print(f"Saved tables, figures and source checksums in {args.output}; no inference performed.")


if __name__ == "__main__":
    main()
