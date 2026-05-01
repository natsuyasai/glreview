"""TUI Application 固有のドメインエンティティ。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from glreview.services.types import MRCategory


class DiffViewMode(Enum):
    """差分表示モード。"""

    UNIFIED = "unified"
    SIDE_BY_SIDE = "side_by_side"


class TreeNodeType(Enum):
    """ツリーノードの種別。"""

    CATEGORY = "category"
    MR = "mr"
    OVERVIEW = "overview"
    FILE = "file"
    LOAD_MORE = "load_more"


@dataclass
class TreeNodeData:
    """ツリーノードに紐づくデータ。"""

    node_type: TreeNodeType
    mr_iid: int | None = None
    file_path: str | None = None
    category: MRCategory | None = None
    next_page: int | None = None


class ContentViewState(Enum):
    """右ペインの表示状態。"""

    EMPTY = "empty"
    OVERVIEW = "overview"
    DIFF = "diff"
    LOADING = "loading"
    ERROR = "error"


# カテゴリ表示ラベルマッピング
CATEGORY_LABELS: dict[MRCategory, str] = {
    MRCategory.ASSIGNED_TO_ME: "Assigned to me",
    MRCategory.REVIEWER_IS_ME: "Reviewer (me)",
    MRCategory.CREATED_BY_ME: "Created by me",
    MRCategory.UNASSIGNED: "Unassigned",
    MRCategory.ASSIGNED_TO_OTHERS: "Others",
}


def get_file_change_label(
    old_path: str, new_path: str, new_file: bool, deleted_file: bool, renamed_file: bool
) -> str:
    """FileChange の表示ラベルを生成する。"""
    if new_file:
        filename = new_path.split("/")[-1]
        return f"+ {filename} {new_path}"
    if deleted_file:
        filename = old_path.split("/")[-1]
        return f"- {filename} {old_path}"
    if renamed_file:
        filename = new_path.split("/")[-1]
        return f"r {filename} {old_path} → {new_path}"
    filename = new_path.split("/")[-1]
    return f"{filename} {new_path}"
