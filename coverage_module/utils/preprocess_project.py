import os
from queue import Queue

import chardet

from core.base_file import File
from core.base_method import Method
from core.base_package import Package
from core.base_test_program import TestProgram
from data.Config import CONFIG
from utils._coverage_utils import analyze_method_signature_for_coverage, analyze_class_signature_for_coverage, update_coverage
from utils._data_preparation import load_focal_method, load_java_tests, load_focal_class
from utils._static_analysis_call_chaining import add_classes_and_methods_in_package, extract_called_functions, find_call_method, find_father_class, find_package_use_source_code, get_package_import
from utils._write_test_class import clear_test_class, save_test_class, write_test_class
from utils.test_excute_utils import write_test_class_and_execute

from data.Config import logger, CONFIG


def find_java_files(directory):
    '''在指定目录及其子目录中查找所有以 .java 结尾的文件，并返回这些文件的完整路径列表。'''
    java_files = []

    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".java"):
                java_files.append(os.path.join(root, file))

    return java_files

def get_packages(project_path, src_path):
    all_files = []
    all_packages_map = {}
    method_map = {} 
    class_map = {}
    
    #获取所有的类和方法
    all_package_path = os.path.join(project_path, src_path)
    java_files = find_java_files(all_package_path)
    for java_path in java_files:
        try:
            with open(java_path, 'rb') as file:
                raw_data = file.read()
            # 检测文件编码
            result = chardet.detect(raw_data)
            encoding = result['encoding']
            java_content = raw_data.decode(encoding)
        except UnicodeDecodeError as e:
            print(f"UnicodeDecodeError: {e}")
            continue
        except Exception as e:
            print(f"An error occurred: {e}")
            continue
        
        package_name = find_package_use_source_code(java_content)
        
        if not package_name:
            continue 
        
        single_package_path = package_name.replace('.', os.path.sep)
        single_package_path = os.path.join(all_package_path, single_package_path)
        
        if package_name not in all_packages_map:
            single_package = Package(package_name, single_package_path)
            all_packages_map[package_name] = single_package
            
        #获取包的对象
        single_package = all_packages_map[package_name]
        single_file = File(java_path, java_content, single_package)
        single_package.add_file(single_file)
        all_files.append(single_file)
        
        # 初步分析类和方法，没有处理调用关系
        add_classes_and_methods_in_package(single_package, java_content, single_file)

    all_packages = list(all_packages_map.values())
    
    #获取了每个文件的import，这一步放在这里是因为需要先分析所有的类里面的的方法，方便处理import *的情况
    for single_file in all_files:
        java_content = single_file.content
        get_package_import(single_file, java_content, all_packages)
        
        for classs in single_file.belong_package.classes:
            single_file.import_map[classs.name_no_package] = classs.name
        for classs in single_file.classes:    
            class_map[classs.name] = classs
            classs.import_map = single_file.import_map
            for method in classs.methods:
                method.import_map = classs.import_map
    
    #根据import更新参数列表和return type
    for single_file in all_files:
        for classs in single_file.classes:
            classs.belong_file = single_file
            for method in classs.methods:
                method.belong_file = single_file
                # 更新返回值类型
                if method.return_type in method.import_map:
                    method.return_type = method.import_map[method.return_type]
                if method.return_type in class_map:
                    method.return_class = class_map[method.return_type]
                
                # 更新参数列表
                new_parameters_list = []
                for parameter in method.parameters_list:
                    if parameter in method.import_map:
                        parameter = method.import_map[parameter]
                    new_parameters_list.append(parameter)
                method.parameters_list = new_parameters_list
                method.set_method_signature()
                
    #处理父子类
    for single_file in all_files:
        for classs in single_file.classes:
            find_father_class(classs.node, classs)
                
    for single_file in all_files:
        for classs in single_file.classes:
            if classs.father_class_name in class_map:
                father_class = class_map[classs.father_class_name]
                classs.father_class = father_class
                father_class.son_classes.add(classs)
    top_class = [classs for classs in class_map.values() if classs.father_class == None]
    class_queue = Queue()
    for item in top_class:
        class_queue.put(item)
    
    while not class_queue.empty():
        classs = class_queue.get()
        for son_class in classs.son_classes:
            class_queue.put(son_class)
            for method in classs.methods:
                #为了deepcopy
                son_class_name = son_class.name
                new_method_name = son_class_name + '.' + method.name_no_package
                
                new_method = Method(method.name_no_package, new_method_name, son_class.belong_package, son_class, method.parameters_list, method.content, method.return_type, method.node)
                
                new_method.import_map = method.import_map
                new_method.is_target = method.is_target
                new_method.set_method_signature()
                arguments_list = tuple(method.parameters_list)
                
                flag = True
                for son_method in son_class.methods:
                    if son_method.signature == new_method.signature:
                        flag = False
                if flag:
                    son_class.add_method(method)
                    method_map[(new_method_name, arguments_list)]= method
    
    all_packages = list(all_packages_map.values())  
    
    # 处理每一个method的行范围
    for single_package in all_packages:
        for method in single_package.methods:
            method_node = method.node
            for i in range(method_node.start_point[0], method_node.end_point[0] + 1):
                method.line_range.add(i + 1)
                method.line_number.add(str(i + 1))
            name = method.name
            arguments_list = tuple(method.parameters_list)
            method_map[(name, arguments_list)]= method
    
    # 处理每一个method的调用关系
    for single_package in all_packages: 
        find_call_method(single_package, method_map, class_map)
        package_name = single_package.name

    all_packages = list(all_packages_map.values()) 
    return all_packages, method_map, class_map

