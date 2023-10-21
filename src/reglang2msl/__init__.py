from importlib import resources as impresources

from lark import Lark

from . import resources
from ._version import __version__
from .translator import CodeGenerator

with (impresources.files(resources) / "reglang.lark").open("rt") as grammar_file:
    parser = Lark(grammar_file.read(), parser="lalr", strict=True)

__all__ = ["CodeGenerator", "parser"]
