cdef class Headers:
    cdef list _raw
    cdef dict _index

    cpdef bytes get(self, bytes name, bytes default=*)
    cpdef str get_str(self, str name, str default=*)
    cpdef bint contains(self, bytes name)
    cpdef bytes serialize(self)
