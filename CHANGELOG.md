# Changelog

## [0.3.8] - 2026-10-16

- **why:** Replace the multi-agent workflow with one Vibe agent plus skills, and add a Blueprint/Codebase sync protocol
- **model:** kompis/qwen3.8-flash-next-iq3_s
- **tags:** agent-framework, workflow, docs

### Added

- Skills under `.opencode/skills/`: `clear-language`, `clear-language-norwegian`, `memory`, `todo-txt`, `wrap-up`
- `AGENTS.md` Master Rules: Blueprint generation, Codebase mapping, and a Synchronization Protocol
- `RULES.md` rules for commit consent, layer boundaries, state ownership, verification gate, intent-based comments, and documentation separation

### Changed

- `AGENTS.md` rewritten from a two-mode agent protocol to Master Rules
- `.opencode/agents/vibe.md` wake-up contract now loads skills and `CODEBASE.md`
- `opencode.json` lists `AGENTS.md` in instructions and sets `autoupdate`, `formatter`, `lsp`, `share`, and `snapshot`
- `.opencode/update.sh` now pulls from `aheimsbakk/agentic-opencode`

### Removed

- Multi-agent workflow agents: `pm`, `architect`, `builder`, `qa`, `brainstorm`
- Worklog system: `.opencode/WORKLOG_TEMPLATE.md` and the worklog rules in `AGENTS.md`
