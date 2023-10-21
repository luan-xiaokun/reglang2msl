"""
Test Serializer
"""
from typing import List

from lark import Lark

from reglang2msl.rule_translator import RuleTransitionBuilder
from reglang2msl.utils import MslAstSerializer


rtb = RuleTransitionBuilder()
serializer = MslAstSerializer()


def test_msl_ast_serializer(parser: Lark, test_examples: List[str]):
    """Test serializer on RegLang examples"""
    for example in test_examples:
        result = parser.parse(example)

        msl_ast = rtb.transform(result)
        serializer.visit(msl_ast)
