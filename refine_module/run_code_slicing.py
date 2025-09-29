from collections import defaultdict
import copy
import json
import os

from tree_sitter import Language, Parser
import tree_sitter_java as tsjava

JAVA_LANGUAGE = Language(tsjava.language(), name='java')
parser = Parser()
parser.set_language(JAVA_LANGUAGE)

from tree_sitter_query import statement_assignment_expression_query, assignment_expression_query, statement_declaration_query, statement_query, process_declaration_query, process_assignment_query, process_method_invocation_query, find_affected_variables_in_method_invocation


# 并查集
class UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))
        self.rank = [0] * n
        self.count = n

    def find(self, x):
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x, y):
        rootX = self.find(x)
        rootY = self.find(y)
        if rootX != rootY:
            if self.rank[rootX] > self.rank[rootY]:
                self.parent[rootY] = rootX
            elif self.rank[rootX] < self.rank[rootY]:
                self.parent[rootX] = rootY
            else:
                self.parent[rootY] = rootX
                self.rank[rootX] += 1
            self.count -= 1

    def connected(self, x, y):
        return self.find(x) == self.find(y)


def find_connected_components(graph):
    """查找图中的所有连通分量。"""
    nodes = list(graph.keys())
    n = len(nodes)
    uf = UnionFind(n)

    # 将图中的边加入并查集
    for node, neighbors in graph.items():
        node_index = nodes.index(node)
        for neighbor in neighbors:
            neighbor_index = nodes.index(neighbor)
            uf.union(node_index, neighbor_index)

    # 构建连通分量
    components = {}
    for i, node in enumerate(nodes):
        root = uf.find(i)
        if root not in components:
            components[root] = []
        components[root].append(node)

    return list(components.values())

def targan_to_find_related_variable(variable_related):
    """通过并查集找到连通块中的所有变量。"""
    variable_index = {}
    index_variable = {}
    index = 0
    for variable in variable_related.keys():
        variable_index[variable] = index
        index_variable[index] = variable
        index += 1
    
    graph = {}
    for variable, info in variable_related.items():
        graph[variable_index[variable]] = []
        for related_variable in info:
            graph[variable_index[variable]].append(variable_index[related_variable])
    
    connected_components = find_connected_components(graph)
    
    for component in connected_components:
        for variable in component:
            for related_variable in component:
                if related_variable != variable:
                    variable_related[index_variable[related_variable]].append(index_variable[variable])

    for key, value in variable_related.items():
        variable_related[key] = list(set(value))
        
    return variable_related

def find_declarator_statement(node, variables):
    '''找到method中所有的变量声明，保存到variables中'''
    '''或者找到所有的object'''
    if node.type == 'local_variable_declaration':
        for child in node.children:
            if child.type == 'variable_declarator':
                name_node = child.child_by_field_name('name')
                variables.append(name_node.text.decode())
                
    if node.type == 'method_invocation':
        object_node = node.child_by_field_name('object')
        if object_node is not None and (object_node.type == 'identifier' or object_node.type == 'this' or object_node.type == 'super'):
            object_name = object_node.text.decode()
            variables.append(object_name)
        
    if node.type == 'field_access':
        object_node = node.child_by_field_name('object')
        if object_node is not None and (object_node.type == 'identifier' or object_node.type == 'this' or object_node.type == 'super'):
            object_name = object_node.text.decode()
            variables.append(object_name)
    if node.type == 'assignment_expression':
        left_node = node.child_by_field_name('left')
        if left_node is not None and left_node.type == 'identifier':
            variables.append(left_node.text.decode())
        
    for child in node.children:
        find_declarator_statement(child, variables)
        
def find_related_variable(code, local_variable):
    '''找到所有的变量之间的关系'''
    root = parser.parse(bytes(code, "utf8")).root_node
    variable_related = defaultdict(list)
    statement_query = JAVA_LANGUAGE.query('''(method_declaration
                                                body:(_
                                                    (_)@statement
                                                )
                                            )''')
    statement_list = statement_query.captures(parser.parse(bytes(code, "utf8")).root_node)
    
    for statement_node, _ in statement_list:
        variable_list = []
        find_node_variable(statement_node, variable_list, local_variable)
        for v1 in variable_list:
            for v2 in variable_list:
                if v1 != v2 and v1 in local_variable and v2 in local_variable:
                    variable_related[v1].append(v2)
                    variable_related[v2].append(v1)
    return variable_related


