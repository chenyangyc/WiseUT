import os
import re
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


def extract_functions(module_content, file_path = None):
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

    imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            content = astor.to_source(node).strip()
            if 'import collections as collections_abc' not in content:
                imports.append(content)
        elif isinstance(node, ast.ImportFrom):
            content = astor.to_source(node).strip()
            if 'import collections as collections_abc' not in content:
                imports.append(content)

    return imports


def extract_global_variables_from_module(module_content):
    tree = ast.parse(module_content)

    global_vars = []
    for node in tree.body:
        if isinstance(node, ast.Assign):  # 处理赋值语句
            for target in node.targets:
                if isinstance(target, ast.Name):
                    global_vars.append(astor.to_source(node).strip())
                    # global_vars[target.id] = ast.unparse(node.value) if hasattr(ast, 'unparse') else None
    
    return global_vars


def extract_class_constructors(class_content):
    tree = ast.parse(class_content)
    visitor = InitFunctionVisitor()
    visitor.visit(tree)
    return visitor.constructor_calls


def extract_module(module_path, module_name=''):
    if module_name == '':
        module_name = os.path.basename(module_path)
    
    with open(module_path, 'r') as fr:
        module_content = fr.read()
        
    single_module = Module(name=module_name, content=module_content, module_path=module_path)
    
    all_classes = extract_classes(module_content)
    all_functions = extract_functions(module_content)
    all_imports = extract_imports_from_module(module_content)
    all_fields = extract_global_variables_from_module(module_content)
    
    single_module.set_fields(all_fields)
    
    for i in all_imports:
        single_module.add_imports(i)
        
    for i in all_classes:
        single_module.add_class(i)
        
    for i in all_functions:
        single_module.add_function(i)
        i.set_belong_module(single_module)
        
        for c in all_classes:
            if i.belong_class is not None and i.belong_class == c.name:
                i.belong_class = c

    return single_module, all_classes, all_functions


def extract_functions_for_llm(content):
    tree = ast.parse(content)
    function_def_visitor = FunctionDefVisitor()
    function_def_visitor.visit(tree)
    
    function_nodes = function_def_visitor.functions

    functions =  [astor.to_source(func_node) for (class_name, func_node) in function_nodes] 
    
    return functions


def extract_imports_for_llm(llm_output):
    tree = ast.parse(llm_output)

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

class RemoveAssertionsTransformer(ast.NodeTransformer):
    def visit_Assert(self, node):
        return ast.Pass()

    def visit_Expr(self, node):
        # Remove expressions like mock_something.assert_...()
        if isinstance(node.value, ast.Call):
            func = node.value.func
            if isinstance(func, ast.Attribute) and func.attr.startswith('assert'):
                return ast.Pass()
        return node
    
    
def change_assert_to_pass_in_test(test_content):
    '''
    将测试用例中的assert语句或mock断言语句转换为pass语句
    '''
    tree = ast.parse(test_content)
    transformer = RemoveAssertionsTransformer()
    new_tree = transformer.visit(tree)
    ast.fix_missing_locations(new_tree)
    return astor.to_source(new_tree)


def reformat_prompt(prompt):
    # Ran * test in *s, use regrex to match
    pattern_1 = r"Ran\s+(\d+)\s+test\s+in\s+([\d.]+)s"
    pattern_2 = r"Ran\s+(\d+)\s+tests\s+in\s+([\d.]+)s"
    
    prompt_lines = prompt.split('\n')
    prompt_lines = [i for i in prompt_lines if not i.startswith('================') and not re.search(pattern_1, i) and not re.search(pattern_2, i)]
    prompt = '\n'.join(prompt_lines)
    return prompt


def refactor_test_res(focal_res):
    focal_res = reformat_prompt(focal_res)
    focal_res_lines = focal_res.split('\n')
    processed_lines = [i for i in focal_res_lines if '<MagicMock' not in i and 'MonkeyPatch object at 0x' not in i and 'create_mock_collection at 0x' not in i and 'object at 0x' not in i and 'instance at 0x' not in i and not ('0x' in i and '>' in i)]
    return '\n'.join(processed_lines)
    # pass
