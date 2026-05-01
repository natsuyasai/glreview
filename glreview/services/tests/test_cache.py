"""glreview.services.cache のユニットテスト。"""

import pytest

from glreview.services.cache import LRUCache


class TestLRUCacheInit:
    def test_empty_on_init(self) -> None:
        cache: LRUCache[str, int] = LRUCache(10)
        assert len(cache) == 0

    def test_invalid_max_size(self) -> None:
        with pytest.raises(ValueError):
            LRUCache(0)

    def test_negative_max_size(self) -> None:
        with pytest.raises(ValueError):
            LRUCache(-1)


class TestLRUCacheGetSet:
    def test_set_and_get(self) -> None:
        cache: LRUCache[str, str] = LRUCache(5)
        cache.set("key", "value")
        assert cache.get("key") == "value"

    def test_get_missing_returns_none(self) -> None:
        cache: LRUCache[str, int] = LRUCache(5)
        assert cache.get("missing") is None

    def test_overwrite_existing(self) -> None:
        cache: LRUCache[str, int] = LRUCache(5)
        cache.set("k", 1)
        cache.set("k", 2)
        assert cache.get("k") == 2
        assert len(cache) == 1

    def test_contains(self) -> None:
        cache: LRUCache[str, int] = LRUCache(5)
        cache.set("k", 1)
        assert "k" in cache
        assert "missing" not in cache


class TestLRUCacheEviction:
    def test_evicts_lru_when_full(self) -> None:
        cache: LRUCache[int, str] = LRUCache(3)
        cache.set(1, "a")
        cache.set(2, "b")
        cache.set(3, "c")
        # アクセスで1と2のLRU順を更新
        cache.get(1)
        cache.get(2)
        # 4を追加 → 最も古い3が破棄される
        cache.set(4, "d")
        assert cache.get(3) is None
        assert cache.get(1) == "a"
        assert cache.get(2) == "b"
        assert cache.get(4) == "d"

    def test_len_does_not_exceed_max(self) -> None:
        cache: LRUCache[int, int] = LRUCache(3)
        for i in range(10):
            cache.set(i, i)
        assert len(cache) == 3


class TestLRUCacheDelete:
    def test_delete_existing(self) -> None:
        cache: LRUCache[str, int] = LRUCache(5)
        cache.set("k", 1)
        cache.delete("k")
        assert cache.get("k") is None
        assert len(cache) == 0

    def test_delete_missing_no_error(self) -> None:
        cache: LRUCache[str, int] = LRUCache(5)
        cache.delete("nonexistent")  # エラーなし


class TestLRUCacheClear:
    def test_clear(self) -> None:
        cache: LRUCache[str, int] = LRUCache(5)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.clear()
        assert len(cache) == 0
        assert cache.get("a") is None