def find_node_variable(node, variable_list, local_variable):
    '''找到语句中的变量'''
    if node.text.decode() in local_variable:
        name = node.text.decode()
        variable_list.append(name)
    for child in node.children:
        find_node_variable(child, variable_list, local_variable)

new_code = ''
def convert_else_to_if(node, condition, code):
    global new_code
    '''将else语句转换为if语句'''
    if node.type == 'if_statement':
            
        condition_node = node.child_by_field_name('condition')
        alternative_node = node.child_by_field_name('alternative')
        else_node = None
        for child in node.children:
            if child.type == 'else':
                else_node = child
                break
        if condition_node is not None and alternative_node is not None:
            else_content = code.encode()[else_node.start_byte : alternative_node.end_byte].decode()
            if_condition = condition_node.text.decode()
            if condition is not None:
                if_condition = f'{condition} && !{if_condition}'
            else:
                if_condition = f'!{if_condition}'
            new_if_content = f'if ({if_condition}) {{ {alternative_node.text.decode()} }}'
            new_code = new_code.replace(else_content, new_if_content)
            convert_else_to_if(alternative_node, if_condition, code)
        return

    for child in node.children:
        convert_else_to_if(child, condition, code)
        
        
def starts_with_assert(input_string):
    trimmed_input = ''.join(input_string.split())
    return trimmed_input.lower().startswith('assert')

def assertion_in_other_assertion(assertion1, assertion2):
    if assertion1.start_byte >= assertion2.start_byte and assertion1.end_byte <= assertion2.end_byte:
        return True
    return False

def find_assertions(code, local_variable):
    '''找到所有的断言'''
    root = parser.parse(bytes(code, "utf8")).root_node
    assertions = []
    expression_statement_query = JAVA_LANGUAGE.query('''(expression_statement)@1''')
    expression_statement_list = expression_statement_query.captures(root)
    
    for expression_statement_node, _ in expression_statement_list:
        if starts_with_assert(expression_statement_node.text.decode()):
            variable_list = []
            find_node_variable(expression_statement_node, variable_list, local_variable)
            assertions.append((expression_statement_node, variable_list))
    # 有一些assertion会出现在其他assertion里面，删掉在里面的
    del_assertions = []
    for assertion in assertions:
        for other_assertion in assertions:
            if assertion_in_other_assertion(assertion[0], other_assertion[0]) and assertion != other_assertion:
                del_assertions.append(assertion)
                break
    for del_assertion in del_assertions:
        assertions.remove(del_assertion)
    return assertions

# def find_assertion(node, assertions, local_variable, variable_list):
#     """Find the assertion in the code."""
#     if node.type in ['while_statement', 'for_statement', 'if_statement']:
#         condition_node = node.child_by_field_name('condition')
#         if condition_node is not None:
#             find_node_variable(condition_node, variable_list, local_variable)
            
    
#     if node.type == "expression_statement":
#         invocation_node = None
#         for child in node.children:
#             if child.type == "method_invocation":
#                 invocation_node = child
#                 break
#         if invocation_node is None:
#             return  
#         name_node = invocation_node.child_by_field_name('name')
#         if name_node is None:
#             return
#         name = name_node.text.decode()
#         if 'assert' in name:
#             find_node_variable(node, variable_list, local_variable)
#             assertions.append((node, variable_list))
#     for child in node.children:
#         single_variable_list = copy.deepcopy(variable_list)
#         find_assertion(child, assertions, local_variable, single_variable_list)

def del_extra_information(code, assertion, local_variable):   
    statement_query = JAVA_LANGUAGE.query('''(method_declaration
                                                body:(_
                                                    (_)@statement
                                                )
                                            )''')
    statement_list = statement_query.captures(parser.parse(bytes(code, "utf8")).root_node)
    del_list = []
    for statement_node, _ in statement_list:
        if assertion[0].text.decode() in statement_node.text.decode():
            continue
        variable_list = []
        find_node_variable(statement_node, variable_list, local_variable)
        related_variable = [variable for variable in variable_list if variable in assertion[1]]
        if not related_variable:
            del_list.append((statement_node.start_byte, statement_node.end_byte))
    return del_list

