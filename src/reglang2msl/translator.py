"""Code translator for RegLang to MSL"""
from lark import Token, Tree

from .knowledge_base_translator import KnowledgeBaseInterpreter, KnowledgeBaseTranslator
from .rule_translator import RuleTranslator


class CodeGenerator:
    """Translate RegLang AST into plain MSL code"""

    def __init__(self) -> None:
        self.rule_translator = RuleTranslator()
        self.kb_interpreter = KnowledgeBaseInterpreter()
        self.kb_translator = KnowledgeBaseTranslator()

    def generate(self, reglang_ast: Tree[Token]) -> str:
        """Translation entrance"""
        kb_dict = self.kb_interpreter.visit(reglang_ast)
        const_def = self.kb_translator.translate(kb_dict)

        import_header, auto_def = self.rule_translator.translate(reglang_ast)

        return import_header + const_def + auto_def
