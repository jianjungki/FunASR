# Comprehensive Documentation Refactor

## Scope

Extend the shipped product documentation system to the remaining maintained
user-facing documentation: installation, SDK tutorial/API, Model Zoo, training,
model registration, service contracts, security, client integrations, deployment
and evaluation. Historical research and release records remain accessible but
are not presented as current deployment recommendations.

## Architecture

- Repository Markdown owns guide content; the bilingual catalogue owns task
  navigation and source mapping.
- The website renders these sources. GitHub Pages compatibility routes render
  the same guides, with a canonical website URL and no duplicated edited body.
- Generated API reference remains source-derived and links to the authored SDK
  contract. Preserve old API/tutorial/training/model URLs.
- SDK, native C++ WebSocket, Python HTTP and native vLLM contracts stay distinct.
- Preserve upstream model attribution and per-model license boundaries. Never
  turn historical benchmark numbers into generic capacity promises.

## Acceptance

Core guides have prerequisites, executable examples or exact recipe references,
expected outputs, limitations and next steps. Catalogue sources and relative
links resolve; all emitted source fragment links work. Search includes the new
topics. Desktop/mobile navigation and generated API reference remain usable.
All relevant tests run on ind-gpu8 before signed DCO publication. Back up before
push/merge/deploy; validate both public documentation hosts after publication.
