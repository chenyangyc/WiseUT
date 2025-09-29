import os
import ast
import astor
import pickle
from tqdm import tqdm
from collections import defaultdict
from core.base_branch import Branch

'''
提取python类
methods键存储了类中所有的方法定义，使用了列表推导式来筛选出类型为ast.FunctionDef的节点。
init键存储了__init__方法的源代码，也是通过列表推导式来筛选出方法名为__init__的节点，并使用astor.to_source将其转化为源代码字符串。
attr键存储了属性赋值语句的源代码，同样使用了列表推导式和astor.to_source来提取和转化。
comment键存储了类定义处的文档字符串，使用ast.get_docstring方法获取。
content键存储了整个类定义的源代码，同样使用astor.to_source来转化。
'''
class ClassDefVisitor(ast.NodeVisitor):
    def __init__(self):
        self.info = defaultdict(dict)

    def visit_ClassDef(self, node):
        class_name = node.name
        
        self.info[class_name]['methods'] = set([n for n in node.body if isinstance(n, ast.FunctionDef)])
        self.info[class_name]['init'] = [astor.to_source(n) for n in node.body if isinstance(n, ast.FunctionDef) and n.name == '__init__']
        self.info[class_name]['attr'] = [astor.to_source(n) for n in node.body if isinstance(n, ast.Assign)]
        docstring = ast.get_docstring(node)
        if docstring:
            self.info[class_name]['comment'] = docstring
        self.info[class_name]['content'] = astor.to_source(node)
        self.generic_visit(node)


class ClassInstantiationVisitor(ast.NodeVisitor):
    def __init__(self):
        self.instance_creations = set()

    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute) and node.func.attr[0].isupper():  # Checking for attributes with uppercase names
            # This assumes that the object's attribute is the class name (common naming convention)
            self.instance_creations.add(node.func.attr)
        elif isinstance(node.func, ast.Name) and node.func.id[0].isupper():  # Assuming class names start with uppercase letters
            self.instance_creations.add(node.func.id)
        self.generic_visit(node)


class FunctionDefVisitor(ast.NodeVisitor):
    def __init__(self):
        self.current_class = None
        self.functions = list()

    def visit_ClassDef(self, node):
        self.current_class = node.name
        self.generic_visit(node)  # Visit methods within the class
        self.current_class = None

    def visit_FunctionDef(self, node):
        if self.current_class:
            # It's a method within the current class
            self.functions.append((self.current_class, node))
        else:
            # It's a standalone function
            self.functions.append((None, node))
        self.generic_visit(node)  # Visit any nested nodes within the function


class FunctionCallVisitor(ast.NodeVisitor):
    def __init__(self):
        # Stores function calls in the format (caller, function)
        self.function_calls = set()

    def visit_Call(self, node):
        # Check if it's a normal function call such as func()
        if isinstance(node.func, ast.Name):
            self.function_calls.add((None, node.func.id))
        # Check if it's a method call such as instance.method()
        elif isinstance(node.func, ast.Attribute):
            caller = self._get_caller(node.func.value)
            if caller != 'unittest':
                self.function_calls.add((caller, node.func.attr))
        self.generic_visit(node)
    

    def _get_caller(self, node):
        """
        Recursively retrieve the name of the variable that is calling the method.
        """
        if isinstance(node, ast.Name):
            return node.id
        return None

