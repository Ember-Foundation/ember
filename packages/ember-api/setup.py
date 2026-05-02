"""
ember-api Cython build configuration.

Compiles the framework-layer hot paths: router, ai/ratelimit token bucket,
ai/sse writer. The HTTP protocol layer's Cython extensions live in the
emberloop package and are pulled in as a runtime dependency.

Build:
    pip install cython
    python setup.py build_ext --inplace
"""
import os
import platform
from setuptools import setup

try:
    from Cython.Build import cythonize
    from Cython.Distutils import Extension
    USE_CYTHON = True
except ImportError:
    from setuptools import Extension
    USE_CYTHON = False


SRC_ROOT = "src"


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


def make_extension(module_path: str) -> Extension:
    rel_path = module_path.replace(".", "/")
    suffix = ".pyx" if USE_CYTHON else ".c"
    compile_args, link_args = _platform_flags()
    return Extension(
        module_path,
        sources=[f"{SRC_ROOT}/{rel_path}{suffix}"],
        extra_compile_args=compile_args,
        extra_link_args=link_args,
    )


CYTHON_EXTENSIONS = [
    make_extension("ember.router.router"),
    make_extension("ember.ai.ratelimit.token_bucket"),
    make_extension("ember.ai.sse.sse_writer"),
]

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
