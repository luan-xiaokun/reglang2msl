"""Test configuration for the project."""
from pathlib import Path
from typing import List

import pytest
from lark import Lark


@pytest.fixture(scope="module")
def parser() -> Lark:
    with open("src/reglang2msl/resources/reglang.lark", encoding="utf-8") as grammar_file:
        grammar = grammar_file.read()
    parser = Lark(grammar, parser="lalr", strict=True)
    return parser


@pytest.fixture(scope="module")
def test_examples() -> List[str]:
    examples_iter = Path("tests/reglang_examples").iterdir()
    tests = []
    for example_path in examples_iter:
        with open(example_path, "r", encoding="utf-8") as test_file:
            tests.append(test_file.read())
    return tests
