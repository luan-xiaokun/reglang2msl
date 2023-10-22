"""Command line entrance for translating RegLang to MSL"""
import argparse
from pathlib import Path

from ._parser import parser
from .translator import CodeGenerator


def read_arguments() -> argparse.Namespace:
    """Read command line arguments"""
    cmd_parser = argparse.ArgumentParser(description="Translate RegLang to MSL")
    cmd_parser.add_argument("input_file", help="path to the input RegLang file")
    cmd_parser.add_argument("output_file", help="path to save the output MSL file")
    return cmd_parser.parse_args()


def translate(reglang_code: str) -> str:
    """Translate RegLang code to MSL code"""
    translator = CodeGenerator()
    ast_tree = parser.parse(reglang_code)
    msl_code = translator.generate(ast_tree)
    return msl_code


if __name__ == "__main__":
    args = read_arguments()

    input_file_path = Path(args.input_file)
    output_file_path = Path(args.output_file)

    with open(input_file_path, "r", encoding="utf-8") as input_file:
        reglang_str = input_file.read()

    msl_str = translate(reglang_str)
    with open(output_file_path, "w", encoding="utf-8") as output_file:
        output_file.write(msl_str)
