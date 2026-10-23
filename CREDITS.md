# Credits and provenance

SourceNest is an independent implementation prepared with Codex assistance.

Conceptual inspiration:

- Andrej Karpathy's LLM Wiki note: https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f — source material and a maintained wiki.
- Avenox Beyin: https://github.com/avenoxai/avenoxbeyin — automatic session-memory workflow.

This repository is not an official release, endorsed integration, or distribution of those complete projects. Links acknowledge ideas; upstream projects retain their own licenses and authorship. The MIT license here applies to this implementation, not to linked third-party materials.

Runtime integrations use Python, Git and whichever assistant CLI the user chooses. Codex and Claude Code hook formats are handled by small local adapters; no upstream repository, credential, private transcript or model weight is bundled.

The October 2026 unreleased update adapts safe-upgrade, rollback, human diagnostic and local-refresh workflow ideas described at https://avenox.lol/beyin.md. The implementation and tests are written for SourceNest; no upstream runtime is bundled. See [adaptation scope](docs/avenox-v3-adaptation.md).

SourceNest 2.0 independently implements the expanded workflow capabilities using the public Avenox V3 documentation and adapter/protocol contracts as references. SourceNest does not vendor the Avenox engine. Native clients retain their own software licenses; optional providers are not bundled. See the capability matrix and validation boundary in docs/v2-guide.md.
