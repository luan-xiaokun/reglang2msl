"""
Utility functions for code translation
"""
import string
import textwrap
from typing import Any, List, Optional, TypeGuard, Union

from lark import Token, Tree
from lark.visitors import Interpreter, v_args


def string2int(val: str) -> Optional[int]:
    """Convert a RegLang string into a number"""
    if val.startswith("0x") and all(c in string.hexdigits for c in set(val[2:])):
        result = int(val[2:], base=16)
    elif val.isdigit():
        result = int(val)
    else:
        result = None
    return result


def is_tree_list(items: List[Any]) -> TypeGuard[List[Tree[Token]]]:
    """Ensure the list only contains Tree objects"""
    return all(isinstance(item, Tree) for item in items)


def is_token_list(items: List[Any]) -> TypeGuard[List[Token]]:
    """Ensure the list only contains Token objects"""
    return all(isinstance(item, Token) for item in items)


@v_args(inline=True)
class MslAstSerializer(Interpreter):
    """Serialize MSL AST into plain MSL code"""

    precedence = {
        "power_expr": 1,
        "mul_expr": 2,
        "add_expr": 3,
        "equality_expr": 4,
        "compare_expr": 5,
        "not_expr": 6,
        "and_expr": 7,
        "or_expr": 8,
        "conditional_expr": 9,
    }

    def _has_higher_precedence(self, this: str, that: str) -> bool:
        return self.precedence[this] < self.precedence.get(that, 0)

    def _binary_expr(self, this: str, operator: str, left: Tree[Token], right: Tree[Token]) -> str:
        left_str = self._visit_tree(left)
        right_str = self._visit_tree(right)
        if self._has_higher_precedence(this, left.data) or (this == left.data == "power_expr"):
            left_str = "(" + left_str + ")"
        if self._has_higher_precedence(this, right.data):
            right_str = "(" + right_str + ")"
        return f"{left_str} {operator} {right_str}"

    def rule(self, *children: Tree[Token]) -> str:
        """Entrance to process rule_translator results"""
        rules = self.visit_children(Tree("rule", list(children)))
        return "".join(rules)

    def conditional_expr(
        self, guard: Tree[Token], then: Tree[Token], otherwise: Tree[Token]
    ) -> str:
        """Serialize conditional_expr"""
        condition_str = self._visit_tree(guard)
        then_val = self._visit_tree(then)
        else_val = self._visit_tree(otherwise)

        if guard.data in self.precedence:
            condition_str = "(" + condition_str + ")"
        if then.data in self.precedence:
            if len(then_val) < 50:
                then_val = "(" + then_val + ")"
            else:
                then_val = "(\n" + textwrap.indent(then_val, "    ") + "\n)"
        if otherwise.data in self.precedence:
            if len(else_val) < 50:
                else_val = "(" + else_val + ")"
            else:
                else_val = "(\n" + textwrap.indent(else_val, "    ") + "\n)"
        line_break = " " if len(condition_str) < 30 else "\n"

        return f"{condition_str} ?{line_break}{then_val} : {else_val}"

    def skip_stmt(self, _: Tree[Token]) -> str:
        """Serialize skip_stmt"""
        return ";"

    def assign_stmt(self, left: Tree[Token], operator: Token, right: Tree[Token]) -> str:
        """Serialize assign_stmt"""
        return f"{self._visit_tree(left)} {operator.value} {self._visit_tree(right)};"

    def or_expr(self, left: Tree[Token], right: Tree[Token]) -> str:
        """Serialize or_expr"""
        return self._binary_expr("or_expr", "||", left, right)

    def and_expr(self, left: Tree[Token], right: Tree[Token]) -> str:
        """Serialize and_expr"""
        return self._binary_expr("and_expr", "&&", left, right)

    def not_expr(self, operand: Tree[Token]) -> str:
        """Serialize not_expr"""
        operand_str = self._visit_tree(operand)
        if operand.data in ["equality_expr", "compare_expr", "and_expr", "or_expr"]:
            operand_str = "(" + operand_str + ")"
        return f"!{operand_str}"

    def const_true(self) -> str:
        """Serialize const_true"""
        return "true"

    def const_false(self) -> str:
        """Serialize const_false"""
        return "false"

    def compare_expr(self, left: Tree[Token], operator: Token, right: Tree[Token]) -> str:
        """Serialize const_false"""
        return self._binary_expr("compare_expr", operator.value, left, right)

    def equality_expr(self, left: Tree[Token], operator: Token, right: Tree[Token]) -> str:
        """Serialize compare_expr"""
        return self._binary_expr("equality_expr", operator.value, left, right)

    def add_expr(self, left: Tree[Token], operator: Token, right: Tree[Token]) -> str:
        """Serialize add_expr"""
        return self._binary_expr("add_expr", operator.value, left, right)

    def mul_expr(self, left: Tree[Token], operator: Token, right: Tree[Token]) -> str:
        """Serialize mul_expr"""
        return self._binary_expr("mul_expr", operator.value, left, right)

    def power_expr(self, base: Tree[Token], exponent: Tree[Token]) -> str:
        """Serialize power"""
        return self._binary_expr("power_expr", "**", base, exponent)

    def func_call(self, *children: Tree[Token]) -> str:
        """Serialize func_call"""
        assert len(children) in [2, 3]
        segments = self.visit_children(Tree("func_call", list(children)))
        return "".join(segments)

    def func_templates(self, *children: Tree[Token]) -> str:  # pragma: no cover
        """Serialize func_templates"""
        arguments = self.visit_children(Tree("func_templates", list(children)))
        return "<" + ", ".join(arguments) + ">"

    def func_arguments(self, *children: Tree[Token]) -> str:
        """Serialize func_arguments"""
        arguments = self.visit_children(Tree("func_arguments", list(children)))
        return "(" + ", ".join(arguments) + ")"

    def var_ref(self, var: Token) -> str:
        """Serialize var_ref"""
        return var.value

    def getitem(self, array: Tree[Token], index: Tree[Token]) -> str:
        """Serialize getitem"""
        return f"{self._visit_tree(array)}[{self._visit_tree(index)}]"

    def getattr(self, obj: Tree[Token], attr: Token) -> str:
        """Serialize getattr"""
        return f"{self._visit_tree(obj)}.{attr.value}"

    def array(self, *children: Union[Token, Tree[Token]]) -> str:
        """Serialize array"""
        elements = self.visit_children(Tree("array", list(children)))
        return "[" + ", ".join(elements) + "]"

    def number(self, token: Token) -> str:
        """Serialize number"""
        return token.value

    def string(self, token: Token) -> str:
        """Serialize string"""
        return token.value
