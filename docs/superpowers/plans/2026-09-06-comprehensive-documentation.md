# Comprehensive Documentation Implementation Plan

**Goal:** Refactor remaining FunASR documentation into a coherent maintained system.
**Architecture:** Existing Jinja/Markdown generator, expanded source catalogue,
generated compatibility pages and curated task-oriented Markdown entry points.
**Tech Stack:** Python, Jinja2, BeautifulSoup, Markdown, Playwright.

- [x] Inventory repository and existing publication pipelines; create isolated worktree.
- [x] Rewrite installation/tutorial; check syntax/contracts without claiming model inference.
- [x] Add source-grounded Python API, training and model registration guides.
- [x] Rebuild bilingual Model Zoo and runtime indexes; preserve release history.
- [x] Expand catalogue and source-link coverage for service/security/client guides.
- [x] Generate GitHub Pages compatibility routes from the same Markdown content.
- [ ] Improve generated API navigation and keyboard/mobile behavior.
- [ ] Run source contracts, link/fragment audits, full site and browser regressions.
- [ ] Back up, sign/DCO, push, inspect exact-head CI, merge and deploy.
- [ ] Verify both public hosts and save publication evidence.

## Validation

Run on ind-gpu8 in `/tmp/funasr-docs-comprehensive-20260906`:

```sh
PYTHONPATH=/tmp/funasr-redesign-python python -m pytest web-pages/product-site/tests -q
PYTHONPATH=/tmp/funasr-redesign-python python web-pages/product-site/build.py --output /tmp/funasr-docs-comprehensive-build
python web-pages/product-site/validate.py /tmp/funasr-docs-comprehensive-build
```

Run newly added learning/training/API source-contract tests and the pinned
Playwright suite. Test compatibility export against a temporary output tree;
preserve generated API data and all prior published route names. Independently
review source correctness before publishing, not just string assertions.
