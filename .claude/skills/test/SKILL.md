---
description: "pytestでテストを実行する"
user-invocable: true
arg: "テストパスやオプション（例: --cov でカバレッジ計測、特定のファイルやテスト名）"
---

# pytest テスト実行

`uv run pytest` を使ってテストを実行します。

## 実行手順

引数 `$ARGUMENTS` に応じて以下を実行します。

### `--cov` または `cov` が指定された場合

カバレッジを計測しながら実行します：

```bash
uv run pytest --cov --cov-report=term-missing $ARGUMENTS
```

### 特定のファイルやテスト名が指定された場合

そのまま pytest に渡します：

```bash
uv run pytest $ARGUMENTS
```

### 引数なし（デフォルト）

全テストを実行します：

```bash
uv run pytest
```

## このプロジェクトのテスト規約

- テストファイル: `test_*.py`（`glreview/` 以下に配置）
- テストクラス: `Test*`
- テスト関数: `test_*`

## 結果の報告

- 失敗したテストはエラーメッセージと共に報告する
- 全テストパスした場合は「tests passed」と報告する
- カバレッジが80%未満の場合は警告する
