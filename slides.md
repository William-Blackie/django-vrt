# DjangoCon 2026: Deterministic Visual Regression Testing for Django

## Slide 1: Title

**Deterministic Visual Regression at Django Scale**  
`django-vrt`: package-first, CI-safe, and fast enough for high-change teams

Speaker framing:

- We needed speed for large UI change sets.
- We also needed confidence to merge without manual screenshot policing.
- The constraint: keep it Python-first and reusable across projects.

---

## Slide 2: The Problem

Why typical screenshot testing breaks down on complex Django products:

- Too many routes and dynamic states.
- Non-deterministic data causes false positives.
- Local vs CI drift causes "works on my machine" visual noise.
- Experiment flags multiply combinations quickly.

Key requirement:

`determinism > convenience`

---

## Slide 3: Design Goals

- One installable package from PyPI.
- Minimal project-side code (config + extension hooks).
- Lockfile-driven matrix for repeatability.
- Deterministic data and auth setup.
- CI outputs people can actually debug.

---

## Slide 4: High-Level Architecture

```text
[djvrt.toml + scenarios.json]
              |
              v
          [djvrt lock]
              |
              v
 [djvrt.lock.json (contract)]
       |                 |
       v                 v
[djvrt baseline]   [djvrt check]
       |                 |
       v                 v
[.djvrt/baselines]  [.djvrt/runs/<run_id>]
                              |
                              v
            [summary.json / junit.xml / report.html]
```

Explanation:

- `lock` is the boundary between config intent and executable matrix.
- Baseline is hash-scoped, so config/matrix changes never silently reuse old images.

---

## Slide 5: Deterministic Contract

`djvrt.lock.json` includes:

- expanded scenario matrix
- config digest
- environment fingerprint
- stable hash

Impact:

- same lock hash => same baseline directory
- any meaningful matrix change => new hash and fresh baseline scope

---

## Slide 6: Data + Model Repeatability

Two mechanisms:

- `data.commands`: migrations, fixture loads, management commands
- `data.loader`: Python hook (`module:function`) for idempotent ORM upserts

```text
djvrt command
    |
    | prepare_data(phase)
    v
data hooks
    |
    | migrate / loaddata / get_or_create
    v
Django DB
    ^
    |
Playwright capture_scenarios
    |
    v
screenshots + outcomes
```

Message:

- Visual testing quality is mostly a data-determinism problem.

---

## Slide 7: Package-First Seeder Framework

Core in package:

- `BaseDjangoVRTSeeder`
- `build_tree_shaken_variants(...)`
- `python -m djvrt.django_seed_cli`

Project extension:

- tiny adapter module with schema/default-config mapping
- optional setup and options-builder hooks

Result:

- reusable engine
- project-specific logic stays small and explicit

---

## Slide 8: Tree-Shaking Experiment Variants

```text
[schema + default config]
           |
           v
 [generate control variant]
           |
           v
[collect candidate mutations]
           |
           v
 [dedupe + stable sort]
           |
           v
[cap max_variants_per_type]
           |
           v
 [write scenarios + manifest]
```

Important nuance:

- tree-shaking is bounded coverage, not full Cartesian explosion.
- true Cartesian sweeps can be added in adapter code with explicit caps.

---

## Slide 9: CI Flow

```text
Checkout + uv sync --frozen
            |
            v
playwright install chromium
            |
            v
      djvrt discover
            |
            v
        djvrt lock
            |
            v
        djvrt check
            |
            v
   upload run artifacts
```

Why this works in practice:

- deterministic seed hooks run in CI too
- non-zero exit on regressions/capture failures
- reviewable HTML and image diffs in artifacts

---

## Slide 10: Monorepo and Release Strategy

Target shape:

- one product repo per Django app
- one reusable `django-vrt` package repo
- consumers install from PyPI and wire only extension hooks

```text
django-vrt package repo
          |
          | publish
          v
         PyPI
          |
          | uv add django-vrt
          v
   any Django project
          |
          v
project-specific seeder adapter
          |
          v
deterministic VRT pipeline
```

---

## Slide 11: What Teams Get

- Faster UI refactors with confidence.
- Safer experiment rollouts.
- Clear approvals for intentional visual changes.
- Portable testing model across Django projects.

---

## Slide 12: Demo Plan (Live)

1. `djvrt discover` and `djvrt lock`
2. run deterministic seeding via `djvrt.django_seed_cli`
3. `djvrt baseline`
4. introduce a UI change
5. `djvrt check` and inspect `report.html`
6. `djvrt approve` for intentional updates

---

## Slide 13: Lessons Learned

- Lockfiles are the foundation, not an extra.
- Data determinism matters more than diff algorithms.
- Keep project extensions thin or the platform stops being reusable.
- Bounded variant generation beats naive exhaustive runs in most teams.

---

## Slide 14: Call To Action

Adopt in three steps:

1. Install `django-vrt` in one Django service.
2. Add deterministic seed hooks and one auth profile.
3. Gate PRs on `djvrt check` with artifact review.

`Repeatability is a feature.`
