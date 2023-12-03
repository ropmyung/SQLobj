"""
──────────────────────
OBJECTIVE INTERACTIVE™
──────────────────────
DEVELOPED BY: rop_e1013

A module that handles Redis database usage and utilites.
"""
import redis
from typing import Optional, Any
from enum import IntEnum

# == TYPE ALIASES == #
_Key = str | int | bytes


class BaseName(IntEnum):
    testdata = 0
    userdata = 1
    itemdata = 2
    reptdata = 3


class MemoryStore(redis.Redis):
    IP: str = "localhost"

    def __init__(self, name: BaseName) -> None:
        super().__init__(self.IP, 6379, int(name))

    def __getitem__(self, __key: _Key) -> int | str:
        value: bytes = self.get(__key)
        if value is None:
            raise KeyError(__key)
        if value.isdigit:
            return int(value)
        else:
            return value.decode()

    def __setitem__(self, __key: _Key, __value: Any) -> None:
        if isinstance(__value, dict): return self.mset(__value)
        if isinstance(__value, list): return self.lpush(__key, *__value)
        return self.set(__key, __value)

    def __delitem__(self, __key: str) -> None:
        self.delete(__key)

    def keys(self, pattern: str = "*", **kwargs) -> list[bytes]:
        return super().keys(pattern, **kwargs)

    def hgetall(self, name: _Key) -> dict[bytes, bytes]:
        return super().hgetall(name)

    def lindex(self, name: _Key, index: int) -> Optional[bytes]:
        return super().lindex(name, index)

    def lrange(self, name: _Key, start: int, end: int) -> list[bytes]:
        return super().lrange(name, start, end)

