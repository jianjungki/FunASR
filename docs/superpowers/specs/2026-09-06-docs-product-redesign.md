# FunASR Documentation and Product Website

## Intent

Rebuild the public documentation experience around model selection, first inference,
deployment, and operation. The user authorized implementation and reversible
deployment without repeated approval. Preserve existing URLs and technical scope.

## Architecture

Keep the existing Jinja/static site generator and deployment registry. Add a
documentation catalogue whose entries point at existing Markdown sources, not
copied articles. Render those sources into bilingual `/docs/` routes with a
shared sidebar, section navigation, source links, and a local search index.
Unlisted repository-relative links continue to their source on GitHub.
The source documentation README and Sphinx index follow the same task order.

The homepage is a concise product/workflow entry. Models, deployments, documentation,
ecosystem, benchmarks, blog and donors share typography, navigation and mobile
behavior. Donors stays last. Legacy article bodies, anchors, demos and media are
preserved while their surrounding shell is normalized during generation.

## Visual Direction

White/light-gray reading surfaces, near-black text and code surfaces, emerald
commands and small coral accents. System sans-serif with a CJK sans fallback.
No stock server hero, artificial performance promises, gradient decoration or
floating section cards. Fixed-size text, restrained 8px-or-less corners,
visible focus, reduced-motion support, readable tables and code on narrow screens.
Use existing licensed Lucide icons and real project/audio assets.

## Technical Integrity

Keep MOSS visibly attributed to OpenMOSS, offline transcription/diarization with
anonymous speakers, not identity recognition. Do not conflate native vLLM,
split-engine wrappers, realtime ASR, or CPU/GPU validation coverage. Fix discovered
stale copy from primary evidence; never expand test claims just to fit the design.
Toolkit license comes from the current repository LICENSE, model licenses vary.

## Acceptance

1. Bilingual home, deployment hub/details, model list, docs, blog and donors work.
2. Docs originate from repository Markdown; links, images, fenced code and tables render.
3. Search works locally, handles no results, and needs no account or remote analytics.
4. Mobile navigation, language peers, anchor links and copy controls work by keyboard.
5. All existing public routes and article content survive; no broken internal links.
6. Static tests, full site validator and browser checks at 320/390/768/1440/1920 pass.
7. Record source commit, build checksums, previous deployment and rollback procedure
   before promotion. Verify public routes after deployment.
