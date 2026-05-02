# UV Scripts (poethepoet) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `pyproject.toml` に poethepoet を追加し、format/lint/test/build の4スクリプトを `uv run poe <task>` で実行できるようにする。

**Architecture:** `pyproject.toml` の `[dependency-groups] dev` に poethepoet を追加し、`[tool.poe.tasks]` セクションにスクリプトを定義する。

**Tech Stack:** uv, poethepoet

---

### Task 1: poethepoet を dev 依存に追加してスクリプトを定義する

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: `[dependency-groups] dev` に poethepoet を追加する**

`pyproject.toml` の `[dependency-groups] dev` に以下を追加:

```toml
[dependency-groups]
dev = [
    "pytest>=8.0,<9.0",
    "pytest-cov>=5.0,<6.0",
    "pytest-asyncio>=0.23,<1.0",
    "ruff>=0.4,<1.0",
    "pyinstaller>=6.0,<7.0",
    "poethepoet>=0.27,<1.0",
]
```

- [ ] **Step 2: `[tool.poe.tasks]` セクションを追加する**

`pyproject.toml` の末尾に追加:

```toml
[tool.poe.tasks]
format = "uv run ruff format ."
lint   = "uv run ruff check --fix"
test   = "uv run pytest"
build  = "uv run pyinstaller glreview.spec"
```

- [ ] **Step 3: uv sync で poethepoet をインストールする**

```bash
uv sync
```

Expected: poethepoet がインストールされる

- [ ] **Step 4: 各スクリプトの動作確認**

```bash
uv run poe format
uv run poe lint
uv run poe test
```

Expected:
- `format`: `58 files left unchanged` などの出力
- `lint`: `All checks passed!`
- `test`: `passed` で終了

(`build` は pyinstaller.spec が必要なため動作確認はスキップ)

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "feat: add poethepoet scripts for format, lint, test, build"
```
