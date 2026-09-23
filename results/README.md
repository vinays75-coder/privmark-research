# Reviewed research evidence

The committed artifacts contain **synthetic records and actual local model
responses**. `PM-...` values are fictional canaries, not real credentials.

- `live_*_small.json` and sidecars: original four-record comparison.
- `bounded_study_v1/pilot/`: two-record 24-versus-64-token diagnostic study.
- `bounded_study_v1/main/`: twelve fresh records per model, 360 scored responses.
- `bounded_study_v1/*_exports/`: saved derived tables, charts and checksum manifests.

See [the reproduction guide](../docs/EXPERIMENT_12_RECORDS.md). The pilot readout
records its then-pending main stage; the main readout and state show subsequent
completion. The main stage proceeded with an explicitly documented exception to
the pilot truncation gate. No independent audit or broader privacy certification
is claimed.

Original provenance can contain historical timestamps, local paths, software
versions and source hashes. These files have not been rewritten to disguise the
execution history. `.gitattributes` preserves their exact bytes. Do not reformat
measured JSON or adjust stored scores. Add any corrected interpretation separately.

Future runs should go under `results/runs/`, ignored by default. The explicit
`.gitignore` allowlist keeps caches, demo exports and accidental local runs out of
Git. Review new evidence before deliberately adding it to that allowlist.
