try:
    from .cprotocol import Connection, HTTPParser
except ImportError:
    from .protocol import Connection
    from .protocol import SimpleHTTPParser as HTTPParser

__all__ = ["Connection", "HTTPParser"]
