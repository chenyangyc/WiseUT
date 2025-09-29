import os
import ast
import astor
import pickle
import sys
from tqdm import tqdm
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.base_module import Module
from core.base_function import Function, Class
from core.base_branch import Branch
from core.ast_objs import ClassDefVisitor, ClassInstantiationVisitor, FunctionDefVisitor, FunctionCallVisitor, InitFunctionVisitor, VariableTypeExtractor
from utils.find_branch_related_util import analyze_code_with_all_variables, update_functions, analyze_conditions


def extract_classes(module_content):
    tree = ast.parse(module_content)
    class_def_visitor = ClassDefVisitor()
    class_def_visitor.visit(tree)

    classes = []
    for class_name, class_info in class_def_visitor.info.items():
        init = class_info['init']
        methods = class_info['methods']
        attributes = class_info['attr']
        comment = class_info.get('comment', None)
        content = class_info['content']
        new_class = Class(name = class_name, methods = methods, attributes = attributes, init = init, comment = comment, content = content)
        classes.append(new_class)
    return classes


def extract_functions(module_content):
    tree = ast.parse(module_content)
    function_def_visitor = FunctionDefVisitor()
    function_def_visitor.visit(tree)
    
    function_nodes = function_def_visitor.functions

    functions =  [
        Function(
            name = func_node.name,
            # parameters = [arg.arg for arg in func_node.args.args]
            signature = f"{func_node.name}({', '.join([arg.arg for arg in func_node.args.args])})",
            content = astor.to_source(func_node),
            line_range = list(range(func_node.lineno, getattr(func_node, 'end_lineno', func_node.lineno) + 1)),
            func_type = 'within_class' if class_name else 'standalone',
            belong_class = class_name
        )
        for (class_name, func_node) in function_nodes
    ] 
    
    return functions


def extract_called_functions(function_content):
    '''
    提取一个函数里面调用的其他函数
    '''
    content_tree = ast.parse(function_content)

    visitor = FunctionCallVisitor()
    visitor.visit(content_tree)
    print(type(visitor))
    function_calls = visitor.function_calls
    return function_calls


def extract_branch_related_called_functions(single_function, add_branch=True):
    '''
    提取一个函数里面和分支有关的其他函数
    '''
    function_content = single_function.content
    dependencies = analyze_code_with_all_variables(function_content)
    update_functions(dependencies)
    functions_set, variables_set, branches_set = analyze_conditions(function_content)
    
    # 把获取的分支加入到函数的分支集合中
    if add_branch:
        for branch in branches_set:
            single_function.add_branch(branch)
            branch.set_belong_function(single_function)
        # 对分支部分进行插装，用于输出分支中变量的类型
        instrumentation_to_branch(single_function)
    for name in variables_set:
        if name not in dependencies.keys():
            continue
        function_list = dependencies[name]['function']
        for funtion in function_list:
            functions_set.add(funtion)
    for branch in branches_set:
        add_vars = set()
        for name in branch.related_vars:
            if name not in dependencies.keys():
                continue
            function_list = dependencies[name]['function']
            for funtion in function_list:
                branch.statically_related_funcs.add(funtion)
            for var in dependencies[name]['identifier']:
                add_vars.add(var)
        branch.related_vars = branch.related_vars.union(add_vars)
    return functions_set


def instrumentation_to_branch(single_function):
    '''
    给定一个branch，对其进行插装print(type(类型))语句
    '''
    function_lines = single_function.content.split('\n')
    add_lines = []
    for single_branch in single_function.branches:
        column_number = single_branch.column_number
        branch_content = single_branch.content
        add_list = []
        for name in single_branch.related_vars:
            if '.' in name:
                type_name = '.'.join(name.split('.')[0:-1])
            else:
                type_name = name
            add_list.append(' ' * column_number + f"print('########## {type_name} : ' + str(type({type_name})))")
            # f"print({type_name} : f'type({type_name})')"
            # add_list.append(' ' * column_number + f"print(type({type_name}))")
        
        add_lines.append((single_branch.line_number - 1, add_list))
    add_lines.sort(key = lambda x: x[0], reverse = True)
    for line_number, add_list in add_lines:
        # 插入位置为line_number行之后，注意，每次出入之后，后面的行号都会发生变化
        for add_line in reversed(add_list):
            function_lines.insert(line_number, add_line)
    single_function.set_instrumentation_content('\n'.join(function_lines))


def get_variable_types_statically(function_content):
    '''
    使用静态分分析获取一个函数中变量的类型
    '''
    visitor = VariableTypeExtractor()
    result = visitor.extract(function_content)
    
    return result
    



def extract_initilized_class(function_content):
    content_tree = ast.parse(function_content)

    visitor = ClassInstantiationVisitor()
    visitor.visit(content_tree)
    return visitor.instance_creations

    
def extract_imports_from_module(module_content):
    tree = ast.parse(module_content)

    imports = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            content = astor.to_source(node).strip()
            if 'import collections as collections_abc' not in content:
                imports.add(content)
        elif isinstance(node, ast.ImportFrom):
            content = astor.to_source(node).strip()
            if 'import collections as collections_abc' not in content:
                imports.add(content)

    return list(imports)


def extract_class_constructors(class_content):
    tree = ast.parse(class_content)
    visitor = InitFunctionVisitor()
    visitor.visit(tree)
    return visitor.constructor_calls