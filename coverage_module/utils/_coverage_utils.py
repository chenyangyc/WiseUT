import re

def remove_content_in_parentheses(text):
    """
    去除括号内的内容

    Args:
        text (_type_): 原始的字符串

    Returns:
        str: 去除括号之后的内容
    """
    # This regex pattern finds a pair of parentheses and anything in between.
    pattern = r"\(.*?\)"

    # The re.sub function replaces the pattern with an empty string.
    new_text = re.sub(pattern, "", text)

    return new_text


def analyze_method_signature_for_coverage(method_signature):
    """
    根据待测函数签名，分析收集覆盖率时需要的一些信息，例如类名，包名，函数名，以及变量列表
    Args:
        method_signature: 函数签名

    Returns:
        package_name: 包名
        package_dir: 包名对应的jacoco路径
        class_name: 类名
        class_dir: 类名对应的jacoco路径
        method_name: 函数名
        parameter_tuple: 参数列表
    """
    parameters = re.findall(r"\(.*?\)", method_signature)[0][1:-1]
    parameter_list = [i for i in parameters.split(",") if i != ""]
    tmp_list = []
    for i in parameter_list:
        if "#" in i:
            i = i.replace("#", ".")
        tmp_list.append(i.strip().lower())

    parameter_tuple = tuple(tmp_list)
    package_name = method_signature.split("#")[0]
    class_name = ".".join(method_signature.split("#")[:2])

    ## 测试覆盖率需要的条件
    package_dir = package_name.replace(".", "/")
    clazz_dir = class_name.replace(".", "/")
    method_name = remove_content_in_parentheses(
        "".join(method_signature.split("#")[2:])
    )
    return (
        package_name,
        package_dir,
        class_name,
        clazz_dir,
        method_name,
        parameter_tuple,
    )
    
def analyze_class_signature_for_coverage(class_signature):
    package_name = class_signature.split("#")[0]
    class_name = ".".join(class_signature.split("#")[:2])

    ## 测试覆盖率需要的条件
    package_dir = package_name.replace(".", "/")
    clazz_dir = class_name.replace(".", "/")
    return (
        package_name,
        package_dir,
        class_name,
        clazz_dir,
    )

def get_coverage_data(coverage_data, package_name, sourcefile_name):
    '''从覆盖率数据中提取特定包和源文件的覆盖率信息'''
    covered_all = coverage_data.get(package_name)
    if not covered_all:
        return None
    covered_all = covered_all.get(sourcefile_name)
    if not covered_all:
        return None
    if 'line' in covered_all.keys():    
        covered_all = covered_all.get('line')
    return covered_all

def really_called(method, test_case):
    """
    Check if a method has been called by a specific test case.
    Args:
        method (Method): The method to check.
        test_case (TestCase): The test case to check against.
    Returns:
        bool: True if the method has been called by the test case, False otherwise.
    """
    # code implementation here
    coverage = test_case.coverage
    if method.belong_package:
        package_name = method.belong_package.name
    else:
        return False
    if method.belong_file:
        sourcefile_name = method.belong_file.file_name
    else:
        return False
    
    covered_all = coverage.get(package_name)
    if not covered_all:
        return False
    covered_all = covered_all.get(sourcefile_name)
    if not covered_all:
        return False
    if 'line' in covered_all.keys():
        covered_all = covered_all.get('line')
    covered_by_case = covered_all.get('coverage_line')
    if covered_by_case is None:
        return False

    executed_lines = set(covered_by_case)
    line_range = set(method.line_range)
    function_executed_lines = executed_lines.intersection(line_range)
    if len(function_executed_lines) > 0:
        return True
    pass

def update_coverage(all_methods_in_package, method_map, class_map, new_test_case, case_called_functions, is_llm=False):
    """
    Updates the coverage information based on the new test case and called functions.
    Args:
        all_methods_in_package (list): List of all methods in the package.
        method_map (dict): Dictionary mapping function names to their corresponding functions.
        class_map (dict): Dictionary mapping class names to their corresponding classes.
        new_test_case (TestCase): The new test case object.
        case_called_functions (list): List of called functions in the test case.
        is_llm (bool, optional): Flag indicating whether the test case is for low-level module (LLM). Defaults to False.
    """
    # Implementation details...
    for func in case_called_functions:
        # 如果存在的话，在当前module的function dict里找对应的函数
        called_function = method_map.get(func)              
        # 如果不存在，就在class里找
        if called_function is None:
            called_functions = []
            called_class_name = '.'.join(func[0].split('.')[:-1])
            called_class = class_map.get(called_class_name)
            if called_class is None:
                continue
            method_name = func[0]
            arguments_list = list(func[1])
            arguments_list_len = len(arguments_list)
            for maybe_method in called_class.methods:
                if method_name == maybe_method.name and arguments_list_len == len(maybe_method.parameters_list):
                    called_functions.append(maybe_method)
        else:
            called_functions = [called_function]
                # 如果找到了,先判断是不是覆盖了，再加入called function
        for called_function in called_functions:
            if really_called(called_function, new_test_case):
                new_test_case.add_called_function(called_function)
                called_function.add_direct_program(new_test_case)
                called_class_name = '.'.join(func[0].split('.')[:-1])
                called_class = class_map.get(called_class_name)
                new_test_case.add_called_method_and_class(called_function, called_class)
            
    for single_target in all_methods_in_package:
        package_name = single_target.get_package_name()
        sourcefile_name = single_target.belong_file.file_name
                
        covered_all = get_coverage_data(new_test_case.coverage, package_name, sourcefile_name)
        if covered_all is None:
            continue
                
        covered_by_case = covered_all.get('coverage_line')
        if covered_by_case is None:
            continue
        total_line = covered_all.get('total_line')
        single_target.line_range = list(set(single_target.line_range).intersection(set(total_line)))
        covered_by_case_in_target = set(covered_by_case).intersection(set(single_target.line_range))
        if len(covered_by_case_in_target) > 0: 
            single_target.add_covered_tests(new_test_case)
            new_test_case.add_covered_function(single_target)
            single_target.add_covered_lines(covered_by_case_in_target)
            if is_llm:
                single_target.add_covered_by_llm(covered_by_case_in_target)