def find_all_chains(start_node, visited=None, path=None, depth=0, max_depth=10):
    if visited is None:
        visited = set()
    if path is None:
        path = [start_node]

    # Stop the recursion if the max depth is reached
    if depth > max_depth:
        return []
    
    # path = path + [start_node]
    visited.add(start_node)
    start_node.set_target()
    
    all_paths = []

    for next_node in start_node.called_methods:
        # print(f"{start_node.name} -> {next_node.name}")
        if next_node not in visited:
            new_paths = find_all_chains(next_node, visited | {next_node}, path + [next_node], depth + 1, max_depth)
            # tmp_path = path + [start_node]
            tmp_path = path + [next_node]
            next_node.add_callee_chain(tmp_path)
            all_paths.extend(new_paths)
        else:
            # Detect cycle - stop the path here to avoid infinite loop
            cycle_index = path.index(next_node)
            # tmp_path = path + [start_node]
            tmp_path = path[:cycle_index] + [next_node]
            next_node.add_callee_chain(tmp_path)
            all_paths.append(path)
    
    # 如果 start_node.called_methods 是空的，添加当前路径
    if not start_node.called_methods:
        all_paths.append(path)
        
    return all_paths

def setup_single_package(all_methods_in_package, method_map, class_map):
    for single_method in all_methods_in_package:
        for name_and_arguments_list in single_method.called_method_name:
            called_methods = []
            if name_and_arguments_list in method_map:
                called_methods = [method_map[name_and_arguments_list]]
            # 粗粒度 已经实现对于名字相同的方法，通过参数列表长度锁定
            else:
                called_class_name = '.'.join(name_and_arguments_list[0].split('.')[:-1])
                called_class = class_map.get(called_class_name)
                if called_class is None:
                    continue
                method_name = name_and_arguments_list[0]
                arguments_list = list(name_and_arguments_list[1])
                arguments_list_len = len(arguments_list)
                called_methods = []
                for maybe_method in called_class.methods:
                    if method_name == maybe_method.name and arguments_list_len == len(maybe_method.parameters_list):
                        called_methods.append(maybe_method)
                    
            for called_method in called_methods:
                single_method.add_called_method(called_method)
                called_method.add_callee_method(single_method)
                called_class_name = '.'.join(name_and_arguments_list[0].split('.')[:-1])
                called_class = class_map.get(called_class_name)
                single_method.add_called_method_and_class(single_method, called_class)
                        

        for name_and_arguments_list in single_method.branch_related_called_methods_name:
            branch_related_called_method = None
            if name_and_arguments_list in method_map:
                branch_related_called_method = method_map[name_and_arguments_list]
                
            if branch_related_called_method is not None:
                single_method.add_branch_related_called_method(branch_related_called_method)
                branch_related_called_class_name = '.'.join(name_and_arguments_list[0].split('.')[:-1])
                branch_related_called_class = class_map.get(branch_related_called_class_name)
                single_method.add_branch_related_called_methods_and_class(branch_related_called_method, branch_related_called_class)

    for single_method in all_methods_in_package:
        paths_from_single_func = find_all_chains(single_method)
        for i in paths_from_single_func:
            if len(i[1:]) != 0:
                single_method.add_called_chain(i[1:])
    pass


