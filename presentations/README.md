# Evidence slides

The repository includes two editable-slide builders for the completed twelve-record
experiment. They read `results/bounded_study_v1/main_exports/comparison.csv` and do
not run models:

```bash
uv sync --locked --extra slides
uv run --no-sync python presentations/isope_2026/build_evidence_results.py
uv run --no-sync python presentations/isope_2026/build_simple_results.py
```

`build_evidence_results.py` produces the latest six-column comparison and protocol
diagram. `build_simple_results.py` produces the earlier two-column version.
Outputs are editable PPTX, PDF, PNG and speaker notes, ignored by Git.

Calibri is used when installed with Microsoft PowerPoint on macOS. Set
`PRIVMARK_FONT_DIR` to another directory containing `Calibri.ttf` and `Calibrib.ttf`
to use that font elsewhere. Otherwise the PDF renderer uses bundled Vera fonts;
PowerPoint still requests Calibri and may substitute a local font. PDF/PNG previews
come from a shared vector layout, not a native PowerPoint export. Rehearse the
PPTX in the presentation application before presenting.

Personal story decks, private presenter metadata and conversation material are
kept outside the repository's tracked-file set. The reference example about
Wisconsin breast cancer/DP-SGD is a visual inspiration only; its data and claims
are not measurements from this experiment.
