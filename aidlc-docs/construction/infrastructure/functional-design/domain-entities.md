# UNIT-01: Infrastructure ドメインエンティティ

## エンティティ関係図

### テキスト表現

```
AppConfig ─────────── 1つのアプリケーションに1つ
  ├─ gitlab_url
  ├─ token
  ├─ editor
  ├─ log_level
  ├─ theme
  └─ remote_name

GitLabProjectInfo ─── GitRepoDetector が生成
  ├─ host
  └─ project_path

MergeRequestSummary ── MR一覧表示用（軽量）
  ├─ iid
  ├─ title
  ├─ author
  ├─ assignee?
  ├─ status
  ├─ labels[]
  └─ updated_at

MergeRequestDetail ── MR詳細表示用（フル情報）
  ├─ iid
  ├─ title
  ├─ description
  ├─ author
  ├─ assignee?
  ├─ status
  ├─ labels[]
  ├─ milestone?
  ├─ pipeline_status?
  ├─ web_url
  ├─ created_at
  └─ updated_at

FileChange ────────── MRの変更ファイル情報
  ├─ old_path
  ├─ new_path
  ├─ new_file
  ├─ deleted_file
  └─ renamed_file

FileDiff ──────────── ファイルの差分内容
  ├─ file_path
  ├─ diff
  ├─ old_path
  └─ new_path

Discussion ────────── MRのディスカッションスレッド
  ├─ id
  └─ notes[] ──────── Note（1:N）

Note ──────────────── コメント/ノート
  ├─ id
  ├─ author
  ├─ body
  ├─ created_at
  └─ position? ────── NotePosition（0..1）

NotePosition ──────── インラインコメントの位置情報
  ├─ file_path
  ├─ new_line?
  └─ old_line?

CommentContext ────── コメント投稿時のコンテキスト
  ├─ mr_iid
  ├─ file_path?
  ├─ line?
  ├─ line_type?
  └─ discussion_id?

CommentType (Enum) ── コメント種別
  ├─ INLINE
  ├─ NOTE
  └─ REPLY
```

## エンティティ詳細定義

### AppConfig

アプリケーション全体の設定を保持する。設定ファイルから読み込まれる。

| フィールド | 型 | 必須 | デフォルト | 制約 |
|---|---|---|---|---|
| gitlab_url | str | はい | `https://gitlab.com` | http:// または https:// で始まること |
| token | str | はい | — | 空でないこと、プレースホルダーでないこと |
| editor | str | いいえ | `$EDITOR` or `vi` | |
| log_level | str | いいえ | `INFO` | DEBUG/INFO/WARNING/ERROR/CRITICAL |
| theme | str | いいえ | `dark` | Textual組み込みテーマ名 |
| remote_name | str | いいえ | `""` | 空 = 自動検出 |

**不変条件**: gitlab_url と token は常にセットで有効な値を持つ

### GitLabProjectInfo

GitリポジトリのリモートURLから解析されたGitLab接続情報。

| フィールド | 型 | 必須 | 制約 |
|---|---|---|---|
| host | str | はい | 空でないこと |
| project_path | str | はい | group/project 形式、サブグループ可 |

**不変条件**: host と project_path はペアで有効（解析成功時のみインスタンス化される）

### MergeRequestSummary

MR一覧表示に必要な最小限の情報。API層が GitLab API レスポンスから生成する。

| フィールド | 型 | 必須 | 制約 |
|---|---|---|---|
| iid | int | はい | 正の整数 |
| title | str | はい | |
| author | str | はい | |
| assignee | str \| None | いいえ | 未割当の場合 None |
| status | str | はい | "opened", "merged", "closed" 等 |
| labels | list[str] | はい | 空リスト可 |
| updated_at | str | はい | ISO 8601 形式 |

### MergeRequestDetail

MR Overview 表示に必要なフル情報。MergeRequestSummary の拡張。

| フィールド | 型 | 必須 | 制約 |
|---|---|---|---|
| iid | int | はい | 正の整数 |
| title | str | はい | |
| description | str | はい | 空文字列可 |
| author | str | はい | |
| assignee | str \| None | いいえ | |
| status | str | はい | |
| labels | list[str] | はい | |
| milestone | str \| None | いいえ | |
| pipeline_status | str \| None | いいえ | |
| web_url | str | はい | |
| created_at | str | はい | ISO 8601 形式 |
| updated_at | str | はい | ISO 8601 形式 |

### FileChange

MRで変更されたファイルのメタ情報。

