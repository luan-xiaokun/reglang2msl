"""Test type inference"""
from typing import List

from lark import Lark

from reglang2msl.knowledge_base_translator import KnowledgeBaseInterpreter
from reglang2msl.rule_translator import RuleTransitionBuilder
from reglang2msl.type_inference import MslTypeInference


kbi = KnowledgeBaseInterpreter()
rtb = RuleTransitionBuilder()


def test_type_inference(parser: Lark, test_examples: List[str]):
    """Test type inference on RegLang examples"""
    for example in test_examples:
        if "require tx.readset(tx.to).foo == contract(tx.to).state.bar;" in example:
            result = parser.parse(example)

            kb_dict = kbi.visit(result)
            msl_ast = rtb.transform(result)

            mti = MslTypeInference(kb_dict)
            mti.visit(msl_ast)
