from collections.abc import Iterable, Iterator
from itertools import islice
from typing import TypeVar

T = TypeVar("T")

def batched(items: Iterable[T], size: int) -> Iterator[list[T]]:
    """
    Yield lists of up to `size` items from `items`, without loading all items into memory.
    Generic by type (T): Iterable[T] -> Iterator[list[T]].
    Note: API cap of 1000 is enforced in the ShowAds client, not here.
    """
    if size <= 0:
        raise ValueError("batch size must be > 0")
    it = iter(items)
    while True:
        chunk = list(islice(it, size))
        if not chunk:
            break
        yield chunk
