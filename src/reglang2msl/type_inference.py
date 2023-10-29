"""Type inference for MSL ASTs"""
from typing import Dict, Union

from lark import Tree, Token
from lark.visitors import Interpreter, v_args

from .knowledge_base_translator import KnowledgeBaseType, KnowledgeType


@v_args(inline=True)
class MslTypeInference(Interpreter):
    """Type inference for MSL ASTs

    A map from AST nodes to their inferred types is stored in `self.types`.
    We are not going to visit every node in the AST, but only those that are
    relevant to sat checking.

    For some AST node type, we already know its type, and we can infer its
    children's types. For example, the children of a logical connective term
    (not, and, or) are always bool, and the children of an arithmetic term
    (add, mul, power) are always int.

    There may be more than one valid type for its children, e.g., the children
    of an equality term (eq, neq) can be either int or string. In this case,
    we will first visit its children, and if we can infer one of their types,
    we can infer the other one's type as well.

    The most tricky case is a node with no known type and has no children
    (or we cannot infer concrete type from its children). For example, a
    variable reference node (which is not a knowledge reference). In this case,
    we have to infer its type from the context. For example, if it is used in
    an equality term, then its type is either int or string. If it is used in
    an arithmetic term, then its type is int.
    """

    def __init__(self, kb_dict: Dict[str, KnowledgeBaseType]) -> None:
        super().__init__()
        self.knowledge_type = {
            f"{kb_name}_{k_name}": self._get_knowledge_type(k)
            for kb_name, kb in kb_dict.items()
            for k_name, k in kb.items()
        }
        self.types: Dict[Tree[Token], str] = {}

    def _get_knowledge_type(self, knowledge: KnowledgeType) -> str:
        if isinstance(knowledge, int):
            return "int"
        if isinstance(knowledge, str):
            return "string"
        assert isinstance(knowledge, list) and len(knowledge) > 0
        if isinstance(knowledge[0], int):
            return "int[]"
        assert isinstance(knowledge[0], str)
        return "string[]"

    def transition_body(self, *stmts: Tree[Token]):
        """Entrance point for type inference"""
        assert all(stmt.data in ["skip_stmt", "assign_stmt"] for stmt in stmts)

        for stmt in filter(lambda stmt: stmt.data == "assign_stmt", stmts):
            # each assign_stmt should look like: output.value = cond ? then : output.value
            assert len(stmt.children) == 3
            output_value, equal_sign, cond_value = stmt.children
            assert isinstance(output_value, Tree) and output_value.data == "getattr"
            assert isinstance(equal_sign, Token) and equal_sign.value == "="
            assert isinstance(cond_value, Tree) and cond_value.data == "conditional_expr"

            self.types[output_value] = "int"
            self.types[cond_value] = "int"

            assert len(cond_value.children) == 3
            guard, then_value, else_value = cond_value.children
            self.types[guard] = "bool"
            self.types[then_value] = "int"
            self.types[else_value] = "int"

            conditions = [guard]
            candidate = then_value
            while isinstance(candidate, Tree) and candidate.data == "conditional_expr":
                assert len(candidate.children) == 3
                conditions.append(candidate.children[0])
                candidate = candidate.children[2]
            assert isinstance(candidate, Tree) and candidate.data == "getattr"

            for cond in conditions:
                self.types[cond] = "bool"
                self.visit(cond)

        return self.types

    def not_expr(self, operand: Tree[Token]) -> str:
        """Negation's operand should be bool"""
        self.types[operand] = "bool"
        self.visit(operand)
        return "bool"

    def and_expr(self, left: Tree[Token], right: Tree[Token]) -> str:
        """Conjunction's left and right terms should be bool"""
        self.types[left] = "bool"
        self.types[right] = "bool"
        self.visit(left)
        self.visit(right)
        return "bool"

    def or_expr(self, left: Tree[Token], right: Tree[Token]) -> str:
        """Disjunction's left and right terms should be bool"""
        self.types[left] = "bool"
        self.types[right] = "bool"
        self.visit(left)
        self.visit(right)
        return "bool"

    def compare_expr(self, left: Tree[Token], _: Token, right: Tree[Token]) -> str:
        """Comparison's left and right terms should be int"""
        self.types[left] = "int"
        self.types[right] = "int"
        self.visit(left)
        self.visit(right)
        return "bool"

    def equality_expr(self, left: Tree[Token], _: Token, right: Tree[Token]) -> str:
        """Equality's left and right terms should be int or string, and have the same type"""
        left_type = self.visit(left)
        right_type = self.visit(right)
        if left_type == "int" or right_type == "int":
            self.types[left] = "int"
            self.types[right] = "int"
            return "bool"
        if left_type == "string" or right_type == "string":
            self.types[left] = "string"
            self.types[right] = "string"
            return "bool"
        assert left_type == right_type == "unknown", f"{left_type} != {right_type}"
        self.types[left] = "int"
        self.types[right] = "int"
        return "bool"

    def add_expr(self, left: Tree[Token], _: Token, right: Tree[Token]) -> str:
        """Addition's left and right terms should be int"""
        self.types[left] = "int"
        self.types[right] = "int"
        self.visit(left)
        self.visit(right)
        return "int"

    def mul_expr(self, left: Tree[Token], _: Token, right: Tree[Token]) -> str:
        """Multiplication's left and right terms should be int"""
        self.types[left] = "int"
        self.types[right] = "int"
        self.visit(left)
        self.visit(right)
        return "int"

    def power_expr(self, base: Tree[Token], exponent: Tree[Token]) -> str:
        """Power's base and exponent should be int"""
        self.types[base] = "int"
        self.types[exponent] = "int"
        self.visit(base)
        self.visit(exponent)
        return "int"

    def func_call(self, *children: Union[Tree[Token], Token]) -> str:
        """Function call"""
        assert len(children) in [2, 3] and isinstance(children[0], Token)
        assert isinstance(children[-1], Tree) and children[-1].data == "func_arguments"
        this_tree = Tree("func_call", list(children))
        func_name = str(children[0].value)
        arguments = children[-1].children

        if func_name == "length":
            assert len(arguments) == 1
            array_type = self.visit(arguments[0])
            if array_type not in ["int[]", "string[]"]:
                array_type = "any[]"
            self.types[arguments[0]] = array_type
            return self.types.get(this_tree, "int")

        if func_name == "reglang.count":
            assert len(arguments) == 1
            assert isinstance(arguments[0], Tree) and arguments[0].data == "array"
            elements = arguments[0].children
            for elem in elements:
                self.types[elem] = "bool"
                self.visit(elem)
            return self.types.get(this_tree, "int")

        if func_name == "reglang.count_member":
            assert len(arguments) == 2 and isinstance(arguments[1], Tree)
            assert isinstance(arguments[0], Tree) and arguments[0].data == "var_ref"

            knowledge_type = self.visit(arguments[0])
            assert knowledge_type in ["int[]", "string[]"]
            self.types[arguments[1]] = knowledge_type

            array_type = self.visit(arguments[1])
            assert array_type == knowledge_type or arguments[1].data == "getitem"
            return self.types.get(this_tree, "int")

        if func_name == "reglang.contains":
            assert len(arguments) == 2 and isinstance(arguments[1], Tree)
            assert isinstance(arguments[0], Tree) and arguments[0].data == "var_ref"

            knowledge_type = self.visit(arguments[0])
            assert knowledge_type in ["int[]", "string[]"]
            self.types[arguments[1]] = knowledge_type[:-2]

            self.visit(arguments[1])
            return self.types.get(this_tree, "bool")

        assert func_name in [
            "reglang.count_eq",
            "reglang.count_neq",
            "reglang.count_le",
            "reglang.count_ge",
            "reglang.count_lt",
            "reglang.count_gt",
        ]
        assert len(arguments) == 2
        assert isinstance(arguments[0], Tree) and isinstance(arguments[1], Tree)
        # element 0 is an array, element 1 is a single value
        array_type = self.visit(arguments[0])
        element_type = self.visit(arguments[1])

        assert element_type in ["int", "string"] or array_type in [
            "int[]",
            "string[]",
        ], "at least one argument should has valid type"

        if element_type in ["int", "string"]:
            self.types[arguments[0]] = element_type + "[]"
            self.types[arguments[1]] = element_type
        else:
            self.types[arguments[0]] = array_type
            self.types[arguments[1]] = array_type[:-2]

        return self.types.get(this_tree, "int")

    def var_ref(self, var: Token) -> str:
        """There are two cases for a variable reference:
        1. a knowledge reference, e.g., `kb_name`_`k_name`
        2. a true variable reference
        For the second case, we need to infer its type from the context.
        """
        this_tree = Tree("var_ref", [var])
        var_name = str(var.value)
        var_type = self.knowledge_type.get(var_name, "unknown")
        return self.types.get(this_tree, var_type)

    # 1. tx_basic: getattr[tx_var, from/to/function], string type
    # 2. tx_state: getitem[getitem[getattr[tx_var, readset/writeset], arith], var_ref]
    # 3. tx_args: getitem[getattr[tx_var, args], var_ref]
    # 4. contract_basic: getattr[getitem[contract, arith], name/owner], string type
    # 5. contract_state: getitem[getattr[getitem[contract, arith], state], var_ref]
    # 6. array_item: getitem[anything, arith]

    def getitem(self, obj: Tree[Token], index: Tree[Token]) -> str:
        """Getitem

        Note that getitem node should NEVER be visited recursively
        """
        this_tree = Tree("getitem", [obj, index])
        # if this is an array_item, index should be a number
        if index.data != "string":
            self.types[index] = "int"
            self.visit(index)
        return self.types.get(this_tree, "unknown")

    def getattr(self, obj: Tree[Token], attr: Token) -> str:
        """Getattr"""
        assert isinstance(attr, Token) and attr.type == "NAME"
        this_tree = Tree("getattr", [obj, attr])
        attr_name = str(attr.value)

        if (
            attr_name == "value"
            and obj.data == "var_ref"
            and isinstance(obj.children[0], Token)
            and obj.children[0].value == "output"
        ):
            # output.value, special case
            return "int"

        if (
            attr_name in ["from", "to", "function"]
            and obj.data == "var_ref"
            and isinstance(obj.children[0], Token)
            and obj.children[0].value == "tx"
        ):
            # tx_basic, string value
            return "string"

        if (
            attr_name in ["name", "owner"]
            and obj.data == "getitem"
            and isinstance(obj.children[0], Tree)
            and obj.children[0].data == "var_ref"
            and isinstance(obj.children[0].children[0], Token)
            and obj.children[0].children[0].value == "contract"
        ):
            # contract_basic, string value
            return "string"

        return self.types.get(this_tree, "unknown")

    def array(self, *children: Union[Tree[Token], Token]) -> str:
        """There are three cases for array's children:
        1. number array,  [NUMBER (, NUMBER)*]
        2. string array, [STRING (, STRING)*]
        3. boolean array, [bool_expr (, bool_expr)*]
        """
        assert len(children) > 0, "expecting at least one element in array"
        if isinstance(children[0], Token) and children[0].type == "NUMBER":
            assert all(isinstance(child, Token) and child.type == "NUMBER" for child in children)
            return "int[]"
        if isinstance(children[0], Token) and children[0].type == "STRING":
            assert all(isinstance(child, Token) and child.type == "STRING" for child in children)
            return "string[]"
        assert all(isinstance(child, Tree) for child in children)
        for child in children:
            self.types[child] = "bool"
            self.visit(child)
        return "bool[]"

    def const_true(self) -> str:
        """True's type is bool"""
        return "bool"

    def const_false(self) -> str:
        """False's type is bool"""
        return "bool"

    def number(self, _: Token) -> str:
        """Number's type is always int"""
        return "int"

    def string(self, _: Token) -> str:
        """String's type is int"""
        return "string"
