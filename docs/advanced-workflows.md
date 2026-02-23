# Local Playbook

This playbook is for validating many experiment variations with deterministic data.

## 1. Start from a clean state

```bash
rm -rf .djvrt/runs
```

Keep committed baselines and lockfile unless you intentionally re-baseline.

## 2. Seed deterministic data and scenarios

Use hook-based seeding through your project adapter:

```bash
python -m djvrt.django_seed_cli \
  --seeder myproject.vrt_seed:ProjectSeeder \
  --setup myproject.vrt_seed:setup_django \
  --options-builder myproject.vrt_seed:build_seed_options \
  --scenario-file .djvrt/scenarios.json \
  --manifest-file .djvrt/tree_shake_manifest.json \
  --max-variants-per-type 32
```

Useful knobs:

- `--include-type <type>` (repeatable): focus on a subset.
- `--max-variants-per-type N`: cap variant count per type.
- `--no-tree-shake`: control-only mode.
- `--option key=value`: adapter-specific overrides (requires `--options-builder`).

## 3. Build lockfile and baseline/check

```bash
uv run djvrt lock
uv run djvrt baseline --force
uv run djvrt check --retry-regressions 1
```

## 4. Inspect what actually ran

- `.djvrt/tree_shake_manifest.json` shows generated variants and coverage intent.
- `djvrt.lock.json` is the deterministic execution contract.
- `.djvrt/runs/<run_id>/report.html` is the visual review surface.

## 5. Scale to broad coverage safely

- Increase `--max-variants-per-type` in controlled increments.
- Run per-type passes with `--include-type` when a full sweep is too large.
- Keep scenario IDs stable so diffs stay readable across runs.

## Notes on "every permutation"

Tree-shaking is intentionally bounded: it generates control plus targeted mutations per type.

If you need true Cartesian combinations across multiple experiment types, implement that in your adapter `build_seed(...)` logic and keep a hard cap to avoid unbounded runtime.