def setup_existing_cases(all_methods_in_package, project_name, all_packages, method_map, class_map, debugging_mode=False):
    # projcet路径如下
    project_root = CONFIG['path_mappings'][project_name]['loc']
    test_root_dir = CONFIG['path_mappings'][project_name]['test']
    src_root_dir = CONFIG['path_mappings'][project_name]['src']
    existing_cases_in_module = load_java_tests(project_root, test_root_dir)
    
    if debugging_mode:
        existing_cases_in_module = [i for i in existing_cases_in_module if 'org.llm' in i['test_class_sig']]
    # test_packages = ['org.jfree.chart.text.format', 'org.jfree.chart.legend', 'org.llm', 'org.jfree.data.category', 'org.jfree.data.function']
    # test_packages = ['org.llm']
    # existing_cases_in_module = [i for i in existing_cases_in_module if '.'.join(i['test_class_sig'].split('.')[:-1]) in test_packages]

    for index, test_info in enumerate(existing_cases_in_module):
        try:
            (project_root, test_root_dir, test_class_sig, test_content) = (test_info['project_root'], test_info['test_root_dir'], test_info['test_class_sig'], test_info['test_class'])
            
            coverage_data = None
            result = write_test_class_and_execute(project_root, test_root_dir, test_class_sig, test_content, 'clean test', True)
            coverage_data = result['coverage']
            
            if coverage_data is None:
                logger.debug(f"Failed to execute test case {test_class_sig}")
                continue
            else:
                logger.debug(f"Successfully executed test case {test_class_sig}")

            new_test_case = TestProgram(content=test_content, target_function=None, coverage=coverage_data)
            case_called_functions = extract_called_functions(test_content, all_packages, method_map, class_map)
            
            update_coverage(all_methods_in_package, method_map, class_map, new_test_case, case_called_functions)
        except Exception as e:
            print('异常提示:', e)  # 输出异常信息
            continue 


def setup_all_packages(project_name, all_packages, method_map, class_map, debugging_mode):
    all_methods_in_package = set()
    for i in range(len(all_packages)):
        single_package = all_packages[i]
        # 拿到当前module里所有的函数    
        all_methods_in_package = single_package.methods | all_methods_in_package
    logger.debug(f"Begin extracting context for {project_name}")
    setup_single_package(all_methods_in_package, method_map, class_map)
    logger.debug(f"Finish extracting context for {project_name}")
    
    logger.debug(f"Begin processing existing cases for {project_name}")
    setup_existing_cases(all_methods_in_package, project_name, all_packages, method_map, class_map, debugging_mode)
    logger.debug(f"Finish processing existing cases for {project_name}")


def analyze_project(project_name, debugging_mode=False):
    all_packages, method_map, class_map = get_packages(CONFIG['path_mappings'][project_name]['loc'], CONFIG['path_mappings'][project_name]['src'])
    setup_all_packages(project_name, all_packages, method_map, class_map, debugging_mode)
    return all_packages, method_map, class_map


