import pytest
from showads_connector.batching import batched

def test_happy_path_chunk_sizes():
    items = list(range(10))            # 0..9
    chunks = list(batched(items, 4))   # expect 4,4,2
    assert chunks == [[0,1,2,3], [4,5,6,7], [8,9]]

def test_accepts_generator_and_last_partial():
    gen = (i for i in range(5))
    assert list(batched(gen, 2)) == [[0,1], [2,3], [4]]

def test_size_must_be_positive():
    with pytest.raises(ValueError):
        list(batched([1,2], 0))
    with pytest.raises(ValueError):
        list(batched([1,2], -3))

def test_empty_iterable_yields_nothing():
    assert list(batched([], 3)) == []
