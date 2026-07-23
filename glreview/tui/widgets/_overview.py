"""MR Overview 表示テキスト構築・コメント位置管理。"""

from __future__ import annotations

import re

from glreview.models import Discussion, MergeRequestDetail, Note

_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def _drafts_as_discussions(drafts: list[Note]) -> list[Discussion]:
    """下書きノートのリストを、表示用の疑似 Discussion のリストに変換する。

    公開済みディスカッションと同じ描画経路(コメントマーカー・一覧表示)を
    再利用するための変換。各下書きは 1件ずつ独立した Discussion として扱う。
    """
    return [Discussion(id=f"draft-{note.id}", notes=[note]) for note in drafts]


def _extract_images(text: str) -> list[tuple[str, str]]:
    """Markdownテキストから画像リンクを抽出して (alt, url) リストを返す。"""
    return _IMAGE_PATTERN.findall(text)


def _build_overview_text(mr_detail: MergeRequestDetail, discussions: list[Discussion]) -> str:
    """MR詳細とディスカッションからOverview表示テキストを構築する。"""
    lines: list[str] = []
    lines.append(f"# !{mr_detail.iid} {mr_detail.title}")
    lines.append("")
    lines.append("| Field      | Value                          |")
    lines.append("|------------|-------------------------------|")
    lines.append(f"| Author     | {mr_detail.author}            |")
    lines.append(f"| Assignee   | {mr_detail.assignee or '—'}   |")
    lines.append(f"| Status     | {mr_detail.status}            |")
    lines.append(f"| Labels     | {', '.join(mr_detail.labels) or '—'} |")
    lines.append(f"| Milestone  | {mr_detail.milestone or '—'}  |")
    lines.append(f"| Pipeline   | {mr_detail.pipeline_status or '—'} |")
    lines.append(f"| URL        | {mr_detail.web_url}           |")
    lines.append(f"| Created    | {mr_detail.created_at}        |")
    lines.append(f"| Updated    | {mr_detail.updated_at}        |")
    lines.append("")
    lines.append("## Description")
    lines.append("")
    lines.append(mr_detail.description or "(no description)")
    lines.append("")

    # 説明文・ディスカッション内の画像URLを収集して表示
    all_images: list[tuple[str, str]] = []
    if mr_detail.description:
        all_images.extend(_extract_images(mr_detail.description))
    for disc in discussions:
        for note in disc.notes:
            all_images.extend(_extract_images(note.body))
    if all_images:
        lines.append(f"## Images ({len(all_images)})")
        lines.append("")
        for alt, url in all_images:
            label = alt if alt else url
            lines.append(f"- [{label}]({url})")
        lines.append("")

    draft_count = sum(1 for disc in discussions for note in disc.notes if note.is_draft)
    heading = f"## Discussions ({len(discussions)})"
    if draft_count:
        heading += f" — {draft_count} draft pending review"
    lines.append(heading)
    for disc in discussions:
        for i, note in enumerate(disc.notes):
            prefix = "  " if i > 0 else ""
            pos_info = ""
            if note.position is not None:
                line_no = note.position.new_line or note.position.old_line
                pos_info = f" [{note.position.file_path}:{line_no}]"
            draft_tag = "[DRAFT] " if note.is_draft else ""
            lines.append(f"{prefix}{draft_tag}**{note.author}**{pos_info} ({note.created_at})")
            for body_line in note.body.splitlines():
                lines.append(f"{prefix}  {body_line}")
            lines.append("")
    return "\n".join(lines)


def _get_comment_lines(discussions: list[Discussion], file_path: str) -> set[int]:
    """インラインコメントが付いている行番号の集合を返す。"""
    lines: set[int] = set()
    for disc in discussions:
        for note in disc.notes:
            if note.position is not None and note.position.file_path == file_path:
                if note.position.new_line is not None:
                    lines.add(note.position.new_line)
                elif note.position.old_line is not None:
                    lines.add(note.position.old_line)
    return lines


def _build_comment_map(
    discussions: list[Discussion], file_path: str
) -> dict[int, list[Discussion]]:
    """行番号 → ディスカッションリストのマップを構築する。"""
    result: dict[int, list[Discussion]] = {}
    for disc in discussions:
        for note in disc.notes:
            if note.position is not None and note.position.file_path == file_path:
                line_no = note.position.new_line or note.position.old_line
                if line_no is not None:
                    if line_no not in result:
                        result[line_no] = []
                    if disc not in result[line_no]:
                        result[line_no].append(disc)
    return result