# def del_extra_information(node, code, assertion, local_variable, del_list, try_node):
#     '''删除多余的信息，包括断言之外的信息，和断言变量无关的信息'''
#     if try_node is not None and node.start_byte == try_node.start_byte and node.end_byte == try_node.end_byte:
#         '''如果是try语句，不删除其他信息，仅仅删除多余的断言'''
#         del_assertion_information(node, code, assertion, local_variable, del_list)
#         return
#     if node.type in ['local_variable_declaration', 'expression_statement'] and node.parent.type != 'for_statement':
#         if 'assert' in node.text.decode():
#             if node.end_byte != assertion[0].end_byte:
#                 del_list.append((node.start_byte, node.end_byte))
#         else:
#             variable_list = []
#             find_node_variable(node, variable_list, local_variable)
#             related_variable = [variable for variable in variable_list if variable in assertion[1]]
#             if not related_variable:
#                 del_list.append((node.start_byte, node.end_byte))
#         return
#     for child in node.children:
#         del_extra_information(child, code, assertion, local_variable, del_list, try_node)

def is_del(node):
    '''判断statement是否可以删除'''
    if node.type in ['local_variable_declaration', 'expression_statement', 'return_statement', 'break_statement', 'continue_statement']:
        return False
    isok = True
    if node.type == 'for_statement':
        body_node = node.child_by_field_name('body')
        if body_node is None:
            return True
        return is_del(body_node)
    else:
        for child in node.children:
            isok = isok and is_del(child)
    return isok
    

def process_empty_branch(node, del_list):   
    '''删除空的分支'''
    global new_code

    if node.type in ['if_statement', 'while_statement', 'for_statement', 'do_statement', 'try_statement']:
        if is_del(node):
            del_list.append((node.start_byte, node.end_byte))
            return
    if node.type == 'block' and node.parent.type == 'block':
        if is_del(node):
            del_list.append((node.start_byte, node.end_byte))
            return
    for child in node.children:
        process_empty_branch(child, del_list)

def delete_code(code, del_list):
    '''删除需要删除列表中的代码'''
    del_list = sorted(del_list, key=lambda x: x[0], reverse=False)
    new_code = ''.encode()
    code = code.encode('utf-8')
    now_byte = 0
    for start_byte, end_byte in del_list:
        new_code += code[now_byte:start_byte]
        now_byte = max(end_byte, now_byte)
    new_code += code[now_byte:]
    return new_code.decode('utf-8')

def is_node_in_catch_or_try(node):
    '''判断节点是否在try或者catch中'''
    if node.type == 'program':
        return False
    if node.type == 'catch_clause':
        return True
    if node.type == 'try_statement':
        return True
    return is_node_in_catch_or_try(node.parent)

def find_try_node(node):
    '''找到try语句'''
    if node.type == 'try_statement':
        return node.child_by_field_name('body')
    return find_try_node(node.parent)


def delete_assertion_after(code, local_variable):
    '''删除断言之后的代码'''
    root = parser.parse(bytes(code, "utf8")).root_node
    
    assertions = find_assertions(code, local_variable)
    
    assertion = assertions[0][0]
    delete_assertion_after_list = []
    method_node = None
    for child in root.children:
        if child.type == 'method_declaration':
            method_node = child
            break
    if method_node is None:
        return code
    body_node = method_node.child_by_field_name('body')
    if body_node is None:
        return code
    for child in body_node.children:
        if child.type == '{' or child.type == '}':
            continue
        if child.start_byte <= assertion.start_byte:
            continue
        if assertion.text.decode() not in child.text.decode():
            delete_assertion_after_list.append((child.start_byte, child.end_byte))
    code = delete_code(code, delete_assertion_after_list)
    return code

