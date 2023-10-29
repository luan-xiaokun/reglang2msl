"""
Translator for RegLang rule
"""
import textwrap
from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, List, Tuple, Union, cast

from lark import Token, Tree
from lark.visitors import Transformer, v_args

from .exceptions import MaxRuleStatementError
from .utils import MslAstSerializer, string2int

ERROR_CODE_BASE = 1000
ERROR_CODE_STEP = 1000


@dataclass
class TemplateInfo:
    """Record if predefined functions or special variables are used in RegLang"""

    def __init__(self) -> None:
        self.has_tx_var: bool = False
        self.has_contract_var: bool = False
        self.predefined_func: Dict[str, bool] = OrderedDict(
            [
                ("reglang.contains", False),
                ("reglang.count", False),
                ("reglang.count_eq", False),
                ("reglang.count_neq", False),
                ("reglang.count_le", False),
                ("reglang.count_ge", False),
                ("reglang.count_lt", False),
                ("reglang.count_gt", False),
                ("reglang.count_member", False),
            ]
        )

    def reset(self) -> None:
        """Reset attributes"""
        self.has_tx_var = False
        self.has_contract_var = False
        for func_name in self.predefined_func:
            self.predefined_func[func_name] = False


@v_args(inline=True)
class RuleTransitionBuilder(Transformer):
    """Translate RegLang rule into MSL AST"""

    def __init__(self) -> None:
        super().__init__()
        self.template_info = TemplateInfo()
        self.has_length_func = False
        self.has_count_func = False
        self.has_tx_var = False
        self.has_contract_var = False

    def _construct_func_call(
        self, function_name: str, arguments: List[Token | Tree[Token]]
    ) -> Tree[Token]:
        function_name_token = Token("NAME", function_name)
        arguments_tree = Tree("func_arguments", arguments)
        func_call_tree: Tree[Token] = Tree("func_call", [function_name_token, arguments_tree])
        return func_call_tree

    def _translate_builtin_boolean_func(self, condition: Tree[Token]) -> Tree[Token]:
        assert condition.data in [
            "equality_expr",
            "compare_expr",
            "func_call",
        ], f"unexpected parse rule {condition.data}"

        if condition.data == "func_call":
            assert len(condition.children) == 2, "expecting function call has two children"
            arguments_tree = condition.children[1]
            assert isinstance(arguments_tree, Tree)
            assert arguments_tree.data == "func_arguments" and len(arguments_tree.children) == 2
            func_name = "reglang.count_member"
            func_arguments = arguments_tree.children
        else:
            # if condition.data == "compare_expr":
            # here we assume that the left operand of the comparison operator is an array
            assert len(condition.children) == 3
            array_argument, operator, value_argument = condition.children
            operator_name_map = {
                "==": "eq",
                "!=": "neq",
                "<=": "le",
                ">=": "ge",
                "<": "lt",
                ">": "gt",
            }
            func_name = f"reglang.count_{operator_name_map[str(operator)]}"
            func_arguments = [array_argument, value_argument]

        self.template_info.predefined_func[func_name] = True
        func_call_tree = self._construct_func_call(func_name, func_arguments)

        return func_call_tree

    def start(self, *blocks: Tree[Token]) -> Tree[Token]:
        """Translate rule blocks into several if-then statements and change error codes"""

        def get_nested_level(tree: Union[Tree[Token], Token], name: str) -> int:
            """Get the nested level of a tree with specific name"""
            if isinstance(tree, Token):
                return 0
            nested = int(tree.data == name)
            if len(tree.children) == 0:
                return nested
            return nested + max(get_nested_level(child, name) for child in tree.children)

        rule_blocks = filter(
            lambda tree: isinstance(tree, Tree) and tree.data in ["skip_stmt", "assign_stmt"],
            blocks,
        )
        rules = list(rule_blocks)
        error_code_prefix = ERROR_CODE_BASE
        for rule in rules:
            assert rule.data in ["skip_stmt", "assign_stmt"]
            if rule.data == "skip_stmt":
                continue
            assert len(rule.children) == 3 and isinstance(rule.children[2], Tree)
            assert rule.children[2].data == "conditional_expr"
            assert len(rule.children[2].children) == 3 and isinstance(
                rule.children[2].children[1], Tree
            )

            conditions = rule.children[2].children[1]
            condition_num = get_nested_level(conditions, "conditional_expr")
            if condition_num >= ERROR_CODE_STEP:
                # in fact, this should never happen as it will exceed the maximum recursion depth
                raise MaxRuleStatementError(
                    f"Too many checking statements ({condition_num})"
                )  # pragma: no cover
            error_codes = [error_code_prefix + i + 1 for i in range(condition_num)][::-1]

            cur_condition = conditions
            while cur_condition.data == "conditional_expr":
                assert len(cur_condition.children) == 3
                assert isinstance(cur_condition.children[2], Tree)
                assert isinstance(cur_condition.children[1], Tree)
                assert cur_condition.children[1].data == "number"
                error_code = Tree("number", [Token("NUMBER", str(error_codes.pop()))])
                cur_condition.children[1] = error_code
                cur_condition = cur_condition.children[2]

            error_code_prefix += ERROR_CODE_STEP

        return Tree("transition_body", cast(List[Token | Tree[Token]], rules))

    # default: number, string, array, var_ref, array_item
    def rule_block(self, _: Token, guard: Tree[Token], *stmts: Tree[Token]) -> Tree[Token]:
        """rule_block is translated into a nested conditional expression assignment"""
        output_var: Tree[Token] = Tree("var_ref", [Token("NAME", "output")])
        output_value: Tree[Token] = Tree("getattr", [output_var, Token("NAME", "value")])
        assign_token = Token("EQUAL", "=")
        error_code: Tree[Token] = Tree("number", [Token("NUMBER", "1")])
        if len(stmts) == 0:
            return Tree("skip_stmt", [Token("SEMICOLON", ";")])
        inner_term: Tree[Token] = Tree("conditional_expr", [stmts[-1], error_code, output_value])
        for stmt in reversed(stmts[:-1]):
            inner_term = Tree("conditional_expr", [stmt, error_code, inner_term])
        outer_term: Tree[Token] = Tree("conditional_expr", [guard, inner_term, output_value])
        assignment: Tree[Token] = Tree("assign_stmt", [output_value, assign_token, outer_term])
        return assignment

    def reg_scope(self, condition: Tree[Token]) -> Tree[Token]:
        """condition of reg_scope is directly converted to transition guard"""
        return condition

    def require_stmt(self, condition: Tree[Token]) -> Tree[Token]:
        """require_stmt is treated as a negated prohibit_stmt"""
        return self.prohibit_stmt(Tree("not_expr", [condition]))

    def prohibit_stmt(self, condition: Tree[Token]) -> Tree[Token]:
        """prohibit_stmt is converted to a boolean condition"""
        return condition

    def and_expr(self, *conditions: Tree[Token]) -> Tree[Token]:
        """and_expr"""
        return Tree("and_expr", list(conditions))

    def or_expr(self, *conditions: Tree[Token]) -> Tree[Token]:
        """or_expr"""
        return Tree("or_expr", list(conditions))

    def compare_expr(self, left: Tree[Token], operator: Token, right: Tree[Token]) -> Tree[Token]:
        """compare_expr needs special treatment when one of its operands is a string"""
        # only when both operands are strings, and one of them cannot be converted to number
        # the comparison is treated as string comparison
        tree_name = "compare_expr" if operator.value not in ["==", "!="] else "equality_expr"
        if left.data == "string" and right.data == "string":
            assert len(left.children) == 1 and isinstance(left.children[0], Token)
            assert len(right.children) == 1 and isinstance(right.children[0], Token)
            left_num = string2int(left.children[0].value.strip('"'))
            right_num = string2int(right.children[0].value.strip('"'))
            if left_num is None or right_num is None:
                return Tree(tree_name, [left, operator, right])

        node_types = ["number", "string", "power_expr", "mul_expr", "add_expr"]
        if right.data in node_types and left.data == "string":
            left = self._convert_string_to_number(left)
        if left.data in node_types and right.data == "string":
            right = self._convert_string_to_number(right)
        return Tree(tree_name, [left, operator, right])

    def membership(self, element: Tree[Token], knowledge_ref: Tree[Token]) -> Tree[Token]:
        """membership is converted to predefined function call"""
        self.template_info.predefined_func["reglang.contains"] = True
        return self._construct_func_call("reglang.contains", [knowledge_ref, element])

    def at_least(self, expr: Tree[Token], condition: Tree[Token]) -> Tree[Token]:
        """at_least is converted to predefined function call"""
        func_call_tree = self._translate_builtin_boolean_func(condition)
        ge_token = Token("__ANON_3", ">=")
        expr = self._convert_string_to_number(expr)
        compare_tree: Tree[Token] = Tree("compare_expr", [func_call_tree, ge_token, expr])
        return compare_tree

    def at_most(self, expr: Tree[Token], condition: Tree[Token]) -> Tree[Token]:
        """at_most is converted to predefined function call"""
        func_call_tree = self._translate_builtin_boolean_func(condition)
        le_token = Token("__ANON_2", "<=")
        expr = self._convert_string_to_number(expr)
        compare_tree: Tree[Token] = Tree("compare_expr", [func_call_tree, le_token, expr])
        return compare_tree

    def any_item(self, condition: Tree[Token]) -> Tree[Token]:
        """any_item is converted to predefined function call"""
        func_call_tree = self._translate_builtin_boolean_func(condition)
        expr = Tree("number", [Token("NUMBER", "1")])
        ge_token = Token("__ANON_3", ">=")
        compare_tree: Tree[Token] = Tree("compare_expr", [func_call_tree, ge_token, expr])
        return compare_tree

    def all_items(self, condition: Tree[Token]) -> Tree[Token]:
        """all_items is converted to predefined function call"""
        func_call_tree = self._translate_builtin_boolean_func(condition)
        assert isinstance(func_call_tree.children[1], Tree)
        array_argument = func_call_tree.children[1].children[0]
        length_argument = Tree("func_arguments", [array_argument])
        expr: Tree[Token] = Tree("func_call", [Token("NAME", "length"), length_argument])
        eq_token = Token("__ANON_0", "==")
        compare_tree: Tree[Token] = Tree("compare_expr", [func_call_tree, eq_token, expr])
        return compare_tree

    def term(self, left: Tree[Token], operator: Token, right: Tree[Token]) -> Tree[Token]:
        """term is renamed to add_expr"""
        left = self._convert_string_to_number(left)
        right = self._convert_string_to_number(right)
        return Tree("add_expr", [left, operator, right])

    def factor(self, left: Tree[Token], operator: Token, right: Tree[Token]) -> Tree[Token]:
        """factor is renamed to mul_expr"""
        left = self._convert_string_to_number(left)
        right = self._convert_string_to_number(right)
        return Tree("mul_expr", [left, operator, right])

    def power(self, base: Tree[Token], exponent: Tree[Token]) -> Tree[Token]:
        """power is renamed to power_expr"""
        base = self._convert_string_to_number(base)
        exponent = self._convert_string_to_number(exponent)
        return Tree("power_expr", [base, exponent])

    def _convert_string_to_number(self, tree: Tree[Token]) -> Tree[Token]:
        """Convert string to number"""
        if tree.data != "string":
            return tree
        assert tree.data == "string"
        assert len(tree.children) == 1 and isinstance(tree.children[0], Token)
        string: str = tree.children[0].value
        new_tree = Tree("number", [Token("NUMBER", string.strip('"'))])
        return new_tree

    def length(self, expr: Tree[Token]) -> Tree[Token]:
        """length is converted to predefined function call"""
        return self._construct_func_call("length", [expr])

    def count(self, *children: Union[Token, Tree[Token]]) -> Tree[Token]:
        """count is converted to predefined function call"""
        self.template_info.predefined_func["reglang.count"] = True
        array_tree: Tree[Token] = Tree("array", list(children))
        return self._construct_func_call("reglang.count", [array_tree])

    def knowledge_ref(self, kb_name: Token, k_name: Token) -> Tree[Token]:
        """knowledge_ref is translated into constant reference"""
        const_name_token = kb_name.update(value=f"{kb_name}_{k_name}")
        var_ref_tree = Tree("var_ref", [const_name_token])
        return var_ref_tree

    def tx_basic(self, basic: Token) -> Tree[Token]:
        """Transaction basic attributes are translated into struct fields"""
        self.template_info.has_tx_var = True
        name_token = basic.update(type="NAME")
        tx_var: Tree[Token] = Tree("var_ref", [Token("NAME", "tx")])
        tx_basic_tree: Tree[Token] = Tree("getattr", [tx_var, name_token])
        return tx_basic_tree

    def tx_state(self, state: Token, address: Tree[Token], var: Tree[Token]) -> Tree[Token]:
        """Transaction state attributes are translated into user-defined state mapping"""
        self.template_info.has_tx_var = True
        if var.data == "var_ref":
            assert len(var.children) == 1 and isinstance(var.children[0], Token)
            var = Tree("string", [Token("STRING", f'"{var.children[0].value}"')])
        name_token = state.update(type="NAME")
        tx_var: Tree[Token] = Tree("var_ref", [Token("NAME", "tx")])
        tx_state_tree: Tree[Token] = Tree("getattr", [tx_var, name_token])
        tx_state_var_tree: Tree[Token] = Tree(
            "getitem", [Tree("getitem", [tx_state_tree, address]), var]
        )
        return tx_state_var_tree

    def tx_args(self, var: Tree[Token]) -> Tree[Token]:
        """Transaction args attributes are translated into user-defined state mapping"""
        self.template_info.has_tx_var = True
        if var.data == "var_ref":
            assert len(var.children) == 1 and isinstance(var.children[0], Token)
            var = Tree("string", [Token("STRING", f'"{var.children[0].value}"')])
        tx_var: Tree[Token] = Tree("var_ref", [Token("NAME", "tx")])
        tx_args_tree: Tree[Token] = Tree("getattr", [tx_var, Token("NAME", "args")])
        tx_args_var_tree: Tree[Token] = Tree("getitem", [tx_args_tree, var])
        return tx_args_var_tree

    def contract_basic(self, address: Tree[Token], basic: Token) -> Tree[Token]:
        """Contract basic attributes are translated into struct fields"""
        self.template_info.has_contract_var = True
        contract_var: Tree[Token] = Tree("var_ref", [Token("NAME", "contract")])
        address_item: Tree[Token] = Tree("getitem", [contract_var, address])
        basic_tree: Tree[Token] = Tree("getattr", [address_item, basic.update(type="NAME")])
        return basic_tree

    def contract_state(self, address: Tree[Token], var: Tree[Token]) -> Tree[Token]:
        """Contract state attributes are translated into user-defined state mapping"""
        self.template_info.has_contract_var = True
        assert var.data == "var_ref"
        assert len(var.children) == 1 and isinstance(var.children[0], Token)
        var = Tree("string", [Token("STRING", f'"{var.children[0].value}"')])
        contract_var: Tree[Token] = Tree("var_ref", [Token("NAME", "contract")])
        address_item: Tree[Token] = Tree("getitem", [contract_var, address])
        state_tree: Tree[Token] = Tree("getattr", [address_item, Token("NAME", "state")])
        state_var_tree: Tree[Token] = Tree("getitem", [state_tree, var])
        return state_var_tree

    def array_item(self, array: Tree[Token], index: Tree[Token]) -> Tree[Token]:
        """array_item is renamed to getitem"""
        index = self._convert_string_to_number(index)
        return Tree("getitem", [array, index])

    def string(self, token: Token) -> Tree[Token]:
        """string is renamed to string"""
        string = str(token.value).lower()
        return Tree("string", [Token("STRING", string)])


