# UNIT-02: GitLab API Services ビジネスロジックモデル

## 概要

GitLab API Servicesは、python-gitlabを通じてGitLab APIと通信し、MRの一覧・詳細・差分取得およびコメント操作を提供するAPI層である。3つのコンポーネント（GitLabClient、MRService、CommentService）で構成される。

---

## 1. GitLabClient ビジネスロジック

### 1.1 認証・接続管理

```
入力: AppConfig (gitlab_url, token)
処理:
  1. AppConfigからgitlab_urlとtokenを取得する
  2. python-gitlab の Gitlab インスタンスを生成する
     - url = config.gitlab_url
     - private_token = config.token
     - timeout = 30秒（NFR要件で決定済み）
  3. gl.auth() を呼び出して認証を検証する
  4. 認証失敗時は GitLabAuthError を送出する
出力: 認証済み Gitlab インスタンス
```

### 1.2 プロジェクト解決

```
入力: project_path (str) — "group/subgroup/project" 形式
処理:
  1. gl.projects.get(project_path) を呼び出す
  2. プロジェクトが見つからない場合は GitLabProjectNotFoundError を送出する
  3. アクセス権がない場合は GitLabAccessDeniedError を送出する
出力: gitlab.v4.objects.Project インスタンス
```

### 1.3 現在のユーザー情報取得

```
入力: なし（認証済みセッションから取得）
処理:
  1. gl.user を参照する
  2. ユーザーIDとユーザー名を返す
出力: CurrentUser 情報（id, username）
```

---

## 2. MRService ビジネスロジック

### 2.1 カテゴリ別MR一覧取得

MR一覧は4カテゴリに分類して取得する。各カテゴリは独立したAPIクエリで取得する。

**共通パラメータ**:
- state: "opened"（オープンMRのみ）
- order_by: ユーザー設定に従う（デフォルト: "updated_at"）
- sort: "desc"
- per_page: 20（1ページ分）
- page: 1（初回）

#### 2.1.1 自身に割り当てられているMR

```
入力: current_user_id, page=1
処理:
  1. project.mergerequests.list(
       state="opened",
       assignee_id=current_user_id,
       order_by=設定値,
       sort="desc",
       per_page=20,
       page=page
     )
  2. 結果を MergeRequestSummary のリストに変換する
  3. 次ページの有無を確認する（レスポンスヘッダ x-next-page）
出力: (list[MergeRequestSummary], has_next_page: bool)
```

#### 2.1.2 自身が作成したMR

```
入力: current_user_id, page=1
���理:
  1. project.mergerequests.list(
       state="opened",
       author_id=current_user_id,
       order_by=設定値,
       sort="desc",
       per_page=20,
       page=page
     )
  2. 結果を MergeRequestSummary のリストに変換する
出力: (list[MergeRequestSummary], has_next_page: bool)
```

#### 2.1.3 未割当のMR

```
入力: page=1
処理:
  1. project.mergerequests.list(
       state="opened",
       assignee_id="None",
       order_by=設定値,
       sort="desc",
       per_page=20,
       page=page
     )
  2. 結果を MergeRequestSummary のリストに変換する
出力: (list[MergeRequestSummary], has_next_page: bool)
```

#### 2.1.4 自身以外に割り当てられているMR

```
入力: current_user_id, page=1
処理:
  1. project.mergerequests.list(
       state="opened",
       assignee_id="Any",
       order_by=設定値,
       sort="desc",
       per_page=20,
       page=page
     )
  2. 結果から assignee_id == current_user_id ���MRを除外する
  3. 残りを MergeRequestSummary のリストに変換する
  ※ GitLab APIに「自身以外のassignee」の直接フィルタがないためクライアント側で除外
出力: (list[MergeRequestSummary], has_next_page: bool)
```

### 2.2 python-gitlab オブジェクトから MergeRequestSummary への��換

```
入力: gitlab MergeRequest オブジェクト
処理:
  1. mr.iid → iid
  2. mr.title → title
  3. mr.author["username"] → author
  4. mr.assignee["username"] if mr.assignee else None → assignee
  5. mr.state → status
  6. mr.labels → labels
  7. mr.updated_at → updated_at
出力: MergeRequestSummary
```

### 2.3 MR詳細取得