def get_callable_methods(project_name, single_package, collect_type):
    callable_methods = []
    all_methods_in_package = single_package.methods
    
    if collect_type == 'method':
        focal_method_sigs = load_focal_method(project_name, single_package.name)
        for method in all_methods_in_package:
            (_, _, class_name, _, method_name, parameter_tuple) = analyze_method_signature_for_coverage(method.signature)
            for focal_method, method_head in focal_method_sigs:
                (_, _, f_class_name, _, f_method_name, f_parameter_tuple) = analyze_method_signature_for_coverage(focal_method)
                if class_name == f_class_name and method_name == f_method_name and len(parameter_tuple) == len(f_parameter_tuple):
                    if method_head != "":
                        method.test_head = method_head + '\n    @Test\n    public void testEmpty(){\n        assertTrue(True);\n    }\n}'
                    callable_methods.append(method)
    elif collect_type == 'class':
        focal_class_sigs = load_focal_class(project_name, single_package.name)
        for method in all_methods_in_package:
            (_, _, class_name, _, method_name, parameter_tuple) = analyze_method_signature_for_coverage(method.signature)
            for focal_class, class_head in focal_class_sigs:
                (_, _, f_class_name, _) = analyze_class_signature_for_coverage(focal_class)
                if class_name == f_class_name:
                    if class_head != "":
                        method.test_head = method_head + '\n    @Test\n    public void testEmpty(){\n        assertTrue(True);\n    }\n}'
                    callable_methods.append(method)
        
    else:
        callable_methods = [i for i in all_methods_in_package if i.is_target == True]
        # callable_methods = [i for i in all_methods_in_package if i.is_target == True and 0 < len(i.covered_lines) < len(i.line_range)]
        # if len(callable_methods) > 5:
        #     callable_methods = callable_methods[0 : 5]
        #     logger.info(f'Only run 5 focal methods.')
    
    callable_methods = [ii for ii in callable_methods if len(ii.covered_lines) < len(ii.line_range)]
    callable_methods = list(set(callable_methods))
    return callable_methods

def delete_existing_case_and_save(project_name, tmp_test_dir_path):
    """
    Deletes existing test cases in a Java project module and saves the changes.
    Args:
        project_name (str): The name of the Java project.
        tmp_test_dir_path (str): The path to the temporary test directory.
    Returns:
        None
    """
    project_root = CONFIG['path_mappings'][project_name]['loc']
    test_root_dir = CONFIG['path_mappings'][project_name]['test']
    existing_cases_in_module = load_java_tests(project_root, test_root_dir)
    
    for test_info in existing_cases_in_module:
        (project_root, test_root_dir, focal_method_sig, test_class_sig, test_content) = (test_info['project_root'], test_info['test_root_dir'], '', test_info['test_class_sig'], test_info['test_class'])
        delete_test_class_and_save(project_root, test_root_dir, test_class_sig, test_content, tmp_test_dir_path, project_name)

def recovery_existing_case(project_name, tmp_test_dir_path):
    """
    Recovers existing test cases in a Java project.
    Args:
        project_name (str): The name of the project.
        tmp_test_dir_path (str): The path to the temporary test directory.
    Returns:
        None
    """
    project_root = CONFIG['path_mappings'][project_name]['loc']
    test_root_dir = CONFIG['path_mappings'][project_name]['test']
    existing_cases_in_module = load_java_tests(tmp_test_dir_path, project_name)
    
    for test_info in existing_cases_in_module:
        (_, _, _, test_class_sig, test_content) = (test_info['project_root'], test_info['test_root_dir'], '', test_info['test_class_sig'], test_info['test_class'])
        recovery_test_class(project_root, test_root_dir, test_class_sig, test_content)

def delete_test_class_and_save(project_root, test_root_dir, test_class_sig, test_content, tmp_test_dir_path, project_name):
    save_project_path = os.path.join(tmp_test_dir_path, project_name)
    '''保存一下现有的测试程序到临时路径'''
    save_test_class(test_class_sig, test_content, save_project_path)
    '''删除测试类'''
    clear_test_class(project_root, test_root_dir, test_class_sig)

def recovery_test_class(project_root, test_root_dir, test_class_sig, test_content):
    write_test_class(project_root, test_root_dir, test_class_sig, test_content)