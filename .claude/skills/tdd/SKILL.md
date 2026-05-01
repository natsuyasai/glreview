---
description: "t-wada推奨TDDワークフローで機能を実装する"
user-invocable: true
arg: "実装する機能の名前や説明"
---

# TDD（テスト駆動開発）ワークフロー

t-wada（和田卓人）が推奨するTDDの進め方に従って実装を行います。

## 基本原則

1. **テストを先に書く**: 実装コードを書く前に、必ず失敗するテストを書く
2. **最小限の実装**: テストを通すための最小限のコードだけを書く
3. **リファクタリング**: テストが通った後にコードを改善する

## Red-Green-Refactor サイクル

### Red（赤: テストが失敗する状態）

1. 実装したい振る舞いを表すテストを1つだけ書く
2. テストを実行して**失敗することを確認する**（必ず実行して確認）
3. テストが正しい理由で失敗していることを確認する

### Green（緑: テストが通る状態）

1. **仮実装（Fake It）**: まずはハードコードでもいいのでテストを通す
2. テストを実行して**成功することを確認する**
3. 必要に応じて**三角測量（Triangulation）**: 別のテストケースを追加して、ハードコードでは通らないようにし、一般的な実装に導く

### Refactor（リファクタリング）

1. テストがGreenの状態で、コードの重複や設計の問題を改善する
2. リファクタリング後もテストがGreenであることを確認する
3. 一度に1つの変更だけ行い、その都度テストを実行する

## このプロジェクトでのテスト規約

### テストファイルの配置

- テストファイルは `glreview/` 以下にモジュールと同ディレクトリに配置
- ファイル名: `test_<module_name>.py`

### テスト実行コマンド

```bash
# 特定のテストファイルのみ実行（高速なフィードバック）
uv run pytest glreview/path/to/test_module.py

# 特定のテスト関数のみ実行
uv run pytest glreview/path/to/test_module.py::test_function_name

# 全テスト実行
uv run pytest

# カバレッジ付きで実行
uv run pytest --cov --cov-report=term-missing
```

### テストの書き方

```python
import pytest
from glreview.module import target_function


class TestTargetFunction:
    def test_expected_behavior(self):
        # Arrange（準備）
        # Act（実行）
        result = target_function(...)
        # Assert（検証）
        assert result == expected
```

### 静的解析（変更後に実行）

```bash
uv run ruff check .
uv run ruff format --check .
```

## 進め方の例

ユーザーが `$ARGUMENTS` と指定した機能について：

1. まず対象の機能が何をすべきか、テストケースを洗い出す
2. 最もシンプルなテストケースから始める
3. Red → Green → Refactor を繰り返す
4. 各サイクルで必ずテストを実行して結果を確認する
5. すべてのテストケースを実装し終えたら、全テストを実行して確認する

## 禁止事項

- テストを書く前に実装コードを書くこと
- 一度に複数のテストケースを追加すること
- テストがRedの状態でリファクタリングすること
- テストを実行せずに次のステップに進むこと