```
入力: mr_iid (int)
���理:
  1. project.mergerequests.get(mr_iid) を呼び出す
  2. MRが見つからない場合は MRNotFoundError を送出する
  3. 結果を MergeRequestDetail に変換する：
     - iid, title, description, author(username)
     - assignee(username or None), status, labels
     - milestone(title or None), pipeline_status(head_pipeline.status or None)
     - web_url, created_at, updated_at
出力: MergeRequestDetail
```

### 2.4 変更ファイル一覧取得

```
入力: mr_iid (int)
処理:
  1. project.mergerequests.get(mr_iid, lazy=True).changes() を呼び出す
     または mr.diffs.list() を使用する
  2. 各変更ファイルを FileChange に変換する：
     - old_path, new_path
     - new_file, deleted_file, renamed_file
出力: list[FileChange]
```

### 2.5 ファイル差分取得（遅延取得）

```
入力: mr_iid (int), file_path (str)
処理:
  1. MRの変更情報（diffs）からfile_pathに一致するエントリを検索する
  2. 見つからない場合は FileNotFoundInMRError を送出する
  3. 差分情報を FileDiff に変換する：
     - file_path, diff(unified diff文字列), old_path, new_path
出力: FileDiff
```

---

## 3. CommentService ビジネスロジック

### 3.1 ディスカッション一覧取得

```
入力: mr_iid (int)
処理:
  1. project.mergerequests.get(mr_iid, lazy=True).discussions.list(all=True)
  2. 各ディスカッションを Discussion に変換する：
     - discussion.id → id
     - discussion.notes → list[Note] に変換
       各 note:
         - note.id, note.author["username"], note.body, note.created_at
         - note.position がある場合:
           NotePosition(file_path, new_line, old_line)
         - note.position がない場合: position = None
  3. システムノート（note.system == True）を除外する
出力: list[Discussion]
```

### 3.2 インラインコメント投稿

```
入力: mr_iid (int), file_path (str), line (int), body (str), line_type (str: "new"|"old")
処理:
  1. バリデーション：body が空でないことを確��
  2. MRの最新のdiff情報（base_sha, head_sha, start_sha）��取得する
  3. ディスカッションを作成する：
     mr.discussions.create({
       "body": body,
       "position": {
         "base_sha": base_sha,
         "head_sha": head_sha,
         "start_sha": start_sha,
         "position_type": "text",
         "new_path": file_path,
         "old_path": file_path,  # リネームの場合は旧パス
         "new_line": line if line_type == "new" else None,
         "old_line": line if line_type == "old" else None
       }
     })
  4. 作成されたノートを Note に変換して返す
出力: Note
```

### 3.3 MR全体ノート投稿

```
入力: mr_iid (int), body (str)
処理:
  1. バリデーション：body が空でないことを確認
  2. mr.notes.create({"body": body})
  3. 作成されたノートを Note に変換して返す
出力: Note
```

### 3.4 リプライ投稿

```
入力: mr_iid (int), discussion_id (str), body (str)
��理:
  1. バリデーション：body が空でないことを確認
  2. mr.discussions.get(discussion_id).notes.create({"body": body})
  3. ディスカッションが見つからない場合は DiscussionNotFoundError を送出��る
  4. 作成されたノートを Note に変換して返す
出力: Note
```

---

## 4. キャッシュ管理ロジック

### 4.1 セッション内メモリキャッシュ

```
キャッシュ対象:
  - MR詳細（MergeRequestDetail）: キー = mr_iid
  - 変更ファイル一覧（list[FileChange]）: キー = mr_iid
  - ファイル差分（FileDiff）: キー = (mr_iid, file_path)
  - ディスカッション（list[Discussion]）: キー = mr_iid

キャッシュ非対象（常にAPI呼び出し）:
  - MR一覧（カテゴリ別）— リストは頻繁に変化するため

キャッシュ無効化:
  - 明示的リフレッシュ操作時にすべてのキャッシュをクリアする
  - コメント投稿成功時に該当MRのディスカッションキャッシュをクリアする
```

---

## 5. データフロー概要

```
TUI層
  |
  | (非同期呼び出し)
  v
MRService / CommentService
  |
  | キャッシュ確認
  |   ├─ ヒット → キャッシュから返す
  |   └─ ミス → GitLabClient経由でAPI���び出し
  |                |
  |                v
  |            python-gitlab
  |                |
  |                v
  |            GitLab REST API
  |
  | python-gitlab オブジェクト → 内部データモデル変換
  |
  v
TUI層（MergeRequestSummary, MergeRequestDetail, FileDiff, Discussion 等）
```
