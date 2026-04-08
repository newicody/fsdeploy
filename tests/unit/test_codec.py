"""
Unit tests for HuffmanCodec and RecordStore.
"""
import struct
import tempfile
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from fsdeploy.lib.scheduler.intentlog.codec import (
    HuffmanCodec, Record, RecordStore, HuffmanStore
)


def test_huffman_codec_basic():
    codec = HuffmanCodec(rebuild_threshold=10)
    # observe tokens
    tokens = ["pool.boot", "pool.import", "pool.boot", "dataset.mount"]
    for t in tokens:
        codec.observe(t)
    assert codec.vocabulary_size == 3
    # force rebuild
    codec.force_rebuild()
    # encode single token
    blob = codec.encode_tokens(["pool.boot"])
    decoded = codec.decode_tokens(blob)
    assert decoded == ["pool.boot"]
    # encode multiple
    blob = codec.encode_tokens(["pool.boot", "dataset.mount"])
    decoded = codec.decode_tokens(blob)
    assert decoded == ["pool.boot", "dataset.mount"]
    # unknown token (should use escape)
    blob = codec.encode_tokens(["unknown.token"])
    decoded = codec.decode_tokens(blob)
    assert decoded == ["unknown.token"]
    # stats
    ratio = codec.compression_ratio()
    assert 0.0 < ratio <= 2.0  # reasonable range
    print("test_huffman_codec_basic passed")


def test_record_store():
    codec = HuffmanCodec(rebuild_threshold=5)
    store = RecordStore(codec, "test")
    rec = Record(
        timestamp=123456.789,
        category="event",
        action="started",
        tokens=["pool.boot", "src:cli"],
        meta={"extra": 1}
    )
    idx = store.append(rec)
    assert idx == 0
    assert store.count == 1
    # retrieve
    retrieved = store.get(idx)
    assert retrieved is not None
    assert retrieved.category == "event"
    assert retrieved.action == "started"
    assert retrieved.tokens == ["pool.boot", "src:cli"]
    # query by category
    by_cat = store.by_category("event")
    assert len(by_cat) == 1
    # query by prefix
    by_prefix = store.by_prefix("pool")
    assert len(by_prefix) == 1
    # multiple records
    rec2 = Record(
        timestamp=123457.0,
        category="task",
        action="completed",
        tokens=["task.import", "pool.boot"],
        meta={}
    )
    store.append(rec2)
    assert store.count == 2
    last_two = store.last(2)
    assert len(last_two) == 2
    assert last_two[0].category == "event"
    assert last_two[1].category == "task"
    print("test_record_store passed")


def test_huffman_store_snapshot():
    store = HuffmanStore(rebuild_threshold=5)
    # log some events
    store.log_event("boot.request", source="ui")
    store.log_task("compile_kernel", "started", task_class="KernelCompileTask")
    store.log_resource("pool.boot", "imported", owner="root")
    # snapshot
    snap = store.snapshot()
    assert "active_tasks" in snap
    assert "resources" in snap
    assert "counts" in snap
    # query
    events = store.history("events", limit=2)
    assert len(events) >= 1
    # stats
    stats = store.stats()
    assert "total_records" in stats
    assert stats["total_records"] >= 3
    print("test_huffman_store_snapshot passed")


def test_prune():
    codec = HuffmanCodec(rebuild_threshold=5)
    tokens = ["a", "a", "a", "b", "b", "c"]  # a freq3, b freq2, c freq1
    for t in tokens:
        codec.observe(t)
    codec.force_rebuild()
    assert codec.vocabulary_size == 3
    # prune min_freq=2 -> c removed
    removed = codec.prune(min_freq=2)
    assert removed == 1
    assert codec.vocabulary_size == 2
    # after rebuild, only a and b present
    top = codec.top_tokens(5)
    tokens_top = [tok for tok, _, _ in top]
    assert "a" in tokens_top
    assert "b" in tokens_top
    assert "c" not in tokens_top
    print("test_prune passed")


if __name__ == "__main__":
    test_huffman_codec_basic()
    test_record_store()
    test_huffman_store_snapshot()
    test_prune()
    print("All tests passed!")
