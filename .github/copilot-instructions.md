# Splat Replay — Copilot Context

> This file provides essential context for **GitHub Copilot** so that code completions follow the project architecture, coding style, and toolchain. Keep it short and stable; update only when global rules truly change.

## Runtime Basics

- **OS / Shell**: **Windows 11** + **PowerShell**
- **Python**: Refer to `.python-version` file.
- **Package Tool**: **uv** only. Never call `pip` directly.
- **Working Directory**: Always confirm current directory with `pwd`/`Get-Location` or use explicit paths (`cd <path>` or `--project <path>`). Use repository root as base reference.

## Folder / Layer Rules

- `src/domain` **must not** import from application or infrastructure.
- `src/application` may import domain but **not** infrastructure.
- `src/interface` (CLI / GUI) calls application use-cases.
- Adapters live under `infrastructure.adapters`, ports under `application.interfaces`.

## Coding Style

- Format with **Black**, maximum **79 characters** per line.
- All public functions and methods **require type hints**.
- Use `structlog` for JSON logging.
- Avoid using `typing.Any`.

## Key Conventions

- Config files live under `config/*.yaml` or `config/*.toml`.
- Temporary debug files or code **must not be committed**.
