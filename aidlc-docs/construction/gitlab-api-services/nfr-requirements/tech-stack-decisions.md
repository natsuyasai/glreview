# UNIT-02: GitLab API Services テックスタック決定

## 概要

UNIT-02（GitLab API Services）で使用する技術スタ��クの詳細決定を記録する。

---

## 1. ランタイム依存

### python-gitlab

| 項目 | 決定 |
|---|---|
| パッケージ | `python-gitlab` |
| バージョン固定 | 完全固定（例：`==4.13.0`） |
| 固定方針 | SECURITY-10準拠。明示的にアップデートする |
| 用途 | GitLab REST APIとの通信 |

**選定理由**:
- GitLab公式推奨のPythonクライアントライブラリ
- MR、ディスカッション、ノート等の操作を網羅
- 認証（Private Token）をネイティブサポート
- アプリケーション設計（INCEPTION）で選定済み

**バージョン固定の根拠**:
- APIクライアントはメジャー/マイナ��アップデートで破壊的変更のリスクがある
- 完全固定によりビルドの再現性を保証する
- セキュリティパッチ適用時は手動でバージョンを更新する

---

## 2. 非同期処理

### asyncio（Python標準ライブラリ）

| 項目 | 決定 |
|---|---|
| モジュール | `asyncio` |
| ラッパー | `asyncio.to_thread()` |
| 追加依存 | なし（Python 3.11+標準） |

**選定理由**:
- python-gitlabは同期ライブラリのため、`asyncio.to_thread()` でノンブロッキング化する
- Textualがasyncioベースのためシームレスに統合可能
- 外部の非同期HTTPクライアント（aiohttp等）は不要 — python-gitlabの内部requestsをそのまま使用

**実装パターン**:
```python
async def get_mr_detail(self, mr_iid: int) -> MergeRequestDetail:
    mr = await asyncio.to_thread(self._project.mergerequests.get, mr_iid)
    return self._convert_to_detail(mr)
```

---

## 3. キャッシュ

### functools.lru_cache / カスタム辞書キャッシュ

| 項目 | 決定 |
|---|---|
| 実装方式 | カスタム辞書ベースのLRUキャッシュ |
| 追加依存 | なし（Python標準ライブラリのみ） |

**選定理由**:
- `functools.lru_cache` はasyncメソッドとの相性が悪い（awaitableをキャッシュしてしまう）
- `collections.OrderedDict` ベースのシンプルなLRUキャッシュを自作する
- エントリ数上限付きで、キャッシュ無効化（手動クリア）もサポートする
- 外部キャッシュライブラリ（cachetools等）は依存を増やすため不採用

---

## 4. テスト依存

### pytest + pytest-asyncio

| パッケージ | バージョン固定 | 用途 |
|---|---|---|
| `pytest` | 完全固定 | テストフレームワーク（UNIT-01で導入済み） |
| `pytest-asyncio` | 完全固定 | asyncメソッドのテストサポート |
| `unittest.mock` | — | Python標準。python-gitlabのモック |

**選定理由**:
- `pytest-asyncio`: async/awaitメソッドのテストに必要
- `unittest.mock`: python-gitlabの呼び出しをモックし、外部依存なしでテスト可能
- 追加のモックライブラリ（responses、vcrpy等）は不使用 — python-gitlabレベルでモックすればHTTPレベルのモックは不要

---

## 5. pyproject.toml への影響

### 追加する依存関係

```toml
[project]
dependencies = [
    # 既存（UNIT-01）
    # ...
    # UNIT-02 追加
    "python-gitlab==4.13.0",
]

[project.optional-dependencies]
dev = [
    # 既存（UNIT-01）
    # ...
    # UNIT-02 追加
    "pytest-asyncio==0.24.0",
]
```

※ python-gitlabの正確なバー��ョンはコード生成時にPyPIの最新安定版を確認して決定する。

---

## 6. 依存関係サマリー

```
UNIT-02 ランタイム依存:
  python-gitlab==4.13.0   (GitLab API通信)
  asyncio (標準ライブラリ)  (非同期処理)

UNIT-02 テスト依存:
  pytest (UNIT-01で導入済み)
  pytest-asyncio==0.24.0  (asyncテスト)
  unittest.mock (標準ライブラリ)

UNIT-01からの継承依存:
  AppConfig, データモデル, Logger
```
