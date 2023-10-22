"""Translate RegLang specification into MSL code"""
from ._parser import parser
from ._version import __version__
from .translator import CodeGenerator

__all__ = ["CodeGenerator", "parser"]