def split_assertion(code):
    """Split the code into assertions and the rest of the code."""
    tree = parser.parse(bytes(code, "utf8"))
    root = tree.root_node
    # 转换代码中的else，全都变成if
    global new_code
    new_code = copy.deepcopy(code)
    convert_else_to_if(root, None, code)
    
    code = copy.deepcopy(new_code)
    root = parser.parse(bytes(code, "utf8")).root_node
    
    # 找到所有变量，以及变量之间的关系
    local_variable = []
    find_declarator_statement(root, local_variable)
    local_variable = list(set(local_variable))
    variable_related = find_related_variable(code, local_variable)
    
    # 删掉自环和重复节点
    for variable in list(variable_related.keys()):
        no_self_list = []
        for related_variable in variable_related[variable]:
            if related_variable != variable:
                no_self_list.append(related_variable)
        no_self_list = list(set(no_self_list))
        variable_related[variable] = no_self_list
        for related_variable in variable_related[variable]:
            variable_related[related_variable].append(variable)
    for variable in variable_related.keys():
        variable_related[variable] = list(set(variable_related[variable]))
    
    variable_related = targan_to_find_related_variable(variable_related)
    
    # 找到所有的断言
    assertions = find_assertions(code, local_variable)
    
    now_code = copy.deepcopy(new_code)
    global del_code
    
    split_assertion_code = []
    for node, variable_list in assertions:
        try_node = None
        
        if is_node_in_catch_or_try(node):
            try_node = find_try_node(node)
            if try_node is not None:
                try_variable_list = []
                find_node_variable(try_node, try_variable_list, local_variable)
                variable_list = list(set(variable_list) | set(try_variable_list))
        new_variable = []
        for variable in variable_list:
            new_variable.extend(variable_related[variable])
            new_variable.append(variable)
        new_variable = list(set(new_variable))
        
        del_list = del_extra_information(code, (node, new_variable), local_variable)
        for other_node, other_variable_list in assertions:
            if node.text.decode() in other_node.text.decode():
                continue
            del_list.append((other_node.start_byte, other_node.end_byte))
        del_list = sorted(del_list, key=lambda x: x[0], reverse=False)
        new_code = delete_code(now_code, del_list)
        
        nroot =  parser.parse(bytes(new_code, "utf8")).root_node
        del_list = []
        process_empty_branch(nroot, del_list)
        del_list = sorted(del_list, key=lambda x: x[0], reverse=False)
        new_code = delete_code(new_code, del_list)
        
        # 删掉assertion之后的代码
        new_code = delete_assertion_after(new_code, local_variable)
        new_code_lines = new_code.split('\n')
        new_code_lines = [line for line in new_code_lines if line.strip() and not line.strip().startswith('//')]
        new_code = '\n'.join(new_code_lines)
        
        split_assertion_code.append(new_code)
        # print('\n')
    
    return split_assertion_code

def get_method_name_node(node):
    if node.type == 'method_declaration':
        return node.child_by_field_name('name')
    for child in node.children:
        name_node = get_method_name_node(child)
        if name_node is not None:
            return name_node
    return None

def get_method_name(code):
    '''提取method的名字'''
    tree = parser.parse(bytes(code, "utf8"))
    root = tree.root_node
    return get_method_name_node(root).text.decode()

def remove_whitespace(s):
    # 使用 str 的 replace 方法去除常见的空白字符
    for whitespace in [' ', '\t', '\n', '\r']:
        s = s.replace(whitespace, '')
    return s

