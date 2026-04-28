"""
Build Cython extensions for Ember.

Usage:
    python3 build_ext.py build_ext --inplace

Each extension is standalone — no cross-module cimport dependencies —
so they can be compiled in any order and the pure-Python fallbacks
remain intact if compilation is skipped.
"""
from setuptools import setup
from Cython.Build import cythonize
from Cython.Distutils import Extension
import os

ROOT = os.path.dirname(os.path.abspath(__file__))

COMPILER_DIRECTIVES = {
    "language_level": "3",
    "boundscheck": False,
    "wraparound": False,
    "cdivision": True,
    "nonecheck": False,
    "profile": False,
    "linetrace": False,
    "embedsignature": True,
}

COMPILE_ARGS = ["-O3", "-march=native", "-ffast-math", "-fno-strict-aliasing"]
LINK_ARGS    = ["-O3"]


def ext(dotted_module: str, extra_sources=None) -> Extension:
    path = dotted_module.replace(".", "/") + ".pyx"
    return Extension(
        dotted_module,
        sources=[path] + (extra_sources or []),
        extra_compile_args=COMPILE_ARGS,
        extra_link_args=LINK_ARGS,
    )


extensions = cythonize(
    [
        ext("ember.headers.headers"),
        ext("ember.ai.ratelimit.token_bucket"),
        ext("ember.ai.sse.sse_writer"),
    ],
    compiler_directives=COMPILER_DIRECTIVES,
    annotate=True,          # generates .html annotation files
    nthreads=os.cpu_count() or 4,
)

setup(
    name="ember",
    ext_modules=extensions,
)
