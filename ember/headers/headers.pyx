# cython: language_level=3, boundscheck=False, wraparound=False, nonecheck=False
"""Cython-compiled HTTP headers container."""

cdef class Headers:
    def __init__(self, list raw):
        self._raw = raw
        self._index = {k.lower(): v for k, v in raw}

    cpdef bytes get(self, bytes name, bytes default=None):
        return self._index.get(name.lower(), default)

    cpdef str get_str(self, str name, str default=None):
        cdef bytes value = self._index.get(name.encode('latin-1'), None)
        if value is None:
            return default
        return value.decode('latin-1')

    cpdef bint contains(self, bytes name):
        return name.lower() in self._index

    def __contains__(self, bytes name):
        return self.contains(name)

    def __iter__(self):
        return iter(self._raw)

    def __len__(self):
        return len(self._raw)

    cpdef bytes serialize(self):
        cdef list parts = []
        for k, v in self._raw:
            parts.append(k + b': ' + v + b'\r\n')
        return b''.join(parts)

    def to_dict(self):
        return {k.decode('latin-1'): v.decode('latin-1') for k, v in self._raw}
