"""Test satisfiability checker"""
from typing import List

from lark import Lark

from reglang2msl.knowledge_base_translator import KnowledgeBaseInterpreter
from reglang2msl.rule_translator import RuleTransitionBuilder
from reglang2msl.se import RuleSatChecker

kbi = KnowledgeBaseInterpreter()
rtb = RuleTransitionBuilder()


def test_sat_checker(parser: Lark, test_examples: List[str]):
    """Test satisfiability checker on RegLang examples"""
    # with open("tests/reglang_examples/example2.rl", "r", encoding="utf-8") as example_file:
    #     example = example_file.read()
    for example in test_examples:
        result = parser.parse(example)

        kb_dict = kbi.visit(result)
        msl_ast = rtb.transform(result)

        rsc = RuleSatChecker(kb_dict)
        rsc.visit(msl_ast)
