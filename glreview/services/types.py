"""GitLab API サービス層固有の型定義。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from glreview.models import MergeRequestSummary


class MRCategory(Enum):
    """MR一覧のカテゴリ分類。"""

    ASSIGNED_TO_ME = "assigned_to_me"
    REVIEWER_IS_ME = "reviewer_is_me"
    CREATED_BY_ME = "created_by_me"
    UNASSIGNED = "unassigned"
    ASSIGNED_TO_OTHERS = "assigned_to_others"


@dataclass
class PaginatedResult:
    """ページネーション付きMR一覧の結果。"""

    items: list[MergeRequestSummary]
    has_next_page: bool
    next_page: int | None