def merge_code(code1, code2):
    code_lines = []
    code1_lines = code1.split('\n')
    code2_lines = code2.split('\n')
    
    error_query = JAVA_LANGUAGE.query('''(ERROR)@1''')
    l1, l2, i1, i2 = len(code1_lines), len(code2_lines), 0, 0
    while i1 < l1 and i2 < l2:
        if 'assert' in code1_lines[i1].lower():
            tmp_str = ''
            while i1 < l1:
                tmp_str += code1_lines[i1] + '\n'
                code_lines.append(code1_lines[i1])
                i1 += 1
                
                if len(error_query.captures(parser.parse(bytes(tmp_str, "utf8")).root_node)) == 0 and tmp_str.strip().endswith(';'):
                    break
            if len(error_query.captures(parser.parse(bytes(tmp_str, "utf8")).root_node)) > 0 and tmp_str.strip().endswith(';'):
                raise Exception('merge error')
        elif 'assert' in code2_lines[i2].lower():
            tmp_str = ''
            while i2 < l2:
                tmp_str += code2_lines[i2] + '\n'
                code_lines.append(code2_lines[i2])
                i2 += 1
                
                if len(error_query.captures(parser.parse(bytes(tmp_str, "utf8")).root_node)) == 0 and tmp_str.strip().endswith(';'):
                    break
            if len(error_query.captures(parser.parse(bytes(tmp_str, "utf8")).root_node)) > 0 and tmp_str.strip().endswith(';'):
                raise Exception('merge error')
        elif remove_whitespace(code1_lines[i1]) == remove_whitespace(code2_lines[i2]):
            code_lines.append(code1_lines[i1])
            i1 += 1
            i2 += 1
        else:
            
            raise Exception('merge error')
            return code1
    while i1 < l1:
        code_lines.append(code1_lines[i1])
        i1 += 1
    while i2 < l2:
        code_lines.append(code2_lines[i2])
        i2 += 1
    return '\n'.join(code_lines)

def merge_preorder(split_assertion_code):
    preorder_dict = defaultdict(list)
    
    for code in split_assertion_code:
        assertions = find_assertions(code, [])
        assertion = assertions[0]
        original_code = copy.deepcopy(code)
        code = code.replace(assertion[0].text.decode(), '')
        preorder_code = remove_whitespace(code)
        preorder_dict[preorder_code].append(original_code)
    
    merge_assertions = []
    for preorder_code, plist in preorder_dict.items():
        mcode = plist[0]
        for code in plist[1:]:
            mcode = merge_code(mcode, code)
        merge_assertions.append(mcode)
    
    return merge_assertions

def split_assignment_expression(code):
    root = parser.parse(bytes(code, "utf8")).root_node
    assignment_list = []
    statement_assignment_expression = statement_assignment_expression_query.captures(root)
    for i in range(0, len(statement_assignment_expression), 3):
        statement_node = statement_assignment_expression[i][0]
        assignment_expression_result = {
            'name': [],
            'value': '',
            'start_byte': statement_node.start_byte,
            'end_byte': statement_node.end_byte,
            'text': ''
        }
        
        assignment_expression = assignment_expression_query.captures(statement_node)
        for j in range(0, len(assignment_expression), 2):
            name_node = assignment_expression[j][0]
            value_node = assignment_expression[j + 1][0]
            assignment_expression_result['name'].append(name_node.text.decode())
            if value_node.type != 'assignment_expression':
                assignment_expression_result['value'] = value_node.text.decode()
        for name in assignment_expression_result['name']:
            assignment_expression_result['text'] += f'{name} = {assignment_expression_result["value"]};\n        '
        assignment_list.append(assignment_expression_result)
        
    assignment_list = sorted(assignment_list, key=lambda x: x['start_byte'])
    new_code = ''.encode()
    code = code.encode('utf-8')
    start_byte = 0
    for assignment in assignment_list:
        new_code += code[start_byte:assignment['start_byte']]
        new_code += assignment['text'].encode()
        start_byte = assignment['end_byte']
    new_code += code[start_byte:]
    new_code = new_code.decode('utf-8')
    return new_code

def split_variable_declaration(code):
    root = parser.parse(bytes(code, "utf8")).root_node
    declarator_list = []
    local_variable_declaration = statement_declaration_query.captures(root)
    i = 0
    while i < len(local_variable_declaration):
        statement_node = local_variable_declaration[i][0]
        type_node = local_variable_declaration[i + 1][0]
        local_variable_declaration_result = {
            'type': type_node.text.decode(),
            'declarator': [],
            'start_byte': statement_node.start_byte,
            'end_byte': statement_node.end_byte,
            'text': ''
        }
        
        i = i + 2
        while i < len(local_variable_declaration) and local_variable_declaration[i][1] == 'declarator':
            declarator = local_variable_declaration[i][0]
            local_variable_declaration_result['declarator'].append(declarator.text.decode())
            local_variable_declaration_result['text'] += f'{local_variable_declaration_result["type"]} {declarator.text.decode()};\n        '
            i += 1
        declarator_list.append(local_variable_declaration_result)
    
    declarator_list = sorted(declarator_list, key=lambda x: x['start_byte'])
    new_code = ''.encode()
    code = code.encode('utf-8')
    start_byte = 0
    for declarator in declarator_list:
        new_code += code[start_byte:declarator['start_byte']]
        new_code += declarator['text'].encode()
        start_byte = declarator['end_byte']
    new_code += code[start_byte:]
    new_code = new_code.decode('utf-8')
    return new_code

