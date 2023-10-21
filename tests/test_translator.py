"""
Test Translator
"""
from typing import List

from lark import Lark

from reglang2msl.translator import CodeGenerator


cg = CodeGenerator()


def test_code_generator(parser: Lark, test_examples: List[str]):
    """Test CodeGenerator on RegLang examples"""
    for example in test_examples:
        result = parser.parse(example)

        print(cg.generate(result))
