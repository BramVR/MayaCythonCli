# gg_CythonCompile Agents

Read `../bram-agent-scripts/AGENTS.md` first.

This repo currently inherits that workflow by default.

Repo-local notes:
- If this file and `../bram-agent-scripts/AGENTS.md` conflict, this file wins.
- Keep repo-specific instructions here; keep shared personal workflow in `../bram-agent-scripts/AGENTS.md`.
- Inherited helper scripts under `../bram-agent-scripts/scripts/` count as available workflow tools for this repo.
- When inherited workflow says to use `committer`, prefer `../bram-agent-scripts/scripts/committer.ps1` unless this repo ships its own `scripts/committer.ps1`.
- Do not parallelize dependent setup and verification commands.
- In sandbox sessions, prefer `.conda/.../python.exe` over `py` or bare `python`.
- If `committer.ps1` is blocked by execution policy, run it via `powershell -ExecutionPolicy Bypass -File`.
