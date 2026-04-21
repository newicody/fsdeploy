"""
Test unitaire pour HuffmanCodec et RecordStore.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/../../..")

from fsdeploy.lib.scheduler.intentlog.codec import HuffmanCodec
from fsdeploy.lib.scheduler.intentlog.codec import RecordStore, Record
import time

def test_huffman_basic():
    codec = HuffmanCodec()
    tokens = ["event.start", "event.end", "event.start", "pool.tank"]
    codec.observe_many(tokens)
    encoded = codec.encode_tokens(tokens)
    decoded = codec.decode_tokens(encoded)
    assert decoded == tokens
    ratio = codec.compression_ratio()
    assert ratio >= 0.0
    top = codec.top_tokens(2)
    assert len(top) >= 1

def test_record_store_basic():
    store = RecordStore()
    record = Record(
        timestamp=time.time(),
        category="test",
        severity="info",
        tokens=["test.record", "value"]
    )
    idx = store.append(record)
    retrieved = store.get(idx)
    assert retrieved is not None
    assert retrieved.tokens == record.tokens
    assert retrieved.category == record.category

def test_huffman_store_integration():
    from fsdeploy.lib.scheduler.intentlog.codec import HuffmanStore
    store = HuffmanStore()
    # Log an event
    store.log_event("test.event", source="test", severity="debug", foo="bar")
    # No assertion, just ensure no exception