class ConditionVisitor(ast.NodeVisitor):
    def __init__(self):
        self.functions = set()  # 存储函数名，格式为完整名称 "a.b"
        self.variables = set()  # 存储变量名，格式为完整名称 "a.b"
        self.branches = set() # 存储分支信息，使用 Branch 对象

    def visit_If(self, node):
        """处理 if 语句中的条件表达式"""
        local_functions, local_variables = self.extract_from_condition(node.test)
        self.branches.add(Branch(node.lineno, node.col_offset, node.end_lineno, node.end_col_offset, astor.to_source(node).strip(), local_functions, local_variables))
        self.generic_visit(node)

    def visit_While(self, node):
        """处理 while 语句中的条件表达式"""
        local_functions, local_variables = self.extract_from_condition(node.test)
        self.branches.add(Branch(node.lineno, node.col_offset, node.end_lineno, node.end_col_offset, astor.to_source(node).strip(), local_functions, local_variables))
        self.generic_visit(node)
        

    def visit_Assert(self, node):
        """处理 assert 语句中的条件表达式"""
        local_functions, local_variables = self.extract_from_condition(node.test)
        self.branches.add(Branch(node.lineno, node.col_offset, node.end_lineno, node.end_col_offset, astor.to_source(node).strip(), local_functions, local_variables))
        self.generic_visit(node)

    def visit_Match(self, node):
        """处理 match 语句中的条件表达式"""
        if node.subject:
            local_functions, local_variables = self.extract_from_condition(node.subject)
            self.branches.add(Branch(node.lineno, node.col_offset, node.end_lineno, node.end_col_offset, astor.to_source(node).strip(), local_functions, local_variables))
        for case in node.cases:
            self.visit(case)


    def visit_IfExp(self, node):
        """处理条件表达式中的条件、主体和 else 部分，合并为一个完整分支"""
        # 提取条件、主体和 else 部分的信息
        cond_functions, cond_variables = self.extract_from_condition(node.test)
        body_functions, body_variables = self.extract_from_condition(node.body)
        else_functions, else_variables = self.extract_from_condition(node.orelse)

        # 合并函数和变量信息
        combined_functions = cond_functions.union(body_functions, else_functions)
        combined_variables = cond_variables.union(body_variables, else_variables)
        
        # 添加到分支
        self.branches.add(Branch(node.lineno, node.col_offset, node.end_lineno, node.end_col_offset, astor.to_source(node).strip(), combined_functions, combined_variables))

        # 递归访问子节点
        self.generic_visit(node)


    def extract_from_condition(self, node):
        """
        提取条件表达式中的函数和变量，并返回该分支的函数和变量集合。
        """
        # 局部集合，用于存储当前调用的函数和变量
        local_functions = set()
        local_variables = set()

        if isinstance(node, ast.Call):
            # 如果是函数调用，处理函数信息
            (func_caller, func_name) = self._process_call(node)
            if func_name:
                local_functions.add((func_caller, func_name))
                self.functions.add((func_caller, func_name))  # 保留全局逻辑

            # 递归处理函数参数中可能包含的变量或函数
            for arg in node.args:
                sub_functions, sub_variables = self.extract_from_condition(arg)
                local_functions.update(sub_functions)
                local_variables.update(sub_variables)

            for keyword in node.keywords:
                sub_functions, sub_variables = self.extract_from_condition(keyword.value)
                local_functions.update(sub_functions)
                local_variables.update(sub_variables)

        elif isinstance(node, ast.Name):
            # 如果是简单变量，直接记录变量名
            local_variables.add(node.id)
            self.variables.add(node.id)  # 保留全局逻辑

        elif isinstance(node, ast.Attribute):
            # 如果是对象属性访问，将其作为完整变量记录
            variable_name = self._get_full_attribute_name(node)
            local_variables.add(variable_name)
            self.variables.add(variable_name)  # 保留全局逻辑

        else:
            # 对其他类型的节点进行递归处理，以确保不遗漏任何条件部分
            for field, value in ast.iter_fields(node):
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, ast.AST):
                            sub_functions, sub_variables = self.extract_from_condition(item)
                            local_functions.update(sub_functions)
                            local_variables.update(sub_variables)
                elif isinstance(value, ast.AST):
                    sub_functions, sub_variables = self.extract_from_condition(value)
                    local_functions.update(sub_functions)
                    local_variables.update(sub_variables)

        # 返回本次调用的局部函数和变量集合
        return local_functions, local_variables


    def _process_call(self, node):
        """
        处理函数调用，提取函数名（包括模块名或调用者），
        返回 (caller, name) 的形式。
        """
        if isinstance(node.func, ast.Name):
            # 普通函数调用，没有模块名
            return (None, node.func.id)
        elif isinstance(node.func, ast.Attribute):
            # 属性访问，返回调用者和函数名
            caller = self._get_caller(node.func.value)
            return (caller, node.func.attr)
        return (None, None)


    def _get_full_attribute_name(self, node):
        """
        获取完整的属性访问名称，例如 "a.b.c"。
        """
        if isinstance(node, ast.Name):
            return node.id  # 简单变量名，直接返回
        elif isinstance(node, ast.Attribute):
            # 递归获取调用链的完整路径
            parent = self._get_full_attribute_name(node.value)
            return f"{parent}.{node.attr}"
        return None
    
    
    def _get_caller(self, node):
        """
        Recursively retrieve the name of the variable that is calling the method.
        """
        if isinstance(node, ast.Name):
            return node.id
        return None