class statement:
    def __init__(self, node, type, local_variables=[]):
        self.node = node
        self.type = type
        self.node_type = node.type
        self.text = node.text.decode()
        self.start_byte = node.start_byte
        self.end_byte = node.end_byte
        self.local_variables = local_variables
        self.variables = []
        self.name = ''
        self.dimensions = ''
        self.value = []
        self.delete_value = []
        self.variable_ok = {}
        self.variable_type = ''
        self.is_delete = False
        self.get_variables()
    
    def get_variables(self):
        find_node_variable(self.node, self.variables, self.local_variables)
        self.variables = list(set(self.variables))
        if self.type == 'assignment':
            assignment_node = self.node.child(0)
            name_node = assignment_node.child_by_field_name('left')
            self.name = name_node.text.decode()
            value_node = assignment_node.child_by_field_name('right')
            find_node_variable(value_node, self.value, self.local_variables)
            self.delete_value = find_affected_variables_in_method_invocation(self.node)
            self.delete_value.append(self.name)
            self.delete_value = [variable for variable in self.delete_value if variable in self.variables]
        elif self.type == 'declaration':
            type_node = self.node.child_by_field_name('type')
            self.variable_type = type_node.text.decode()
            declarator_node = self.node.child_by_field_name('declarator')
            name_node = declarator_node.child_by_field_name('name')
            self.name = name_node.text.decode()
            dimensions_ndoe = declarator_node.child_by_field_name('dimensions')
            if dimensions_ndoe is not None:
                self.dimensions = dimensions_ndoe.text.decode()
            value_node = declarator_node.child_by_field_name('value')
            if value_node is not None:
                find_node_variable(value_node, self.value, self.local_variables)
            self.delete_value = find_affected_variables_in_method_invocation(self.node)
            self.delete_value.append(self.name)
            self.delete_value = [variable for variable in self.delete_value if variable in self.variables]
        elif self.type == 'if_statement':
            consequence_node = self.node.child_by_field_name('consequence')
            self.value = self.variables
            find_node_variable(consequence_node, self.delete_value, self.local_variables)
            pass
        elif self.type == 'method_invocation':
            self.value = self.variables
            self.delete_value = find_affected_variables_in_method_invocation(self.node)
            self.delete_value.append(self.name)
            self.delete_value = [variable for variable in self.delete_value if variable in self.variables]
            pass
        else:
            self.value = copy.deepcopy(self.variables)
            self.delete_value = copy.deepcopy(self.variables)
        self.value = list(set(self.value))
        self.delete_value = list(set(self.delete_value))
        for value in self.delete_value:
            self.variable_ok[value] = False

def setup_statement(node, local_variables):
    if node.type == 'expression_statement':
        if node.child(0).type == 'method_invocation':
            if 'assert' in node.text.decode():
                return statement(node, 'assertion', local_variables)
            else:
                return statement(node, 'method_invocation', local_variables)
        elif node.child(0).type == 'assignment_expression':
            return statement(node, 'assignment', local_variables)
        return statement(node, 'expression_statement')
    elif node.type == 'local_variable_declaration':
        return statement(node, 'declaration', local_variables)
    return statement(node, node.type, local_variables)

