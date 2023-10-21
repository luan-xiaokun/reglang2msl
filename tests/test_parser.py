"""
Test RegLang parser
"""
from typing import List

from lark import Lark


def test_parsing_reglang_examples(parser: Lark, test_examples: List[str]):
    """Test parsing RegLang examples"""
    for example in test_examples:
        parser.parse(example)
