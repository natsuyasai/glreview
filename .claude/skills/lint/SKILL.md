---
description: "ruffによる静的解析とフォーマットチェックを実行する"
user-invocable: true
arg: "オプション（例: --fix でauto-fix、format でフォーマット修正）"
---

# Ruff 静的解析

`uv run ruff` を使って静的解析とフォーマットチェックを実行します。

## 実行手順

引数 `$ARGUMENTS` に応じて以下を実行します。

### `--fix` または `fix` が指定された場合

自動修正可能な問題を修正します：

```bash
uv run ruff check --fix .
uv run ruff format .
```

### `format` のみが指定された場合

フォーマットのみ修正します：

```bash
uv run ruff format .
```

### 引数なし（デフォルト）

チェックのみ実行します（ファイルを変更しない）：

```bash
uv run ruff check .
uv run ruff format --check .
```

## 結果の報告

- エラーや警告があればファイルと行番号を示して報告する
- すべてパスした場合は「lint OK」と報告する
- フォーマット違反がある場合はファイル名を列挙する