def get_statement(code):
    root = parser.parse(bytes(code, "utf8")).root_node
    local_variables = []
    find_declarator_statement(root, local_variables)
    local_variables = list(set(local_variables))
    # local_variables = [variable for variable in local_variables if variable != 'this' and variable != 'super' and not variable[0].isupper()]
    process_statement_list = []
    statement_list = [setup_statement(node[0], local_variables) for node in statement_query.captures(root)]
    process_statement_list.extend([setup_statement(node[0], local_variables) for node in process_declaration_query.captures(root)])
    process_statement_list.extend([setup_statement(node[0], local_variables) for node in process_assignment_query.captures(root)])
    process_statement_list.extend([setup_statement(node[0], local_variables) for node in process_method_invocation_query.captures(root)])
    
    statement_list = sorted(statement_list, key=lambda x: x.start_byte, reverse=True)
    process_statement_list = sorted(process_statement_list, key=lambda x: x.start_byte, reverse=True)
    return statement_list, process_statement_list

def get_delete_statement_list(code, statement_list):
    '''
    找到assertion的statement，如果在分支里或者在循环里，则直接退出
    
    从最后一个开始,找到第一个赋值语句
    '''
    root = parser.parse(bytes(code, "utf8")).root_node
    local_variables = []
    find_declarator_statement(root, local_variables)
    local_variables = list(set(local_variables))
    # local_variables = [variable for variable in local_variables if not variable[0].isupper()]
    variable_type = defaultdict(str)
    variable_dimensions = defaultdict(str)
    for statement in statement_list:
        if statement.type == 'declaration':
            variable_type[statement.name] = statement.variable_type
            if statement.dimensions:
                variable_dimensions[statement.name] = statement.dimensions
    
    for variable in local_variables:
        isok = False
        for statement in statement_list:
            if variable in statement.delete_value:
                statement.variable_ok[variable] = isok
            if statement.name == variable and not isok:
                statement.variable_ok[variable] = False
                isok = True

    for i in range(len(statement_list)):
        statement = statement_list[i]
        if statement.type not in ['declaration', 'assignment', 'if_statement', 'method_invocation']:
            statement.variable_ok = {key: False for key in statement.variable_ok.keys()}
            statement.is_delete = False
        elif statement.type == 'assignment':
            if statement.name not in statement.variables:
                statement.is_delete = False
        else:
            statement.is_delete = all([isok for isok in statement.variable_ok.values()])
        if not statement.is_delete:
            for variable in statement.value:
                for j in range(i + 1, len(statement_list)):
                    if variable in statement_list[j].delete_value:
                        statement_list[j].variable_ok[variable] = False
                    if statement_list[j].name == variable:
                        statement_list[j].variable_ok[variable] = False
                        break
    del_list = []
    for i in range(len(statement_list)):
        statement = statement_list[i]
        if statement.is_delete:
            del_list.append((statement.start_byte, statement.end_byte))
    del_list = sorted(del_list, key=lambda x: x[0], reverse=False)
    new_code = delete_code(code, del_list)
    
    root = parser.parse(bytes(new_code, "utf8")).root_node
    statement_list = [setup_statement(node[0], local_variables) for node in statement_query.captures(root)]
    statement_list = sorted(statement_list, key=lambda x: x.start_byte)
    del_list = []
    for variable in local_variables:
        for i in range(len(statement_list)):
            range_statement = statement_list[i]
            if variable == range_statement.name:
                if range_statement.type == 'declaration':
                    break
                if range_statement.type == 'assignment':
                    if range_statement.name in variable_type:
                        if variable in variable_dimensions:
                            new_variable = f'{variable_type.get(variable)} {variable} {variable_dimensions.get(variable)}'
                        else:
                            new_variable = f'{variable_type.get(variable)} {variable}'
                        value_text = range_statement.text.split('=')[1]
                        declarator_code = f'{new_variable} = {value_text}'
                        del_list.append((range_statement.start_byte, range_statement.end_byte, declarator_code))
                    break
    del_list = sorted(del_list, key=lambda x: x[0], reverse=False)
    del_code = ''.encode()
    new_code = new_code.encode('utf-8')
    start = 0
    for start_byte, end_byte, declarator_code in del_list:
        del_code += new_code[start:start_byte]
        del_code += declarator_code.encode()
        start = end_byte
    del_code += new_code[start:]
    del_code = del_code.decode('utf-8')
    
    del_code = '\n'.join([line for line in del_code.split('\n') if line.strip()])
    return del_code