class CompleteAssignmentVisitor(ast.NodeVisitor):
    def __init__(self):
        # 初始化
        self.all_variables = set()  # 存储所有遇到的变量（包括赋值目标和右侧出现的变量）
        self.dependencies = {}  # 存储变量的依赖关系，结构为：变量 -> { 'function': [], 'identifier': [] }

    def visit_Assign(self, node):
        """
        处理赋值节点（`Assign`），提取赋值左侧的变量名，以及右侧的变量和函数调用信息。
        """
        # 提取赋值目标中的变量名（只提取简单变量名或属性表达式，如 a 或 a.b）
        targets = [self._get_variable_name(target) for target in node.targets if isinstance(target, (ast.Name, ast.Attribute))]
        # 将这些目标变量加入 all_variables 集合
        self.all_variables.update(targets)

        # 获取赋值右侧的值节点
        value = node.value
        # 初始化存储右侧的变量名和函数调用
        right_side_variables = set()
        right_side_functions = set()

        # 从右侧表达式中提取变量和函数调用
        self.extract_from_value(value, right_side_variables, right_side_functions)
        
        # 对于每个赋值目标，记录依赖关系
        for target in targets:
            if target not in self.dependencies:
                # 初始化依赖结构
                self.dependencies[target] = {'function': [], 'identifier': []}
            # 记录右侧的函数调用
            self.dependencies[target]['function'].extend(list(right_side_functions))
            # 记录右侧使用的变量（排除目标本身，避免循环依赖）
            self.dependencies[target]['identifier'].extend(list(right_side_variables - set(targets)))
        
        # 继续遍历子节点
        self.generic_visit(node)

    def extract_from_value(self, node, variables, functions):
        """
        提取表达式中的变量和函数调用信息。
        遍历表达式节点，提取所有涉及的变量名（`variables`）和函数调用（`functions`）。
        函数调用信息返回为 (caller, name) 的形式。
        """
        if isinstance(node, ast.Name):
            # 如果是变量节点，记录变量名
            variables.add(node.id)
            self.all_variables.add(node.id)
        elif isinstance(node, ast.Call):
            # 如果是函数调用，提取函数调用相关信息
            if isinstance(node.func, ast.Attribute):
                # 如果是方法调用，如 `obj.method()`，提取调用者和方法名
                caller = self._get_variable_name(node.func.value)
                function_name = node.func.attr
                functions.add((caller, function_name))  # 记录为 (caller, name)
            elif isinstance(node.func, ast.Name):
                # 如果是普通函数调用，如 `func()`，记录函数名
                functions.add((None, node.func.id))  # 无调用者时，caller 为 None
            
            # 遍历函数调用的所有参数，递归提取其中的变量和函数调用
            for arg in node.args:
                self.extract_from_value(arg, variables, functions)
            for keyword in node.keywords:
                # 处理关键字参数的值部分
                self.extract_from_value(keyword.value, variables, functions)
        elif isinstance(node, ast.BinOp):
            # 如果是二元操作符，如 `a + b`，递归处理左右两边的表达式
            self.extract_from_value(node.left, variables, functions)
            self.extract_from_value(node.right, variables, functions)
        elif isinstance(node, ast.Attribute):
            # 如果是对象属性访问，如 `a.b`，将整个属性表达式作为变量
            variable_name = self._get_variable_name(node)  # 提取完整属性名（如 a.b）
            variables.add(variable_name)
            self.all_variables.add(variable_name)
        else:
            # 对于其他类型的节点，递归提取所有字段和子节点中的变量和函数调用
            for field, value in ast.iter_fields(node):
                if isinstance(value, list):
                    # 如果字段是列表，遍历列表中的所有节点
                    for item in value:
                        if isinstance(item, ast.AST):
                            self.extract_from_value(item, variables, functions)
                elif isinstance(value, ast.AST):
                    # 如果字段是单个子节点，递归处理
                    self.extract_from_value(value, variables, functions)

    def _get_variable_name(self, node):
        """
        获取变量的完整名称（包括属性访问，如 a.b）。
        """
        if isinstance(node, ast.Name):
            return node.id  # 简单变量，直接返回名称
        elif isinstance(node, ast.Attribute):
            # 如果是属性访问（如 a.b），递归提取完整路径
            return f"{self._get_variable_name(node.value)}.{node.attr}"
        return None  # 其他情况返回 None


