from tree_sitter import Language, Parser
import tree_sitter_python as ts_python

PYTHON_LANGUAGE = Language(ts_python.language())
parser = Parser()
parser.language = PYTHON_LANGUAGE

CALL_QUERY = PYTHON_LANGUAGE.query('(call)@call')
PARAMETERS_QUERY = PYTHON_LANGUAGE.query('(function_definition(parameters)@parameters)')
BRANCH_QUERY = PYTHON_LANGUAGE.query('(if_statement)@branch')
RETURN_QUERY = PYTHON_LANGUAGE.query('(return_statement)@return')
