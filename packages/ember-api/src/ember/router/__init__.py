try:
    from .router import Router, Route, AIRoute, LRUCache, RouterStrategy
except ImportError:
    from .router import Router, Route, AIRoute, LRUCache, RouterStrategy

__all__ = ["Router", "Route", "AIRoute", "LRUCache", "RouterStrategy"]