| フィールド | 型 | 必須 | 制約 |
|---|---|---|---|
| old_path | str | はい | |
| new_path | str | はい | |
| new_file | bool | はい | |
| deleted_file | bool | はい | |
| renamed_file | bool | はい | |

**ビジネスルール**: `renamed_file = True` の場合、`old_path != new_path`

### FileDiff

ファイルの差分内容（unified diff 形式）。

| フィールド | 型 | 必須 | 制約 |
|---|---|---|---|
| file_path | str | はい | 表示用のファイルパス |
| diff | str | はい | unified diff テキスト |
| old_path | str | はい | |
| new_path | str | はい | |

### CommentType (Enum)

コメントの種別を表す列挙型。

| 値 | 説明 |
|---|---|
| INLINE | ファイルの特定行に対するインラインコメント |
| NOTE | MR全体に対するノートコメント |
| REPLY | 既存ディスカッションへのリプライ |

### CommentContext

コメント投稿時に必要なコンテキスト情報。CommentType に応じて必要なフィールドが異なる。

| フィールド | 型 | 必須条件 | 制約 |
|---|---|---|---|
| mr_iid | int | 常に必須 | 正の整数 |
| file_path | str \| None | INLINE時に必須 | |
| line | int \| None | INLINE時に必須 | 正の整数 |
| line_type | str \| None | INLINE時に必須 | "new" または "old" |
| discussion_id | str \| None | REPLY時に必須 | |

**不変条件**:
- `CommentType.INLINE`: file_path, line, line_type はすべて非None
- `CommentType.NOTE`: file_path, line, line_type, discussion_id はすべて None
- `CommentType.REPLY`: discussion_id は非None

### Discussion

MRのディスカッション（コメントスレッド）。

| フィールド | 型 | 必須 | 制約 |
|---|---|---|---|
| id | str | はい | GitLab ディスカッションID |
| notes | list[Note] | はい | 1つ以上のNoteを含む |

**不変条件**: `len(notes) >= 1`（ディスカッションには最低1つのノートが存在する）

### Note

ディスカッション内の個別のコメント/ノート。

| フィールド | 型 | 必須 | 制約 |
|---|---|---|---|
| id | int | はい | 正の整数 |
| author | str | はい | |
| body | str | はい | |
| created_at | str | はい | ISO 8601 形式 |
| position | NotePosition \| None | いいえ | インラインコメントの場合のみ |

### NotePosition

インラインコメントのファイル内位置情報。

| フィールド | 型 | 必須 | 制約 |
|---|---|---|---|
| file_path | str | はい | |
| new_line | int \| None | いいえ | 新ファイルでの行番号 |
| old_line | int \| None | いいえ | 旧ファイルでの行番号 |

**不変条件**: `new_line` と `old_line` の少なくとも一方は非None

## エンティティ間の関係

```
AppConfig (1) ──使用── (1) ConfigManager
AppConfig (1) ──使用── (1) GitLabClient [UNIT-02]
GitLabProjectInfo (1) ──生成── (1) GitRepoDetector
MergeRequestDetail (1) ──拡張── (1) MergeRequestSummary [概念的]
MergeRequestDetail (1) ──持つ── (N) FileChange
FileChange (1) ──対応── (0..1) FileDiff
Discussion (1) ──含む── (1..N) Note
Note (1) ──持つ── (0..1) NotePosition
CommentContext (1) ──参照── (1) CommentType
```

## UNIT-01 が直接管理するエンティティ

| エンティティ | 管理コンポーネント | 責任 |
|---|---|---|
| AppConfig | ConfigManager | 生成、読み込み、バリデーション |
| GitLabProjectInfo | GitRepoDetector | 生成 |

## UNIT-01 が定義するが他ユニットが使用するエンティティ

| エンティティ | 使用元 | 用途 |
|---|---|---|
| MergeRequestSummary | UNIT-02 (MRService) | API結果のマッピング |
| MergeRequestDetail | UNIT-02 (MRService) | API結果のマッピング |
| FileChange | UNIT-02 (MRService) | API結果のマッピング |
| FileDiff | UNIT-02 (MRService) | API結果のマッピング |
| CommentType | UNIT-03 (CommentDialog) | UI選択肢 |
| CommentContext | UNIT-03 (CommentDialog) | コメント投稿コンテキスト |
| Discussion | UNIT-02 (CommentService) | API結果のマッピング |
| Note | UNIT-02 (CommentService) | API結果のマッピング |
| NotePosition | UNIT-02 (CommentService) | API結果のマッピング |
