from tree_sitter import Language, Parser
import tree_sitter_java as tsjava

JAVA_LANGUAGE = Language(tsjava.language(), name='java')
parser = Parser()
parser.set_language(JAVA_LANGUAGE)

# 变量赋值语句
statement_assignment_expression_query_text = '''
(expression_statement
	(assignment_expression
        left: (identifier)@name
        right: (_)@value
    )
)@assignment_expression
'''
# 变量赋值
assignment_expression_query_text = '''
(assignment_expression
    left: (identifier)@name
    right: (_)@value
)
'''

# 局部变量定义
statement_declaration_query_text = '''
(local_variable_declaration
	type: (_)@type
    declarator: (_)@declarator
)@local_variable_declaration
'''

# 函数内部所有的statement
statement_query_text = '''
(program
    (method_declaration 
        body:(block
            (_)@all
        )
    )
)
'''

# 函数内部所有的变量定义statement
process_declaration_query_text = '''
(program
    (method_declaration 
        body:(block
            (local_variable_declaration
                type: (_)
                declarator: (_)
            )@local_variable_declaration
        )
    )
)
'''

# 函数内部所有的变量赋值statement
process_assignment_query_text = '''
(program
    (method_declaration 
        body:(block
            (expression_statement
                (assignment_expression
                    left: (identifier)
                    right: (_)
                )
            )@assignment_expression
        )
    )
)
'''

# 函数内部所有的函数调用statement
process_method_invocation_query_text = '''
(program
    (method_declaration 
        body:(block
            (expression_statement
                (method_invocation)
            )@method_invocation
        )
    )
)
'''

line_comment_query_text = '''
(line_comment)@line_comment
'''

block_comment_query_text = '''
(block_comment)@block_comment
'''

line_comment_query = JAVA_LANGUAGE.query(line_comment_query_text)
block_comment_query = JAVA_LANGUAGE.query(block_comment_query_text)


method_invocation_query_text = '''
(method_invocation
    name:(_)
    arguments:(_)
)@method_invocation
'''
method_invocation_query = JAVA_LANGUAGE.query(method_invocation_query_text)

change_naming_conventions = ['set', 'add', 'insert', 'remove', 'delete', 'clear', 'reset', 'update', 'create', 'make', 'build', 'append', 'merge']


def find_affected_variables_in_method_invocation(node):
    # 返回一个列表，包含所有受影响的变量
    affected_variables = []
    
    for method_invocation_node, type_name in method_invocation_query.captures(node):
        object_node = method_invocation_node.child_by_field_name('object')
        name_node = method_invocation_node.child_by_field_name('name')
        arguments_node = method_invocation_node.child_by_field_name('arguments')
        
        if object_node:
            affected_variables.append(object_node.text.decode())
        method_name = name_node.text.decode().lower()
        could_change = any([naming_convention in method_name for naming_convention in change_naming_conventions])
        if could_change:
            for argument in arguments_node.children:
                if argument.type == 'identifier':
                    affected_variables.append(argument.text.decode())
    
    return affected_variables


statement_assignment_expression_query = JAVA_LANGUAGE.query(statement_assignment_expression_query_text)
assignment_expression_query = JAVA_LANGUAGE.query(assignment_expression_query_text)
statement_declaration_query = JAVA_LANGUAGE.query(statement_declaration_query_text)
statement_query = JAVA_LANGUAGE.query(statement_query_text)
process_declaration_query = JAVA_LANGUAGE.query(process_declaration_query_text)
process_assignment_query = JAVA_LANGUAGE.query(process_assignment_query_text)
process_method_invocation_query = JAVA_LANGUAGE.query(process_method_invocation_query_text)


identifier_query_text = '''
(identifier)@identifier
'''
identifier_query = JAVA_LANGUAGE.query(identifier_query_text)

type_identifier_query_text = '''
(type_identifier)@type_identifier
'''
type_identifier_query = JAVA_LANGUAGE.query(type_identifier_query_text)

if_statement_query_text = '''
(if_statement)@if_statement
'''
if_statement_query = JAVA_LANGUAGE.query(if_statement_query_text)

for_statement_query_text = '''
(for_statement)@for_statement
'''
for_statement_query = JAVA_LANGUAGE.query(for_statement_query_text)

while_statement_query_text = '''
(while_statement)@while_statement
'''
while_statement_query = JAVA_LANGUAGE.query(while_statement_query_text)

do_statement_query_text = '''
(do_statement)@do_statement
'''
do_statement_query = JAVA_LANGUAGE.query(do_statement_query_text)


try_statement_query_text = '''
(try_statement)@try_statement
'''
try_statement_query = JAVA_LANGUAGE.query(try_statement_query_text)


finally_clause_query_text = '''
(finally_clause)@finally_clause
'''
finally_clause_query = JAVA_LANGUAGE.query(finally_clause_query_text)

return_statement_query_text = '''
(return_statement)@return_statement
'''
return_statement_query = JAVA_LANGUAGE.query(return_statement_query_text)

break_statement_query_text = '''
(break_statement)@break_statement
'''
break_statement_query = JAVA_LANGUAGE.query(break_statement_query_text)

continue_statement_query_text = '''
(continue_statement)@continue_statement
'''
continue_statement_query = JAVA_LANGUAGE.query(continue_statement_query_text)

throw_statement_query_text = '''
(throw_statement)@throw_statement
'''
throw_statement_query = JAVA_LANGUAGE.query(throw_statement_query_text)

if_and_else_statement_query_text = '''
(if_statement
    alternative:(_)@alternative_statement
)@if_statement
'''
if_and_else_statement_query = JAVA_LANGUAGE.query(if_and_else_statement_query_text)

method_name_query_text = '''
(method_declaration
    name: (identifier)@method_name
)
'''
method_name_query = JAVA_LANGUAGE.query(method_name_query_text)