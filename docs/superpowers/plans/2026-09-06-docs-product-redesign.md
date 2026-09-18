# Documentation and Product Website Implementation Plan

**Goal:** Modernize the whole FunASR documentation experience without losing existing content.
**Architecture:** Existing Jinja generator plus source-backed Markdown catalogue and shared shell.
**Tech Stack:** Python, Jinja2, BeautifulSoup, Python-Markdown, plain CSS/JS, Playwright.
**Spec:** ../specs/2026-09-06-docs-product-redesign.md

## Sequence

- [x] Inventory current website, build/deploy contract and documentation sources.
- [x] Add failing tests for source-backed docs, search, shared shell and license boundaries.
- [x] Implement catalogue/renderer, link mapping, bilingual docs and search.
- [x] Rework homepage, shared visual system, navigation and legacy reading surfaces.
- [x] Reorganize source docs index, README entry points and GitHub Pages entry points.
- [x] Run static/browser regressions and visually inspect desktop/mobile screenshots.
- [ ] Preserve rollback bundle, sign/DCO PR, verify exact-head checks, merge and deploy.
- [ ] Verify public routes, record release evidence and remaining content gaps.

## Test Commands

Run on ind-gpu8 from the isolated repository:

```sh
python -m pytest web-pages/product-site/tests -q
python web-pages/product-site/build.py --output /tmp/funasr-redesign-build
python web-pages/product-site/validate.py /tmp/funasr-redesign-build
```

Use the repository browser suite and an added redesign suite to verify desktop/mobile
navigation, source-backed MOSS docs, search/no-results, copy, language peer, all old
routes, media loading and layout overflow. Retain logs/screenshots with the release.
