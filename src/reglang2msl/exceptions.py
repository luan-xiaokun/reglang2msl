"""Code translation exceptions"""


class TranslationException(Exception):
    """Base exception class for RegLang2Msl translation"""


class InterpretationError(TranslationException):
    """Exception that occurs during interpretation execution"""


class MaxRuleStatementError(TranslationException):
    """Too many checking statements in a single rule"""
