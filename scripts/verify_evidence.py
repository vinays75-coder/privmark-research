"""Validate committed measured artifacts, stage accounting and export checksums offline."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from privmark import load_artifact  # noqa: E402


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    results = ROOT / 'results'
    artifacts = list(results.glob('live_*_small.json'))
    study = results / 'bounded_study_v1'
    state = json.loads((study / 'state.json').read_text())
    plan = json.loads((study / 'plan.json').read_text())
    plan_digest = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    require(plan_digest == state['plan_sha256'], 'Plan digest mismatch')
    for stage, expected_calls in [('pilot', 120), ('main', 360)]:
        status = state['stages'][stage]
        require(status['status'] == 'complete', f'{stage} is incomplete')
        paths = sorted((study / stage).glob('m*.json'))
        artifacts.extend(paths)
        require(len(paths) == len(plan['stages'][stage]['jobs']), f'{stage}: wrong job count')
        events = [json.loads(line) for line in
                  (study / stage / 'responses.jsonl').read_text().splitlines()]
        responses = [e for e in events if e['event'] == 'response']
        started = [e for e in events if e['event'] == 'request_started']
        def key(event):
            return (event['job_id'], event['kind'],
                    json.dumps(event['reference'], sort_keys=True))
        lookup = {key(e): e for e in responses}
        require(len(lookup) == len(responses) == len(started), f'{stage}: repeated/missing calls')
        require(set(lookup) == {key(e) for e in started}, f'{stage}: request mismatch')
        for kind, count in [('scored', expected_calls), ('warmup', len(paths))]:
            selected = [e for e in responses if e['kind'] == kind]
            require(len(selected) == count, f'{stage}: wrong {kind} count')
            for label, field in [('input', 'prompt_tokens'), ('output', 'new_tokens')]:
                require(sum(e['result'][field] for e in selected) ==
                        status[f'{kind}_{label}_tokens_actual'], f'{stage}: token total mismatch')
            require(all(e['result']['new_tokens'] <= e['max_new_tokens'] for e in selected),
                    f'{stage}: response exceeded cap')
        for path in paths:
            data = load_artifact(path)
            job = next(j for j in plan['stages'][stage]['jobs']
                       if j['job_id'] == data['config']['job_id'])
            require(data['records'] == job['records'], f'{path.name}: fixture mismatch')
            model = data['models'][0]
            require(model['metadata']['resolved_revision'] == job['revision'],
                    f'{path.name}: revision mismatch')
            for condition, entry in model['conditions'].items():
                for trial in entry['trials']:
                    reference = {k: trial[k] for k in ('record_id', 'condition', 'attack')}
                    event = lookup[(job['job_id'], 'scored', json.dumps(reference, sort_keys=True))]
                    require(trial['text'] == event['result']['text'] and
                            trial['messages'] == event['messages'], f'{path.name}: log mismatch')
            if stage == 'main':
                require(data['config']['pilot_gate_decision'] == status['pilot_gate_decision'],
                        f'{path.name}: missing exception provenance')
        exports = study / f'{stage}_exports'
        for name, expected in json.loads((exports / 'checksums.json').read_text()).items():
            require(Path(name).name == name, 'Invalid export manifest path')
            require(hashlib.sha256((exports / name).read_bytes()).hexdigest() == expected,
                    f'Export checksum mismatch: {stage}/{name}')
    for path in artifacts:
        require(path.with_suffix('.sha256').exists(), f'Missing checksum: {path.name}')
        require(load_artifact(path)['mode'] == 'measured', f'Not measured: {path.name}')
    require(state['stages']['pilot']['main_eligible'] is False, 'Historical pilot gate changed')
    require(state['stages']['main']['pilot_gate_decision']['passed'] is False,
            'Historical gate exception changed')
    print(f'Verified {len(artifacts)} measured artifacts, unique calls, token totals and export hashes.')
    print('No model loading or inference was performed.')


if __name__ == '__main__':
    main()
