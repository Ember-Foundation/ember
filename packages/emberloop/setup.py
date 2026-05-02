"""
emberloop Cython build configuration.

Compiles the io_uring event loop, llhttp-backed protocol parser, and the
Cython hot paths for headers/request/response objects. Pure-Python fallbacks
exist alongside each .pyx file and are used when Cython is not available.

Build:
    pip install cython
    python setup.py build_ext --inplace
"""
import os
import platform
import sys
from setuptools import setup

try:
    from Cython.Build import cythonize
    from Cython.Distutils import Extension
    USE_CYTHON = True
except ImportError:
    from setuptools import Extension
    USE_CYTHON = False


SRC_ROOT = "src"
LLHTTP_VENDOR = "vendor/llhttp"
LLHTTP_SOURCES = [
    f"{LLHTTP_VENDOR}/llhttp.c",
    f"{LLHTTP_VENDOR}/api.c",
    f"{LLHTTP_VENDOR}/http.c",
]


def _platform_flags() -> tuple[list[str], list[str]]:
    system = platform.system()
    if system == "Windows":
        return ["/O2", "/GS-"], []
    portable = os.environ.get("CIBUILDWHEEL") == "1"
    debug    = os.environ.get("EMBER_DEBUG")  == "1"
    compile_args = ["-O3", "-Wno-unused-variable", "-Wno-unused-function"]
    link_args    = ["-O3"]
    if not portable:
        compile_args[1:1] = ["-march=native", "-ffast-math"]
    if not portable and not debug:
        link_args.append("-Wl,-s")
    return compile_args, link_args


def make_extension(
    module_path: str,
    extra_sources: list[str] | None = None,
    include_dirs: list[str] | None = None,
) -> Extension:
    rel_path = module_path.replace(".", "/")
    suffix = ".pyx" if USE_CYTHON else ".c"
    sources = [f"{SRC_ROOT}/{rel_path}{suffix}"] + (extra_sources or [])
    compile_args, link_args = _platform_flags()
    return Extension(
        module_path,
        sources=sources,
        extra_compile_args=compile_args,
        extra_link_args=link_args,
        include_dirs=include_dirs or [],
    )


def make_uring_extension() -> "Extension | None":
    if sys.platform in ("win32", "darwin"):
        return None
    suffix = ".pyx" if USE_CYTHON else ".c"
    compile_args, link_args = _platform_flags()
    return Extension(
        "ember.eventloop.uring",
        sources=[f"{SRC_ROOT}/ember/eventloop/uring{suffix}"],
        include_dirs=["/usr/include"],
        libraries=["uring"],
        library_dirs=["/usr/lib/x86_64-linux-gnu"],
        extra_compile_args=compile_args,
        extra_link_args=link_args,
    )


CYTHON_EXTENSIONS = [
    make_extension("ember.headers.headers"),
    make_extension(
        "ember.protocol.cprotocol",
        extra_sources=LLHTTP_SOURCES,
        include_dirs=[LLHTTP_VENDOR],
    ),
    make_extension("ember.response.response"),
    make_extension("ember.request.request"),
]

_uring_ext = make_uring_extension()
if _uring_ext is not None:
    CYTHON_EXTENSIONS.append(_uring_ext)

if USE_CYTHON:
    extensions = cythonize(
        CYTHON_EXTENSIONS,
        include_path=[SRC_ROOT],
        compiler_directives={
            "language_level": "3",
            "boundscheck": False,
            "wraparound": False,
            "cdivision": True,
            "nonecheck": False,
            "profile": False,
            "linetrace": False,
        },
        annotate=False,
    )
else:
    extensions = []

setup(ext_modules=extensions)
