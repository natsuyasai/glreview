"""セッション内メモリLRUキャッシュ。"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Hashable
from typing import Generic, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


class LRUCache(Generic[K, V]):
    """エントリ数上限付きLRUキャッシュ。

    asyncioシングルスレッド環境での使用を想定。スレッドセーフではない。
    上限超過時は最も古く使われていないエントリを破棄する。
    """

    def __init__(self, max_size: int) -> None:
        if max_size <= 0:
            raise ValueError("max_size must be positive")
        self._max_size = max_size
        self._cache: OrderedDict[K, V] = OrderedDict()

    def get(self, key: K) -> V | None:
        """キーに対応する値を返す。存在しない場合はNoneを返す。アクセスでLRU順を更新する。"""
        if key not in self._cache:
            return None
        self._cache.move_to_end(key)
        return self._cache[key]

    def set(self, key: K, value: V) -> None:
        """キーと値をキャッシュに保存する。上限超過時はLRUエントリを破棄する。"""
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self._max_size:
            self._cache.popitem(last=False)

    def delete(self, key: K) -> None:
        """指定キーのエントリを削除する。存在しない場合は何もしない。"""
        self._cache.pop(key, None)

    def clear(self) -> None:
        """すべてのキャッシュエントリを削除する。"""
        self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)

    def __contains__(self, key: object) -> bool:
        return key in self._cache
