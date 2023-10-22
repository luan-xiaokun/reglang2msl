"""Create a parser for the RegLang language"""
import importlib.resources

from lark import Lark

from . import resources

with (importlib.resources.files(resources) / "reglang.lark").open("rt") as grammar_file:
    parser = Lark(grammar_file.read(), parser="lalr", strict=True)
