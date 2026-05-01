# 作業単位 依存関係マトリックス

## ユニット間依存関係

| ユニット | UNIT-01 | UNIT-02 | UNIT-03 |
|---|---|---|---|
| **UNIT-01** Infrastructure | - | | |
| **UNIT-02** GitLab API Services | **依存** | - | |
| **UNIT-03** TUI Application | **依存** | **依存** | - |

## 依存関係図

```
+--------------------------------------------------+
|        UNIT-03: TUI Application                  |
|  GLReviewApp, MRListPanel, ContentPanel,       |
|  CommentDialog, HelpScreen                       |
+-------------------+------------------------------+
                    |
          +---------+---------+
          |                   |
          v                   v
+--------------------+  +--------------------------+
| UNIT-02: GitLab    |  | UNIT-01: Infrastructure  |
| API Services       |  | (ConfigManager直接参照)  |
| GitLabClient,      |  +--------------------------+
| MRService,         |
| CommentService     |
+---------+----------+
          |
          v
+--------------------+
| UNIT-01:           |
| Infrastructure     |
| ConfigManager,     |
| GitRepoDetector,   |
| Logger, Models     |
+--------------------+
```

## インターフェース定義

### UNIT-01 → UNIT-02 提供インターフェース

| 提供元 | インターフェース | 利用者 |
|---|---|---|
| ConfigManager | `load() -> AppConfig` | GitLabClient |
| データモデル | `MergeRequestSummary`, `MergeRequestDetail`, `FileChange`, `FileDiff`, `Discussion`, `Note`, `NotePosition`, `CommentType`, `CommentContext` | MRService, CommentService |

### UNIT-02 → UNIT-03 提供インターフェース

| 提供元 | インターフェース | 利用者 |
|---|---|---|
| MRService | `get_assigned_to_me()`, `get_created_by_me()`, `get_unassigned()`, `get_assigned_to_others()` | MRListPanel |
| MRService | `get_mr_detail()`, `get_mr_changes()`, `get_mr_diff()` | ContentPanel |
| CommentService | `get_discussions()` | ContentPanel |
| CommentService | `add_inline_comment()`, `add_note()`, `reply_to_discussion()` | CommentDialog |

### UNIT-01 → UNIT-03 提供インターフェース

| 提供元 | インターフェース | 利用者 |
|---|---|---|
| ConfigManager | `load() -> AppConfig`（editor設定） | GLReviewApp（外部エディタ連携） |

## 実装順序の根拠

1. **UNIT-01（Infrastructure）を最初に実装**
   - 他の全ユニットが依存するデータモデルと設定管理を提供
   - 外部依存が最小限（標準ライブラリのみ）
   - 単独でテスト可能

2. **UNIT-02（GitLab API Services）を2番目に実装**
   - UNIT-01のデータモデルとConfigManagerに依存
   - UNIT-01完成後に統合テストが可能
   - python-gitlabのモックによる単体テストが可能

3. **UNIT-03（TUI Application）を最後に実装**
   - 全ユニットに依存
   - UNIT-01, UNIT-02の安定したインターフェースを前提にUI構築
   - Textualのテストフレームワークで単体テスト可能

## 循環依存の確認

循環依存なし。依存関係は厳密に一方向：

```
UNIT-03 → UNIT-02 → UNIT-01
UNIT-03 → UNIT-01（直接参照）
```