class VariableTypeExtractor(ast.NodeVisitor):
    '''
    给定一段代码，获取其中所有变量的类型信息。
    '''
    def __init__(self):
        self.variables = {}  # 存储变量及其类型

    def visit_FunctionDef(self, node):
        # 解析函数参数
        for arg in node.args.args:
            if arg.annotation:
                # 如果参数有类型注解，提取类型名
                self.variables[arg.arg] = self._get_type_name(arg.annotation)
            else:
                # 如果没有类型注解，类型设置为变量名本身
                self.variables[arg.arg] = arg.arg
        # 继续遍历函数体
        self.generic_visit(node)

    def visit_Assign(self, node):
        # 解析普通赋值语句
        value_type = self._get_value_type(node.value)
        for target in node.targets:
            if isinstance(target, ast.Name):
                self.variables[target.id] = value_type
        self.generic_visit(node)

    def visit_AnnAssign(self, node):
        # 解析带类型注解的赋值
        if isinstance(node.target, ast.Name):
            if node.annotation:
                # 如果有类型注解，提取类型
                self.variables[node.target.id] = self._get_type_name(node.annotation)
            elif node.value:
                # 如果没有注解但有赋值，推断类型
                self.variables[node.target.id] = self._get_value_type(node.value)
            else:
                # 无法确定时，使用变量名作为类型
                self.variables[node.target.id] = node.target.id
        self.generic_visit(node)

    def _get_value_type(self, value):
        """推断值的类型"""
        if isinstance(value, ast.Call):
            # 如果是函数调用，推断为函数名称
            if isinstance(value.func, ast.Name):
                return value.func.id
            elif isinstance(value.func, ast.Attribute):
                caller = self._get_caller(value.func.value)
                return f"{caller}.{value.func.attr}" if caller else value.func.attr
        elif isinstance(value, ast.Constant):
            # 常量值的类型
            return type(value.value).__name__
        elif isinstance(value, ast.Name):
            # 如果是另一个变量，返回该变量名
            return value.id
        return "Unknown"

    def _get_caller(self, node):
        """
        Recursively retrieve the name of the variable that is calling the method.
        """
        if isinstance(node, ast.Name):
            return node.id
        return None

    def _get_type_name(self, node):
        """提取类型注解的名称"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Subscript):
            # 处理诸如 List[int] 之类的类型
            return self._get_type_name(node.value)
        elif isinstance(node, ast.Attribute):
            return node.attr
        return "Unknown"

    def extract(self, code):
        """解析代码并提取变量类型"""
        tree = ast.parse(code)
        self.visit(tree)
        return self.variables


class InitFunctionVisitor(ast.NodeVisitor):
    def __init__(self):
        self.constructor_calls = set()
    
    def visit_FunctionDef(self, node):
        # 只处理 __init__ 函数
        if node.name == "__init__":
            self.generic_visit(node)

    def visit_Call(self, node):
        # Check if it's a normal function call such as func()
        if isinstance(node.func, ast.Name):
            self.constructor_calls.add((None, node.func.id))
        # Check if it's a method call such as instance.method()
        elif isinstance(node.func, ast.Attribute):
            caller = self._get_caller(node.func.value)
            if caller != 'unittest':
                self.constructor_calls.add((caller, node.func.attr))
        self.generic_visit(node)
    

    def _get_caller(self, node):
        """
        Recursively retrieve the name of the variable that is calling the method.
        """
        if isinstance(node, ast.Name):
            return node.id
        return None