"""
Interpreter and translator for RegLang knowledge base
"""
import warnings
from typing import Dict, List, Optional, Tuple, Union, cast

from lark import Token, Tree
from lark.visitors import Interpreter

from .exceptions import InterpretationError
from .utils import is_token_list, is_tree_list, string2int


KnowledgeType = Union[int, str, List[int], List[str]]
KnowledgeBaseType = Dict[str, KnowledgeType]


class KnowledgeBaseInterpreter(Interpreter):
    """Interpreter to translate RegLang knowledge base into pure Python dictionary.

    This interpreter will walk through all knowledge base block definitions, collect all knowledge
    definitions and save them in a dictionary.

    Only constant arithmetic expressions are allowed in knowledge definitions, i.e., only number,
    string, array, knowledge reference, array item are allowed, other atom/var elements are not
    expected and errors will be raised.
    """

    def __init__(self) -> None:
        super().__init__()
        self.kb_dict_collection: Dict[str, KnowledgeBaseType] = {}

    def _reset(self) -> None:
        self.kb_dict_collection = {}

    def start(self, tree: Tree[Token]) -> Dict[str, KnowledgeBaseType]:
        """Entrance rule for execution"""
        kb_trees = filter(
            lambda child: isinstance(child, Tree) and child.data == "knowledgebase_block",
            tree.children,
        )

        for kb_tree in kb_trees:
            kb_name, kb_dict = cast(
                Tuple[str, KnowledgeBaseType],
                self.visit(cast(Tree[Token], kb_tree)),
            )
            self.kb_dict_collection.update({kb_name: kb_dict})

        result = self.kb_dict_collection
        self._reset()

        return result

    def knowledgebase_block(self, tree: Tree[Token]) -> Tuple[str, KnowledgeBaseType]:
        """
        Rule for knowledgebase_block

        This function will call rules for arithmetic expressions, we assume that
        errors will be raised by those rules when unexpected expressions are met,
        instead of by this function.
        """
        assert len(tree.children) > 1
        token, *knowledge_tree_list = tree.children
        assert isinstance(token, Token) and is_tree_list(knowledge_tree_list)

        kb_name = str(token.value)
        kb_dict: KnowledgeBaseType = {}
        for k_tree in knowledge_tree_list:
            k_args = self.visit(k_tree)
            self._update_knowledge_base(kb_dict, *k_args)  # type: ignore

        return kb_name, kb_dict

    def knowledge_init(self, tree: Tree[Token]) -> Tuple[str, KnowledgeType]:
        """Rule for knowledge_init"""
        assert len(tree.children) == 2
        k_name_token, k_def = tree.children
        assert isinstance(k_name_token, Token) and isinstance(k_def, Tree)

        k_name = str(k_name_token.value)
        k_def_value = cast(KnowledgeType, self.visit(k_def))

        return k_name, k_def_value

    def knowledge_alt(self, tree: Tree[Token]) -> Tuple[str, KnowledgeType, Token]:
        """Rule for knowledge_alt"""
        assert len(tree.children) == 3
        k_name_token, k_func, k_alt = tree.children
        assert isinstance(k_name_token, Token) and isinstance(k_alt, Tree)
        assert isinstance(k_func, Token) and k_func in ["add", "del"]

        k_name = str(k_name_token.value)
        k_alt_value = cast(KnowledgeType, self.visit(k_alt))

        return k_name, k_alt_value, k_func

    def _update_knowledge_base(
        self,
        kb_dict: KnowledgeBaseType,
        k_name: str,
        k_value: KnowledgeType,
        k_func: Optional[Token] = None,
    ) -> None:
        # when k_func is None, we are dealing with knowledgebase_init
        if k_func is None:
            kb_dict.update({k_name: k_value})
            return

        # ensure the knowledge being altered is defined
        if k_name not in kb_dict:
            raise InterpretationError(
                f"{k_func.line}:{k_func.column}: knowledge '{k_name}' is not defined"
            )

        # ensure the knowledge is an array
        if not isinstance(kb_dict[k_name], list):
            raise InterpretationError("adding and removing elements only support array objects")
        altered_array = cast(Union[List[int], List[str]], kb_dict[k_name])

        # cast the new value into an array so we can determine
        # the resulting type more easily
        if not isinstance(k_value, list):
            k_value = cast(Union[List[int], List[str]], [k_value])

        value_type = int if isinstance(k_value[0], int) else str
        array_type = (
            value_type
            if len(altered_array) == 0
            else int
            if isinstance(altered_array[0], int)
            else str
        )

        # if the type of the arithmetic expression and the type of
        # the array are not consistent, we convert them to string
        if value_type != array_type:
            altered_array = list(map(str, altered_array))
            k_value = list(map(str, k_value))

        for value in k_value:
            if k_func.value == "add" and value not in altered_array:
                altered_array.append(value)  # type: ignore
            elif k_func.value == "del" and value in altered_array:
                altered_array.remove(value)  # type: ignore

    def term(self, tree: Tree[Token]) -> int:
        """Rule for term"""
        assert len(tree.children) == 3
        left, operator, right = tree.children
        assert isinstance(left, Tree) and isinstance(right, Tree)
        assert isinstance(operator, Token) and operator in ["+", "-"]

        left_term = self.visit(left)
        right_term = self.visit(right)
        left_value = string2int(left_term) if isinstance(left_term, str) else int(left_term)
        right_value = string2int(right_term) if isinstance(right_term, str) else int(right_term)

        if left_value is None:
            raise InterpretationError(f"'{left_term}' cannot be converted to number")

        if right_value is None:
            raise InterpretationError(f"'{right_term}' cannot be converted to number")

        return left_value + right_value if operator == "+" else left_value - right_value

    def factor(self, tree: Tree[Token]) -> int:
        """Rule for factor"""
        assert len(tree.children) == 3
        left, operator, right = tree.children
        assert isinstance(left, Tree) and isinstance(right, Tree)
        assert isinstance(operator, Token) and operator in ["*", "/", "%"]

        left_factor = self.visit(left)
        right_factor = self.visit(right)
        left_value = string2int(left_factor) if isinstance(left_factor, str) else int(left_factor)
        right_value = (
            string2int(right_factor) if isinstance(right_factor, str) else int(right_factor)
        )

        if left_value is None:
            raise InterpretationError(f"'{left_value}' cannot be converted to number")

        if right_value is None:
            raise InterpretationError(f"'{right_value}' cannot be converted to number")

        # pylint: disable=eval-used
        return int(eval(f"{left_value} {operator} {right_value}"))

    def power(self, tree: Tree[Token]) -> int:
        """Rule for power"""
        assert len(tree.children) == 2
        left, right = tree.children
        assert isinstance(left, Tree) and isinstance(right, Tree)

        left_power = self.visit(left)
        right_power = self.visit(right)
        left_value = string2int(left_power) if isinstance(left_power, str) else int(left_power)
        right_value = string2int(right_power) if isinstance(right_power, str) else int(right_power)

        if left_value is None:
            raise InterpretationError(f"'{left_value}' cannot be converted to number")

        if right_value is None:
            raise InterpretationError(f"'{right_value}' cannot be converted to number")

        result = int(left_value**right_value)
        if result > 10**4300 - 1:
            warnings.warn(
                "exceeding the limit (4300) for integer string conversion. \
                you probably do not want to use string for power expression"
            )
        return result

    def length(self, tree: Tree[Token]) -> int:
        """Rule for length

        We can tolerate using `length([1])`, but not `length(foo)`.
        Errors will be raised by other rules.
        """
        assert len(tree.children) == 1
        array = tree.children[0]
        assert isinstance(array, Tree)

        array_value = self.visit(array)
        if not isinstance(array_value, list):
            raise InterpretationError(
                f"length only applies to array, but got '{type(array_value)}'"
            )

        return len(array_value)

    def count(self, _: Tree[Token]) -> None:
        """Rule for count

        We do not allow count arithmetic expressions in knowledge definition.
        Therefore, logic expressions also will not show up in knowledge definition.
        """
        self._forbidden_expr("count")

    def _forbidden_expr(self, name: str) -> None:
        raise InterpretationError(f"{name} expressions are not expected in knowledge definition")

    def array(self, tree: Tree[Token]) -> Union[List[int], List[str]]:
        """Rule for array

        RegLang only supports number array and string array, so the element type is determined by
        examining the first element's type.

        Since RegLang forbids using empty array, this approach is fine. In fact, if the source
        code can be parsed by the provided parser, the interpretation error will never be raised.
        """
        assert len(tree.children) > 0 and is_token_list(tree.children)

        first_element = tree.children[0]
        if first_element.type == "NUMBER":
            return [int(child.value) for child in tree.children]

        if first_element.type == "STRING":
            return [child.lower()[1:-1] for child in tree.children]

        # this should not happen
        raise InterpretationError(  # pragma: no cover
            f"{first_element.line}:{first_element.column}: "
            + f"unexpected Token type in array: '{first_element.type}'"
        )

    def number(self, tree: Tree[Token]) -> int:
        """Rule for RegLang number"""
        assert len(tree.children) == 1
        number_token = cast(Token, tree.children[0])
        return int(number_token.value)

    def string(self, tree: Tree[Token]) -> str:
        """Rule for RegLang string"""
        assert len(tree.children) == 1
        string_token = cast(Token, tree.children[0])
        return string_token.lower()[1:-1]

    def tx_basic(self, _: Tree[Token]) -> None:
        """Rule for tx_basic"""
        return self._forbidden_expr("tx basic")

    def tx_state(self, _: Tree[Token]) -> None:
        """Rule for tx_state"""
        self._forbidden_expr("tx state")

    def contract_basic(self, _: Tree[Token]) -> None:
        """Rule for contract_basic"""
        self._forbidden_expr("contract basic")

    def contract_state(self, _: Tree[Token]) -> None:
        """Rule for contract_state"""
        self._forbidden_expr("contract state")

    def knowledge_ref(self, tree: Tree[Token]) -> KnowledgeType:
        """Rule for knowledge_ref

        Undeclared knowledge base or knowledge definition will raise interpretation error.
        """
        assert len(tree.children) == 2
        kb_name_token, k_name_token = tree.children
        assert isinstance(kb_name_token, Token) and isinstance(k_name_token, Token)

        kb_name, k_name = str(kb_name_token.value), str(k_name_token.value)

        if kb_name not in self.kb_dict_collection:
            raise InterpretationError(f"knowledge base '{kb_name}' is not defined")
        kb_dict = self.kb_dict_collection[kb_name]

        k_def = kb_dict.get(k_name, None)
        if k_def is None:
            raise InterpretationError(f"knowledge '{k_name}' is not defined in '{kb_name}'")

        return cast(KnowledgeType, k_def)

    def array_item(self, tree: Tree[Token]) -> Union[int, str]:
        """Rule for array_item

        Invalid index value will raise interpretation error.
        """
        assert len(tree.children) == 2 and is_tree_list(tree.children)

        array, index = tree.children
        array_value = self.visit(array)
        index_value = self.visit(index)

        array_value = cast(Union[List[int], List[str]], array_value)
        index_value = string2int(index_value) if isinstance(index_value, str) else int(index_value)

        if index_value is None:
            raise InterpretationError(
                "array indices must be numbers or strings convertible to numbers"
            )

        if index_value < 0 or index_value >= len(array_value):
            raise InterpretationError("index out of bounds")

        return array_value[index_value]

    def var_ref(self, _: Tree[Token]) -> None:
        """Rule for var_ref"""
        self._forbidden_expr("variable reference")


class KnowledgeBaseTranslator:
    """Translate pure Python KnowledgeBaseType objects into Msl const def code"""

    def translate(self, kb_dict_collection: Dict[str, KnowledgeBaseType]) -> str:
        """RegLang knowledge base translation implementation"""
        msl_kb_code = ""

        for kb_name, kb_dict in kb_dict_collection.items():
            for k_name, knowledge in kb_dict.items():
                msl_kb_code += self.translate_knowledge_def(kb_name, k_name, knowledge)

        if msl_kb_code:
            msl_kb_code += "\n"

        return msl_kb_code

    def translate_knowledge_def(self, kb_name: str, k_name: str, knowledge: KnowledgeType) -> str:
        """Translate a knowledge definition into a string"""
        const_name = kb_name + "_" + k_name
        const_value = self._knowledge2string(knowledge)

        msl_const_def_text = f"const {const_value} as {const_name};\n"

        return msl_const_def_text

    def _knowledge2string(self, var: KnowledgeType) -> str:
        if isinstance(var, (int, str)):
            return repr(var).replace("'", '"')
        return "[" + ", ".join(map(self._knowledge2string, var)) + "]"
