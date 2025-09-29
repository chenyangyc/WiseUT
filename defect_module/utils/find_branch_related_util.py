import ast
from collections import deque
from core.ast_objs import ConditionVisitor, CompleteAssignmentVisitor
from core.base_branch import Branch

'''
part1:
目标：使用ast处理python文本，得到所有的条件语句中的函数和变量
实现过程：
1.遍历整个代码的ast，提取出其中的条件语句，接下来只对这部分进行提取
2.仔细找到条件语句内容中的所有函数调用，包括本模块直接调用，调用其他类其他模块的函数，将所有的函数名存储下来
3.仔细找到条件语句内容中所有的变量，注意函数名不是变量，找到的变量包括直接使用，也包括在函数的参数列表中的，将所有的参数都存储下来
'''

def report_conditions(functions, variables, branches):
    functions_set = set(functions)
    variables_set = set(variables - {f[1] for f in functions if f[0] is None})
    branches_set = branches
    return functions_set, variables_set, branches_set

def analyze_conditions(code):
    tree = ast.parse(code)
    visitor = ConditionVisitor()
    visitor.visit(tree)
    return report_conditions(visitor.functions, visitor.variables, visitor.branches)

'''
part2:
目标：使用ast处理python文本，得到所有的变量的赋值语句，得到每一个变量有关的其他变量和函数，将结果存储到字典中
实现过程：
1.遍历整个代码的ast，提取出其中的变量赋值语句，接下来只对这部分进行提取
2.提取赋值语句的左边，这是作为变量来处理，接下来右边的处理结果都存储到这个变量里面，注意处理连等的情况
3.处理赋值语句的等号右边，提取中其中所有的函数调用和变量，注意函数名不是变量，找到的变量包括直接使用，也包括在函数的参数列表中的，将所有的函数和参数都存储下来，这些作为和等号左边变量有关的函数和变量
'''
                
def report_code_with_all_variables(all_variables, dependencies):
    # 确保所有变量都在字典中
    for var in all_variables:
        if var not in dependencies:
            dependencies[var] = {'function': [], 'identifier': []}
    return dependencies

def analyze_code_with_all_variables(code):
    tree = ast.parse(code)
    visitor = CompleteAssignmentVisitor()
    visitor.visit(tree)
    return report_code_with_all_variables(visitor.all_variables, visitor.dependencies)


'''
part3:
目标：在上一步的基础上，现在已经得到所有变量的和与其有关的变量和函数，现在要把每一个变量有关的其他变量的函数都加进该变量的函数列表里，使用拓扑排序的方法进行处理。
实现过程：
目前已经有上一步得到的字典dependencies
1.拓扑排序排序的变量选择和这个变量有关的变量的数量
2.将选择的变量的有关函数，加入所有包含该变量为有关变量的变量的函数列表中
3.在最后得到所有变量有关的所有函数
'''


def topological_sort(dependencies):
    # 构建图和入度表
    graph = {var: set(dep['identifier']) for var, dep in dependencies.items()}
    in_degree = {var: 0 for var in graph}
    for var in graph:
        for dep_var in graph[var]:
            in_degree[dep_var] += 1

    # 使用队列进行拓扑排序
    queue = deque([var for var in in_degree if in_degree[var] == 0])
    sorted_vars = []

    while queue:
        var = queue.popleft()
        sorted_vars.append(var)
        for dep_var in graph[var]:
            in_degree[dep_var] -= 1
            if in_degree[dep_var] == 0:
                queue.append(dep_var)

    # if len(sorted_vars) != len(graph):
    #     raise ValueError("存在循环依赖，无法完成拓扑排序")

    other_vars = list(dependencies.keys() - set(sorted_vars))
    return sorted_vars, other_vars

def update_functions(dependencies):
    sorted_vars, other_vars = topological_sort(dependencies)
    for var in reversed(sorted_vars):  # 逆序处理，确保从最底层的依赖开始更新
        related_vars = dependencies[var]['identifier']
        for related_var in related_vars:
            dependencies[var]['function'] += dependencies[related_var]['function']
        dependencies[var]['function'] = list(set(dependencies[var]['function']))  # 去重
    
    vlist = []
    for var in other_vars:
        vlist += dependencies[var]['function']
        vlist = list(set(vlist))
    for var in other_vars:
        dependencies[var]['function'] = vlist
        
# all start

# def start_analysis(code):
#     dependencies = analyze_code_with_all_variables(code)
#     update_functions(dependencies)
#     functions_set, variables_set = analyze_conditions(code)
#     for name in variables_set:
#         if name not in dependencies.keys():
#             continue
#         function_list = dependencies[name]['function']
#         for funtion in function_list:
#             functions_set.add(funtion)
#     return functions_set