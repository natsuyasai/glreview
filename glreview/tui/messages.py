"""TUI Application コンポーネント間のメッセージ定義。"""

from __future__ import annotations

from textual.message import Message


class ShowOverview(Message):
    """MR Overview表示リクエストメッセージ。MRListPanel → ContentPanel。"""

    def __init__(self, mr_iid: int) -> None:
        super().__init__()
        self.mr_iid = mr_iid


class ShowDiff(Message):
    """ファイル差分表示リクエストメッセージ。MRListPanel → ContentPanel。"""

    def __init__(self, mr_iid: int, file_path: str) -> None:
        super().__init__()
        self.mr_iid = mr_iid
        self.file_path = file_path


class CommentPosted(Message):
    """下書きコメント追加完了メッセージ。CommentDialog → ContentPanel。"""

    def __init__(self, mr_iid: int) -> None:
        super().__init__()
        self.mr_iid = mr_iid


class ReviewSubmitted(Message):
    """レビュー送信(下書き一括公開)完了メッセージ。SubmitReviewDialog → ContentPanel。"""

    def __init__(self, mr_iid: int) -> None:
        super().__init__()
        self.mr_iid = mr_iid
