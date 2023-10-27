"""Symbolic execution to check satisfiability of RegLang"""
from typing import Dict, List, Union

import cvc5
from lark import Tree, Token
from lark.visitors import Interpreter, v_args

from .knowledge_base_translator import KnowledgeBaseType
from .utils import string2int


@v_args(inline=True)
class RuleSatChecker(Interpreter):
    """Symbolic execution to check satisfiability of RegLang"""

    def __init__(self, kb_dict: Dict[str, KnowledgeBaseType]) -> None:
        self.kb_dict = kb_dict
        self.solver = cvc5.Solver()  # pylint: disable=all
        self.solver.setOption("produce-models", "true")
        self.solver.setOption("produce-unsat-cores", "true")

    def transition_body(self, *stmts: Tree[Token]):
        """Check satisfiability of transition body"""
        assert all(stmt.data in ["skip_stmt", "assign_stmt"] for stmt in stmts)

        def negated_expr(expr: Tree[Token]) -> Tree[Token]:
            """Negate an expression"""
            if expr.data == "not_expr":
                return expr.children[0]
            return Tree("not_expr", [expr])

        rule_formulae = []

        for stmt in filter(lambda stmt: stmt.data == "assign_stmt", stmts):
            assert len(stmt.children) == 3
            cond_expr = stmt.children[2]

            assert cond_expr.data == "conditional_expr" and len(cond_expr.children) == 3
            # premise -> (!cond1 && !cond2 && ...)
            premise = cond_expr.children[0]
            conditions = []
            candidate = cond_expr.children[1]
            while isinstance(candidate, Tree) and candidate.data == "conditional_expr":
                assert len(candidate.children) == 3
                conditions.append(candidate.children[0])
                candidate = candidate.children[2]
            # the last candidate must be "output.value", reaching here means that the rule is satisfied
            assert isinstance(candidate, Tree) and candidate.data == "getattr"
            negated_conditions = list(map(negated_expr, conditions))
            # both the premise and each negated condition are boolean expressions

            premise_term = self.visit(premise)
            negated_condition_terms = list(map(self.visit, negated_conditions))
            conclusion_term = (
                negated_condition_terms[0]
                if len(negated_condition_terms) == 1
                else self.solver.mkTerm(cvc5.Kind.AND, *negated_condition_terms)
            )
            print(premise_term)
            print(negated_condition_terms)
            formula = self.solver.mkTerm(
                cvc5.Kind.IMPLIES,
                premise_term,
                conclusion_term,
            )
            self.solver.assertFormula(formula)

        print("result:", self.solver.checkSat())

    def not_expr(self, operand: Tree[Token]) -> cvc5.Term:
        """Negate a term"""
        term: cvc5.Term = self._visit_tree(operand)
        assert term.getSort() == self.solver.getBooleanSort(), "negation term should be boolean"
        return self.solver.mkTerm(cvc5.Kind.NOT, term)

    def and_expr(self, left: Tree[Token], right: Tree[Token]) -> cvc5.Term:
        """Conjunction of two terms"""
        left_term: cvc5.Term = self._visit_tree(left)
        right_term: cvc5.Term = self._visit_tree(right)
        assert (
            left_term.getSort() == right_term.getSort() == self.solver.getBooleanSort()
        ), "conjunction term should be boolean"
        return self.solver.mkTerm(cvc5.Kind.AND, left_term, right_term)

    def or_expr(self, left: Tree[Token], right: Tree[Token]) -> cvc5.Term:
        """Disjunction of two terms"""
        left_term: cvc5.Term = self._visit_tree(left)
        right_term: cvc5.Term = self._visit_tree(right)
        assert (
            left_term.getSort() == right_term.getSort() == self.solver.getBooleanSort()
        ), "disjunction term should be boolean"
        return self.solver.mkTerm(cvc5.Kind.OR, left_term, right_term)

    def compare_expr(self, left: Tree[Token], operator: Token, right: Tree[Token]) -> cvc5.Term:
        """Return the compare test"""
        left_term: cvc5.Term = self._visit_tree(left)
        right_term: cvc5.Term = self._visit_tree(right)
        assert (
            left_term.getSort() == right_term.getSort()
        ), "compare term should be of the same sort"
        op = (
            cvc5.Kind.LEQ
            if operator.value == "<="
            else cvc5.Kind.LT
            if operator.value == "<"
            else cvc5.Kind.GEQ
            if operator.value == ">="
            else cvc5.Kind.GT
        )
        return self.solver.mkTerm(op, left_term, right_term)

    def equality_expr(self, left: Tree[Token], operator: Token, right: Tree[Token]) -> cvc5.Term:
        """Return the equality test"""
        left_term: cvc5.Term = self._visit_tree(left)
        right_term: cvc5.Term = self._visit_tree(right)
        assert (
            left_term.getSort() == right_term.getSort()
        ), "equality term should be of the same sort"
        op = cvc5.Kind.EQUAL if operator.value == "==" else cvc5.Kind.DISTINCT
        return self.solver.mkTerm(op, left_term, right_term)

    def const_true(self) -> cvc5.Term:
        """Return the constant true"""
        return self.solver.mkTrue()

    def const_false(self) -> cvc5.Term:
        """Return the constant false"""
        return self.solver.mkFalse()

    def add_expr(self, left: Tree[Token], operator: Token, right: Tree[Token]) -> cvc5.Term:
        """Return the addition term"""
        left_term: cvc5.Term = self._visit_tree(left)
        right_term: cvc5.Term = self._visit_tree(right)
        assert left_term.getSort() == right_term.getSort(), "add term should be integer or real"
        op = cvc5.Kind.ADD if operator.value == "+" else cvc5.Kind.SUB
        return self.solver.mkTerm(op, left_term, right_term)

    def mul_expr(self, left: Tree[Token], operator: Token, right: Tree[Token]) -> cvc5.Term:
        """Return the multiplication term"""
        left_term: cvc5.Term = self._visit_tree(left)
        right_term: cvc5.Term = self._visit_tree(right)
        assert left_term.getSort() == right_term.getSort(), "mult term should be integer or real"
        op = (
            cvc5.Kind.MULT
            if operator.value == "*"
            else cvc5.Kind.INTS_DIVISION
            if operator.value == "/"
            else cvc5.Kind.INTS_MODULUS
        )
        return self.solver.mkTerm(op, left_term, right_term)

    def power_expr(self, base: Tree[Token], exponent: Tree[Token]) -> cvc5.Term:
        """Return the power term"""
        base_term: cvc5.Term = self._visit_tree(base)
        exponent_term: cvc5.Term = self._visit_tree(exponent)
        assert (
            base_term.getSort() == exponent_term.getSort()
        ), "power term should be integer or real"
        return self.solver.mkTerm(cvc5.Kind.POW, base_term, exponent_term)

    def func_call(self, *children: Union[Tree[Token], Token]) -> cvc5.Term:
        """Special treatment of function call"""
        assert len(children) in [2, 3] and isinstance(children[0], Token)
        func_name = str(children[0].value)
        if func_name == "length":
            pass

    def array(self, *children: Union[Tree[Token], Token]) -> cvc5.Term:
        """Return the array as a sequence term"""
        assert len(children) > 0, "array should not be empty"
        element_units: List[cvc5.Term] = [
            self.solver.mkTerm(cvc5.Kind.SEQ_UNIT, e)
            for e in self.visit_children(Tree("array", list(children)))
        ]
        sequence = self.solver.mkTerm(cvc5.Kind.SEQ_CONCAT, *element_units)
        return sequence

    def number(self, token: Token) -> cvc5.Term:
        """Return the constant number"""
        return self.solver.mkInteger(string2int(token.value))

    def string(self, token: Token) -> cvc5.Term:
        """Return the constant string"""
        return self.solver.mkString(str(token.value).strip('"'))
