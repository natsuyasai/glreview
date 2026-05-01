# UNIT-03: TUI Application テックスタック決定

## 概要

UNIT-03（TUI Application）で使用する技術スタックの詳細決定を記録する。

---

## 1. ランタイム依存

### Textual

| 項目 | 決定 |
|---|---|
| パッケージ | `textual` |
| バージョン固定 | メジャーまで固定（例：`>=0.60,<1.0`） |
| 固定方針 | マイナーアップデートを許容し、破壊的変更はメジャーで防ぐ |
| 用途 | TUIフレームワーク（App、Widget、Screen、CSS等） |

**選定理由**:
- Pythonネイティブの最新TUIフレームワーク
- CSS風のスタイリング、リアクティブ属性、組み込みウィジェット（Tree、RichLog、DataTable等）を提供
- アプリケーション設計（INCEPTION）で選定済み

**バージョン固定方針の根拠**:
- Textualは0.x系であり、活発にAPIが改善されている
- メジャーまで固定（`<1.0`）とすることで、パッチ・マイナーの改善を自動的に取り込みつつ、1.0リリース時の破壊的変更を防ぐ
- UNIT-02のpython-gitlab（完全固定）とは異なる方針：TextualはUI層であり、APIクライアントほど互換性リスクが高くない

### Pygments

| 項目 | 決定 |
|---|---|
| パッケージ | `pygments` |
| バージョン固定 | メジャーまで固定（例：`>=2.0,<3.0`） |
| 用途 | 差分表示のシンタックスハイライト |

**選定理由**:
- Pythonの標準的なシンタックスハイライトライブラリ
- Textualの `RichLog` / Rich との統合がネイティブ
- 多言語対応（300+言語）でMRの差分表示に最適
- 要件分析で選定済み

**バージョン固定方針の根拠**:
- Pygmentsは安定したライブラリ（2.x系が長期間安定）
- メジャーまで固定で十分な安定性を確保できる

---

## 2. テスト依存

### pytest + textual.testing

| パッケージ | バージョン固定 | 用途 |
|---|---|---|
| `pytest` | 完全固定（UNIT-01で導入済み） | テストフレームワーク |
| `pytest-asyncio` | 完全固定（UNIT-02で導入済み） | asyncメソッドのテストサポート |
| `textual` (dev extras) | — | `textual.testing` モジュール（Pilot API） |

**テスト構成**:
- **ビジネスロジックテスト**: 通常の `pytest` でUIに依存しないロジックを検証
  - ツリーノードデータ構築
  - 差分パース・フォーマット
  - 状態遷移
- **Textual Pilotテスト**: `textual.testing.app_test` デコレータ / `async with app.run_test()` を使用
  - ヘッドレス環境でのアプリケーション起動テスト
  - キーバインドの動作確認
  - モーダル表示の確認

**実装パターン（Pilotテスト）**:
```python
from textual.testing import app_test

async def test_app_startup():
    app = GLReviewApp()
    async with app.run_test() as pilot:
        assert app.query_one(MRListPanel) is not None
        assert app.query_one(ContentPanel) is not None
```

---

## 3. pyproject.toml への影響

### 追加する依存関係

```toml
[project]
dependencies = [
    # 既存（UNIT-01, UNIT-02）
    # ...
    # UNIT-03 追加
    "textual>=0.60,<1.0",
    "pygments>=2.0,<3.0",
]
```

※ textualのバージョン下限は、コード生成時にPyPIの最新安定版を確認して決定する。

---

## 4. 依存関係サマリー

```
UNIT-03 ランタイム依存:
  textual>=0.60,<1.0     (TUIフレームワーク)
  pygments>=2.0,<3.0     (シンタックスハイライト)

UNIT-03 テスト依存:
  pytest (UNIT-01で導入済み)
  pytest-asyncio (UNIT-02で導入済み)
  textual.testing (textualパッケージに含まれる)

UNIT-01からの継承依存:
  AppConfig, データモデル, Logger, ConfigManager, GitRepoDetector

UNIT-02からの継承依存:
  GitLabClient, MRService, CommentService, PaginatedResult, MRCategory
```
