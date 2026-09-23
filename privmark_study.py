"""Bounded, explicitly staged local experiment. Planning never loads a model."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path

from privmark import load_artifact, new_artifact, provenance, save_artifact
from privmark_assessment import assess_response
from privmark_data import ATTACKS, MODELS, PROTOCOL_VERSION, make_messages, make_records
from privmark_disclosure import build_disclosure
from privmark_metrics import paired_difference, summarize_trials

VERSION = "privmark-bounded-study-v1"
REVISIONS = dict(zip(MODELS, (
    "a10cc1512eabd3dde888204e902eca88bddb4951",
    "7ae557604adf67be50417f59c2c2f167def9a775",
    "c1899de289a04d12100db370d81485cdf75e47ca",
), strict=True))


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def make_plan():
    stages = {}
    for name, seeds, count, caps in (("pilot", [4242], 2, [24, 64]),
                                     ("main", [77, 123, 2026], 4, [64])):
        jobs = []
        for model_index, model_id in enumerate(MODELS):
            for seed in seeds:
                for cap in caps:
                    jobs.append({"job_id": f"m{model_index}-s{seed}-t{cap}",
                                 "model_id": model_id, "revision": REVISIONS[model_id],
                                 "seed": seed, "max_new_tokens": cap,
                                 "records": make_records(count, seed)})
        stages[name] = {"jobs": jobs, "scored_requests": len(jobs) * count * 10,
                        "scored_output_token_ceiling": sum(count * 10 * j["max_new_tokens"]
                                                           for j in jobs),
                        "warmup_requests": len(jobs), "warmup_output_token_ceiling": 8 * len(jobs)}
    return {"version": VERSION, "protocol": PROTOCOL_VERSION, "device": "cpu",
            "automatic_retries": 0, "warmup_cap": 8, "pilot_truncation_limit": 0.05,
            "stages": stages}


def create_plan(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    plan = make_plan()
    atomic_json(directory / "plan.json", plan)
    atomic_json(directory / "state.json", {"plan_sha256": digest(plan),
                "created_at": now(), "stages": {s: {"status": "not_started"}
                                                for s in plan["stages"]}})
    return plan


def load_plan(directory):
    plan = json.loads((directory / "plan.json").read_text())
    state = json.loads((directory / "state.json").read_text())
    if digest(plan) != state["plan_sha256"] or plan != make_plan():
        raise ValueError("The frozen plan differs from this protocol. Create a new plan for review.")
    return plan, state


def verify_continuation(directory, stage, plan, state):
    """Allow a manual continuation only at a fully accounted, completed-job boundary."""
    progress = state["stages"][stage]
    jobs = plan["stages"][stage]["jobs"]
    completed = progress.get("completed_jobs", [])
    if (progress.get("status") != "failed" or progress.get("unaccounted_requests") != 0
            or not completed or completed != [j["job_id"] for j in jobs[:len(completed)]]):
        raise ValueError("Continuation requires a failed stage at a clean completed-job boundary")
    expected = {"scored_requests_reserved": 0, "scored_output_tokens_reserved": 0,
                "warmup_requests_reserved": len(completed),
                "warmup_output_tokens_reserved": len(completed) * plan["warmup_cap"]}
    for job in jobs[:len(completed)]:
        path = directory / stage / f"{job['job_id']}.json"
        if not path.with_suffix(".sha256").exists():
            raise ValueError("Completed artifact checksum missing")
        artifact = load_artifact(path)
        if (artifact["config"].get("plan_sha256") != state["plan_sha256"]
                or artifact["records"] != job["records"]
                or artifact["config"].get("job_id") != job["job_id"]):
            raise ValueError("Completed artifact does not match the frozen plan")
        requests = len(job["records"]) * 2 * len(ATTACKS)
        expected["scored_requests_reserved"] += requests
        expected["scored_output_tokens_reserved"] += requests * job["max_new_tokens"]
    if any(progress[k] != value for k, value in expected.items()):
        raise ValueError("An unfinished job has spent reservations; continuation would repeat work")
    events = [json.loads(line) for line in
              (directory / stage / "responses.jsonl").read_text().splitlines()]
    for kind in ("scored", "warmup"):
        started = [e for e in events if e["event"] == "request_started" and e["kind"] == kind]
        responses = [e for e in events if e["event"] == "response" and e["kind"] == kind]
        if (len(started) != expected[f"{kind}_requests_reserved"] or
                len(responses) != len(started) or
                any(e["job_id"] not in completed for e in started + responses)):
            raise ValueError("Request log does not match the completed jobs")
        for token, field in (("input", "prompt_tokens"), ("output", "new_tokens")):
            if sum(e["result"][field] for e in responses) != progress[f"{kind}_{token}_tokens_actual"]:
                raise ValueError("Token accounting does not match the response log")
    return progress


def run_stage(directory, stage, *, backend_factory=None, continue_completed=False,
              truncation_override_reason=None):
    """Run one stage once. A crash/error consumes its reservation; never retry implicitly.

    The durable exclusive marker prevents concurrent runs and reruns even if a
    process dies before its state is written. Completed artifacts remain usable.
    """
    directory = Path(directory)
    plan, state = load_plan(directory)
    if stage not in plan["stages"]:
        raise ValueError("Unknown stage")
    if truncation_override_reason is not None and (
            stage != "main" or not isinstance(truncation_override_reason, str)
            or not truncation_override_reason.strip()):
        raise ValueError("A truncation override requires a nonempty reason and the main stage")
    if continue_completed:
        verify_continuation(directory, stage, plan, state)
    elif state["stages"][stage]["status"] != "not_started":
        raise ValueError("Stage already attempted; inspect saved evidence before planning more work.")
    if stage == "main":
        pilot = state["stages"]["pilot"]
        if pilot.get("status") != "complete":
            raise ValueError("Main stage requires a complete pilot")
        if not pilot.get("main_eligible", False) and not truncation_override_reason:
            raise ValueError("Main stage requires a complete pilot with <=5% truncation at 64 tokens.")
    # No model imports or network access occur until the explicit run command.
    if backend_factory is None:
        from privmark_backend import LocalModel
        backend_factory = LocalModel
    stage_dir = directory / stage
    budget = plan["stages"][stage]
    if continue_completed:
        # Exclusive marker permits only one explicit recovery and prevents races.
        with (stage_dir / "CONTINUATION_STARTED").open("x") as handle:
            handle.write(now() + "\n")
        progress = state["stages"][stage]
        progress["previous_failure"] = {"error": progress.pop("error", None),
                                        "finished_at": progress.pop("finished_at", None)}
        progress["status"] = "running"
        progress["continued_at"] = now()
        atomic_json(stage_dir / "continuation_provenance.json", provenance())
    else:
        stage_dir.mkdir(exist_ok=False)
        (stage_dir / "STARTED").write_text(now() + "\n")
        progress = {"status": "running", "started_at": now(), "completed_jobs": [],
                "scored_requests_reserved": 0, "scored_output_tokens_reserved": 0,
                "warmup_requests_reserved": 0, "warmup_output_tokens_reserved": 0,
                "scored_output_tokens_actual": 0, "warmup_output_tokens_actual": 0,
                "scored_input_tokens_actual": 0, "warmup_input_tokens_actual": 0,
                "cap64_truncated": 0, "cap64_responses": 0,
                "unaccounted_requests": 0}
        if stage == "main":
            progress["pilot_gate_decision"] = {
                "passed": pilot["main_eligible"],
                "observed_truncation": pilot["cap64_truncated"] / pilot["cap64_responses"],
                "threshold": plan["pilot_truncation_limit"],
                "override_reason": truncation_override_reason,
                "decided_at": now(),
                "budget_changed": False,
            }
    state["stages"][stage] = progress
    atomic_json(directory / "state.json", state)
    if not continue_completed:
        atomic_json(stage_dir / "provenance.json", provenance())

    def event(value):
        with (stage_dir / "responses.jsonl").open("a") as handle:
            handle.write(json.dumps({"timestamp": now(), **value}, allow_nan=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    def generate(backend, job, messages, kind, reference):
        cap = plan["warmup_cap"] if kind == "warmup" else job["max_new_tokens"]
        requests_key = f"{kind}_requests_reserved"
        tokens_key = f"{kind}_output_tokens_reserved"
        if (progress[requests_key] + 1 > budget[f"{kind}_requests"] or
                progress[tokens_key] + cap > budget[f"{kind}_output_token_ceiling"]):
            raise RuntimeError("Frozen stage budget exhausted")
        progress[requests_key] += 1
        progress[tokens_key] += cap
        progress["unaccounted_requests"] += 1
        atomic_json(directory / "state.json", state)
        request = {"job_id": job["job_id"], "kind": kind, "reference": reference,
                   "max_new_tokens": cap, "messages": messages}
        event({"event": "request_started", **request})
        backend.max_new_tokens = cap
        result = backend.generate(messages)
        event({"event": "response", **request, "result": result})
        for key in ("new_tokens", "prompt_tokens"):
            if type(result.get(key)) is not int or result[key] < 0:
                raise RuntimeError(f"Backend did not provide valid {key}")
        if result["new_tokens"] > cap:
            raise RuntimeError("Backend violated the requested output cap; stopping")
        progress[f"{kind}_output_tokens_actual"] += result["new_tokens"]
        progress[f"{kind}_input_tokens_actual"] += result["prompt_tokens"]
        progress["unaccounted_requests"] -= 1
        if kind == "scored" and cap == 64:
            progress["cap64_responses"] += 1
            progress["cap64_truncated"] += int(result["truncated"])
        atomic_json(directory / "state.json", state)
        return result

    backend = None
    try:
        for job in budget["jobs"]:
            if job["job_id"] in progress["completed_jobs"]:
                continue
            backend = backend_factory(job["model_id"], revision=job["revision"],
                                      device=plan["device"], seed=job["seed"],
                                      max_new_tokens=job["max_new_tokens"])
            event({"event": "model_loaded", "job_id": job["job_id"],
                   "metadata": backend.metadata})
            generate(backend, job, [{"role": "user", "content": "Reply with the word ready."}],
                     "warmup", {})
            trials = {"baseline": [], "hardened": []}
            requests = [(record, condition, attack) for record in job["records"]
                        for condition in trials for attack in ATTACKS]
            random.Random(job["seed"]).shuffle(requests)
            for record, condition, attack in requests:
                reference = {"record_id": record["record_id"], "condition": condition,
                             "attack": attack}
                messages = make_messages(record, condition, attack)
                result = generate(backend, job, messages, "scored", reference)
                assessment = assess_response(result["text"], record, result["truncated"])
                trials[condition].append({**reference, "messages": messages, **result,
                    "leaked": assessment["full_disclosure"], "assessment": assessment,
                    "utility_ok": result["text"].strip().strip(".!").lower()
                                  == record["public_value"]})
            model = {"model_id": job["model_id"], "status": "complete",
                     "metadata": dict(backend.metadata), "memorization": {"status": "not evaluated"},
                     "conditions": {condition: {"trials": rows, "summary": summarize_trials(rows)}
                                    for condition, rows in trials.items()},
                     "paired_difference": paired_difference(trials["baseline"], trials["hardened"],
                                                            job["seed"])}
            model["disclosures"] = build_disclosure(model)
            artifact = new_artifact("measured", {"study_version": VERSION, "stage": stage,
                "plan_sha256": state["plan_sha256"], "job_id": job["job_id"],
                "seed": job["seed"], "max_new_tokens": job["max_new_tokens"]}, job["records"])
            if "pilot_gate_decision" in progress:
                artifact["config"]["pilot_gate_decision"] = progress["pilot_gate_decision"]
            artifact["models"] = [model]
            save_artifact(artifact, stage_dir / f"{job['job_id']}.json")
            backend.close()
            backend = None
            progress["completed_jobs"].append(job["job_id"])
            atomic_json(directory / "state.json", state)
            print(f"Saved {stage}/{job['job_id']}.json ({len(progress['completed_jobs'])}"
                  f"/{len(budget['jobs'])} jobs)", flush=True)
        progress["status"] = "complete"
        if stage == "pilot":
            progress["main_eligible"] = (progress["cap64_truncated"] /
                                          progress["cap64_responses"] <=
                                          plan["pilot_truncation_limit"])
    except BaseException as exc:
        progress["status"] = "failed"
        progress["error"] = f"{type(exc).__name__}: {exc}"
        event({"event": "stage_failed", "error": progress["error"]})
        raise
    finally:
        try:
            if backend is not None:
                backend.close()
        finally:
            progress["finished_at"] = now()
            atomic_json(directory / "state.json", state)
    return progress


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan", help="Write the fixed budget; no inference")
    plan.add_argument("--output", type=Path, required=True)
    run = sub.add_parser("run", help="Run only the explicitly selected stage")
    run.add_argument("--study", type=Path, required=True)
    run.add_argument("--stage", choices=["pilot", "main"], required=True)
    run.add_argument("--continue-completed", action="store_true",
                     help="Explicit recovery only if no requests in an unfinished job were spent")
    run.add_argument("--truncation-override-reason",
                     help="Record an explicit decision to proceed despite a failed pilot gate; "
                          "does not alter the token budget or the pilot result")
    args = parser.parse_args()
    if args.command == "plan":
        plan = create_plan(args.output)
        for name, budget in plan["stages"].items():
            print(f"{name}: {budget['scored_requests']} scored requests, "
                  f"<= {budget['scored_output_token_ceiling']} scored output tokens; "
                  f"warmups <= {budget['warmup_output_token_ceiling']} additional tokens")
        print("Plan saved. No model loaded. Check usage before explicitly running the pilot.")
    else:
        result = run_stage(args.study, args.stage, continue_completed=args.continue_completed,
                           truncation_override_reason=args.truncation_override_reason)
        print(f"Stage {result['status']}. Stopped; no following stage runs automatically.")
        if args.stage == "pilot":
            print(f"Main eligible on truncation check: {result['main_eligible']}. "
                  "Review the report and usage meter before choosing the next step.")


if __name__ == "__main__":
    main()