def splited_code(java_code):
    """给定java test源码，返回分割后的代码"""
    java_code = split_assignment_expression(java_code)
    java_code = split_variable_declaration(java_code)
    split_assertion_code = split_assertion(java_code)
    merge_assertion = merge_preorder(split_assertion_code)
    
    method_name = get_method_name(java_code)
    for id, split_code in enumerate(merge_assertion):
        new_method_name = f'{method_name}_split_{id}'
        merge_assertion[id] = split_code.replace(method_name, new_method_name)
    
    new_splited_codes = []
    for split_code in merge_assertion:
        statement_list, process_statement_list = get_statement(split_code)
        new_splited_code = get_delete_statement_list(split_code, statement_list)
        new_splited_codes.append(new_splited_code)

    return new_splited_codes

if __name__ == '__main__':
    JAVA_CODE = '''
public void testCreateCategoryDataset1() {
        String[] rowKeys = {"R1", "R2", "R3"};
        String[] columnKeys = {"C1", "C2"};
        double[][] data = new double[3][];
        data[0] = new double[] {1.1, 1.2};
        data[1] = new double[] {2.1, 2.2};
        data[2] = new double[] {3.1, 3.2};
        CategoryDataset dataset = DatasetUtilities.createCategoryDataset(
                rowKeys, columnKeys, data);
        assertTrue(dataset.getRowCount() == 3);
        assertTrue(dataset.getColumnCount() == 2);
    }
    '''
    JAVA_CODE = split_assignment_expression(JAVA_CODE)
    JAVA_CODE = split_variable_declaration(JAVA_CODE)
    get_statement(JAVA_CODE)
    split_assertion_code = split_assertion(JAVA_CODE)
    merge_assertion = merge_preorder(split_assertion_code)
    
    for code in merge_assertion:
        statement_list, process_statement_list = get_statement(code)
        variable_range_dict = get_delete_statement_list(code, statement_list)
    
    code_base = os.path.dirname(__file__)
    json_path = os.path.join(code_base, 'data', 'all_evosuite_tests.json')
    
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    tests = [line['function'] for line in data]
    
    statement_types = set()
    for test in tests:
        test = split_assignment_expression(test)
        test = split_variable_declaration(test)
    test_result = []
    
    test_number = {
        '0': 0,
        '1': 0,
        'more': 0
    }
    
    num, num2 = 0, 0
    for idx, test in enumerate(tests):
        test = split_assignment_expression(test)
        test = split_variable_declaration(test)
        split_assertion_code = split_assertion(test)
        merge_assertion = merge_preorder(split_assertion_code)
        method_name = get_method_name(test)
        for id, split_code in enumerate(merge_assertion):
            new_method_name = f'{method_name}_split_{id}'
            merge_assertion[id] = split_code.replace(method_name, new_method_name)
        data[idx]['splitted_test_function_contents'] = merge_assertion
        new_splitted_test_function = []
        for split_code in merge_assertion:
            statement_list, process_statement_list = get_statement(split_code)
            new_splited_code = get_delete_statement_list(split_code, statement_list)
            if remove_whitespace(split_code) == remove_whitespace(JAVA_CODE):
                a = 1
            new_splitted_test_function.append(new_splited_code)
            if remove_whitespace(split_code) != remove_whitespace(new_splited_code):
                num += 1
            else:
                num2 += 1
        data[idx]['splitted_test_function_contents'] = new_splitted_test_function
        
        if len(new_splitted_test_function) == 0:
            data[idx]['splitted_test_function_contents'] = [test]
            test_number['0'] += 1
        elif len(new_splitted_test_function) == 1:
            test_number['1'] += 1
        else:
            test_number['more'] += 1
        test_result.append({
            'function': test,
            'split_assertion_code': merge_assertion,
        })
    
    print(num, num2)
    print(test_number)
    result_json_path = os.path.join(code_base, 'data', 'all_splited_evosuite_tests.json')
    with open(result_json_path, 'w') as f:
        json.dump(data, f, indent=4)
    