class RuleTranslator:
    """Translate Reglang into MSL code"""

    template = """automaton Rule (
    tx_input: in Tx,
    contract_input: in Contract,
    output: out int
) {{
    states {{
        bool pass = true;
        bool checking = false;
        Tx tx = null;
        Contract contract = null;
    }}
    transitions {{
{read_input}
        checking -> {{
            output.value = 0;
{rules}            pass = (output.value == 0);
            checking = false;
            sync output;
        }}
    }}
}}
"""

    def __init__(self):
        self.transition_builder = RuleTransitionBuilder()
        self.serializer = MslAstSerializer()

    def translate(self, reglang_ast: Tree[Token]) -> Tuple[str, str]:
        """Translate a RegLang AST into an MSL program"""
        msl_ast: Tree[Token] = self.transition_builder.transform(reglang_ast)
        rule_transition_segment: str = self.serializer.visit(msl_ast)

        # reglang.contains may be imported but not really used
        # in which case we need to remove it from the import list
        if "reglang.contains(" not in rule_transition_segment:
            self.transition_builder.template_info.predefined_func["reglang.contains"] = False

        dependency_import = self.import_dependencies(self.transition_builder.template_info)
        read_input = self.construct_read_input(self.transition_builder.template_info)
        automaton_def = self.template.format(
            read_input=read_input,
            rules=textwrap.indent(rule_transition_segment, " " * 12),
        )
        self.transition_builder.template_info.reset()

        return dependency_import, automaton_def

    def import_dependencies(self, template_info: TemplateInfo) -> str:
        """Provide necessary predefined function and data type imports"""
        predefined_func = ""
        for func_name in template_info.predefined_func:
            if template_info.predefined_func[func_name]:
                predefined_func += f"import {func_name}\n"
        predefined_func += "import reglang.Contract as Contract\nimport reglang.Tx as Tx\n\n"
        return predefined_func

    def construct_read_input(self, template_info: TemplateInfo) -> str:
        """Provide necessary synchronization for reading inputs"""
        if not template_info.has_tx_var and not template_info.has_contract_var:
            return "        !checking -> checking = true;"

        read_input = ""
        conditions = ["!checking"]
        ports = []
        assignments = []

        if template_info.has_tx_var:
            read_input += "!checking && !tx_input.reqRead -> tx_input.reqRead = true;\n"
            conditions.append("(tx_input.reqRead && tx_input.reqWrite)")
            ports.append("tx_input")
            assignments.append("tx = tx_input.value;")

        if template_info.has_contract_var:
            read_input += "!checking && !contract_input.reqRead -> contract_input.reqRead = true;\n"
            conditions.append("(contract_input.reqRead && contract_input.reqWrite)")
            ports.append("contract_input")
            assignments.append("contract = contract_input.value;")

        guard = " && ".join(conditions)
        sync_port = f"sync {', '.join(ports)};"
        read_value = textwrap.indent("\n".join(assignments), "    ")
        read_input += f"{guard} -> {{\n    {sync_port}\n{read_value}\n    checking = true;\n}}"

        return textwrap.indent(read_input, "        ")
