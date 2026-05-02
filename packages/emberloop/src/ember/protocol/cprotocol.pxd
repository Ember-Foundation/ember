# cython: language_level=3
# Declaration file for cprotocol — cimport this to use HTTPParser from other .pyx files.

cdef extern from "llhttp.h":
    struct llhttp__internal_s:
        void*         data
        unsigned char method
        unsigned char upgrade
    ctypedef llhttp__internal_s llhttp_t

    ctypedef int (*llhttp_data_cb)(llhttp_t*, const char*, size_t) noexcept
    ctypedef int (*llhttp_cb)(llhttp_t*) noexcept

    struct llhttp_settings_s:
        llhttp_cb      on_message_begin
        llhttp_data_cb on_url
        llhttp_data_cb on_status
        llhttp_data_cb on_header_field
        llhttp_data_cb on_header_value
        llhttp_cb      on_headers_complete
        llhttp_data_cb on_body
        llhttp_cb      on_message_complete
        llhttp_cb      on_url_complete
        llhttp_cb      on_status_complete
        llhttp_cb      on_header_field_complete
        llhttp_cb      on_header_value_complete
        llhttp_cb      on_chunk_header
        llhttp_cb      on_chunk_complete
        llhttp_cb      on_reset
    ctypedef llhttp_settings_s llhttp_settings_t

    ctypedef enum llhttp_type_t:
        HTTP_BOTH     = 0
        HTTP_REQUEST  = 1
        HTTP_RESPONSE = 2

    void          llhttp_settings_init(llhttp_settings_t* settings)
    void          llhttp_init(llhttp_t* parser, llhttp_type_t type_,
                              const llhttp_settings_t* settings)
    int           llhttp_execute(llhttp_t* parser, const char* data, size_t length)
    void          llhttp_reset(llhttp_t* parser)
    unsigned char llhttp_get_method(const llhttp_t* parser)
    const char*   llhttp_method_name(unsigned int method)
    int           llhttp_should_keep_alive(const llhttp_t* parser)


cdef class HTTPParser:
    cdef llhttp_t          _parser
    cdef llhttp_settings_t _settings
    cdef public object     _conn
    cdef bytearray         _url_buf
    cdef bytearray         _hdr_field_buf
    cdef bytearray         _hdr_value_buf
    cdef list              _headers
    cdef bint              _headers_done

    cpdef int  feed(self, bytes data) except -1
    cpdef void reset(self)
