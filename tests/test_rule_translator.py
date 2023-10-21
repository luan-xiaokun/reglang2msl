"""
Test RuleTranslator
"""
from typing import List

from lark import Lark

from reglang2msl.rule_translator import RuleTransitionBuilder, RuleTranslator


rtb = RuleTransitionBuilder()
rt = RuleTranslator()


def test_rule_translator(parser: Lark, test_examples: List[str]):
    """Test RuleTranslator on RegLang examples"""
    for example in test_examples:
        result = parser.parse(example)

        rtb.transform(result)
        rt.translate(result)
