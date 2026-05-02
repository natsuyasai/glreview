# UV Scripts Design

## Overview

npm の `package.json scripts` に相当する機能を `pyproject.toml` 上に定義し、`uv run poe <task>` で呼び出せるようにする。ツールには `poethepoet` を使用する。

## Dependencies

`poethepoet` を `dev` dependency group に追加する。

```toml
[dependency-groups]
dev = [
    ...
    "poethepoet>=0.27,<1.0",
]
```

## Script Definitions

`pyproject.toml` に `[tool.poe.tasks]` セクションを追加する。

```toml
[tool.poe.tasks]
format = "uv run ruff format ."
lint   = "uv run ruff check --fix"
test   = "uv run pytest"
build  = "uv run pyinstaller glreview.spec"
```

## Usage

```sh
uv run poe format   # ruff format .
uv run poe lint     # ruff check --fix
uv run poe test     # pytest
uv run poe build    # pyinstaller glreview.spec
```

## Scope

- `pyproject.toml` への `poethepoet` 追加と `[tool.poe.tasks]` セクション追加のみ
- 既存のスクリプト・設定には変更なし
