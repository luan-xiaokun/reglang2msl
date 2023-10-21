"""
Test KnowledgeBaseInterpreter and KnowledgeBaseTranslator
"""
from typing import List

import pytest
from lark import Lark

from reglang2msl.knowledge_base_translator import (
    KnowledgeBaseInterpreter,
    KnowledgeBaseTranslator,
)
from reglang2msl.exceptions import InterpretationError


kbi = KnowledgeBaseInterpreter()
kbt = KnowledgeBaseTranslator()


def test_knowledge_base_translator(parser: Lark, test_examples: List[str]):
    """Test KnowledgeBaseInterpreter and KnowledgeBaseTranslator on RegLang examples"""
    for example in test_examples:
        result = parser.parse(example)

        kb_dict = kbi.visit(result)
        kbt.translate(kb_dict)


def test_undefined_knowledge(parser: Lark):
    """Test undefined knowledge"""
    text = """
        knowledgebase erroneous_knowledge
        knowledge foo = 2;
        bar.add(1);
        end
    """
    with pytest.raises(InterpretationError):
        kbi.visit(parser.parse(text))


def test_alter_non_array_knowledge(parser: Lark):
    """Test altering non-array knowledge"""
    text = """
        knowledgebase erroneous_knowledge
        knowledge foo = 2;
        foo.add(1);
        end
    """
    with pytest.raises(InterpretationError):
        kbi.visit(parser.parse(text))


def test_int_and_str_array_type(parser: Lark):
    """Test add int to str array and vice versa"""
    text = """
        knowledgebase int_str_array
        knowledge foo = [2];
        foo.add("1");
        knowledge bar = ["2"];
        bar.add(1);
        end
    """
    kbi.visit(parser.parse(text))


def test_invalid_arith(parser: Lark):
    """Test invalid arithmetic with wrong types"""
    text_list = [
        'knowledgebase invalid_arith knowledge foo = "bar" + 1; end',
        'knowledgebase invalid_arith knowledge foo = "0x1" + "baz"; end',
        'knowledgebase invalid_arith knowledge foo = "bar" * "1"; end',
        'knowledgebase invalid_arith knowledge foo = 10 * "baz"; end',
    ]
    for text in text_list:
        with pytest.raises(InterpretationError):
            kbi.visit(parser.parse(text))


def test_forbidden_variable_reference(parser: Lark):
    """Test forbidden variable reference"""
    tests = [
        "knowledgebase test knowledge foo = bar; end",
        "knowledgebase test knowledge foo = tx.from; end",
        "knowledgebase test knowledge foo = tx.readset(bar).baz; end",
        "knowledgebase test knowledge foo = tx.args.bar; end",
        "knowledgebase test knowledge foo = contract(bar).name; end",
        "knowledgebase test knowledge foo = contract(bar).state.baz; end",
        "knowledgebase test knowledge foo = count(true, false); end",
    ]
    for test in tests:
        with pytest.raises(InterpretationError):
            kbi.visit(parser.parse(test))


def test_array_item_access(parser: Lark):
    """Test array item access"""
    text = """
        knowledgebase array_item_access
        knowledge foo = [1, 2, 3];
        foo.add(4);
        end
        knowledgebase array_item_access_2
        knowledge bar = knowledgebase(array_item_access).foo[3];
        end
    """
    kbi.visit(parser.parse(text))


def test_invalid_array_index(parser: Lark):
    """Test array index out of range and invalid index type"""
    tests = [
        """
        knowledgebase array_item_access
        knowledge foo = [1, 2, 3];
        end
        knowledgebase array_item_access_2
        knowledge bar = knowledgebase(array_item_access).foo[3];
        end
    """
    ]
    tests.append(
        """
        knowledgebase array_item_access
        knowledge foo = [1, 2, 3];
        end
        knowledgebase array_item_access_2
        knowledge bar = knowledgebase(array_item_access).foo["baz"];
        end
    """
    )
    for test in tests:
        with pytest.raises(InterpretationError):
            kbi.visit(parser.parse(test))


def test_undefined_knowledge_name(parser: Lark):
    """Test undefined knowledge name"""
    text = """
        knowledgebase foo
        knowledge bar = 1;
        end
        knowledgebase baz
        knowledge bar = knowledgebase(foo).buz;
        end
    """
    with pytest.raises(InterpretationError):
        kbi.visit(parser.parse(text))


def test_undefined_knowledgebase(parser: Lark):
    """Test undefined knowledgebase"""
    text = """
        knowledgebase foo
        knowledge bar = 1;
        end
        knowledgebase baz
        knowledge bar = knowledgebase(buz).bar;
        end
    """
    with pytest.raises(InterpretationError):
        kbi.visit(parser.parse(text))


def test_length_usage(parser: Lark):
    """Test length usage"""
    text = """
        knowledgebase foo
        knowledge bar = length([1, 2, 3]);
        end
        knowledgebase baz
        knowledge buz = length(knowledgebase(foo).bar);
        end
    """
    with pytest.raises(InterpretationError):
        kbi.visit(parser.parse(text))


def test_power_expression(parser: Lark):
    """Test power expression"""
    valid_tests = [
        "knowledgebase test knowledge foo = 2 ^ 3; end",
        'knowledgebase test knowledge large = "10" ^ 4300; end',
    ]
    kbi.visit(parser.parse(valid_tests[0]))
    with pytest.warns(UserWarning):
        kbi.visit(parser.parse(valid_tests[1]))

    invalid_tests = [
        'knowledgebase test knowledge foo = 2 ^ "3.0"; end',
        'knowledgebase test knowledge foo = "2.0" ^ 3; end',
    ]
    for test in invalid_tests:
        with pytest.raises(InterpretationError):
            kbi.visit(parser.parse(test))
