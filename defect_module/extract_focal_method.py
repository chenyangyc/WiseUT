import json
import os
import pickle
import subprocess
from collections import defaultdict
from tree_sitter import Language, Parser
import tree_sitter_python as ts_python
from pathlib import Path
from tqdm import tqdm
from data.configurations import code_base, project_configs, logger
from utils.file_parse import extract_module

PYTHON_LANGUAGE = Language(ts_python.language())
parser = Parser()
parser.language = PYTHON_LANGUAGE

CALL_QUERY = PYTHON_LANGUAGE.query('(call)@call')
PARAMETERS_QUERY = PYTHON_LANGUAGE.query('(function_definition(parameters)@parameters)')


def get_function_parameter(function_content):
    root_node = parser.parse(bytes(function_content, 'utf8')).root_node
    function_parameter_nodes = PARAMETERS_QUERY.captures(root_node)
    
    if len(function_parameter_nodes.get('parameters', [])) == 0:
        raise ValueError("No function parameters found in the provided content.")
    
    parameter_content = function_parameter_nodes.get('parameters')[0].text.decode()
    return parameter_content


def splite_call_function(caller_function_content, called_function_name):
    root_node = parser.parse(bytes(caller_function_content, 'utf8')).root_node
    function_call_nodes = CALL_QUERY.captures(root_node)
    
    called_function_node = None
    for call_node in function_call_nodes.get('call', []):
        function = call_node.child_by_field_name('function')
        if function.type == 'identifier':
            function_name = function.text.decode()
            # function_obj = None
        elif function.type == 'attribute':
            # function_obj = function.child_by_field_name('object').text.decode()
            function_name = function.child_by_field_name('attribute').text.decode()
        else:
            continue
        if function_name == called_function_name:
            called_function_node = call_node
            break
    if called_function_node:
        end_byte = called_function_node.end_byte
        split_function = caller_function_content.encode()[:end_byte].decode() + '\n'
        arguments = called_function_node.child_by_field_name('arguments').text.decode()
        return {
            'result': 'success',
            'split_function': split_function,
            'called_arguments': arguments,
        }
    # if not called_function_name.startswith('__'):
    #     logger.error(f"Cannot find the called function {called_function_name} in the caller function content.")
    return {
        'result': 'failure',
        'split_function': caller_function_content,
        'called_arguments': '()',
    }



def find_all_chains(function_dict, start_node, visited=None, path=None, depth=0, max_depth=10):
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

    for next_node in start_node.called_functions:
        # print(f"{start_node.name} -> {next_node.name}")
        if next_node not in visited:
            new_paths = find_all_chains(function_dict, function_dict[next_node], visited | {next_node}, path + [next_node], depth + 1, max_depth)
            tmp_path = path + [next_node]
            function_dict[next_node].add_callee_chain(tmp_path)
            all_paths.extend(new_paths)
        else:
            # Detect cycle - stop the path here to avoid infinite loop
            cycle_index = path.index(next_node)
            tmp_path = path[:cycle_index] + [next_node]
            function_dict[next_node].add_callee_chain(tmp_path)
            all_paths.append(path)
    
    # 如果 start_node.called_functions 是空的，添加当前路径
    if not start_node.called_functions:
        all_paths.append(path)
    return all_paths


def parser_project(src_path: str, base_module_name: str):
    """
    Parse the project to extract modules, classes, and functions.
    """
    src_path = Path(src_path)
    module_paths = list(src_path.rglob("*.py"))
    # module_paths = [module_path for module_path in module_paths if 'test' not in module_path.as_posix() and 'tests' not in module_path.as_posix()]
    modules = []
    function_dict = {}
    for file_path, module_name in tqdm(
        [(module_path, module_path.relative_to(src_path).as_posix().replace('.py', '').replace(os.sep, '.')) for module_path in module_paths],
        desc="Parsing modules",
        total=len(module_paths),
    ):
        # single_module, all_classes, all_methods = extract_module(file_path, f'{base_module_name}{module_name}')
        single_module, all_classes, all_methods = extract_module(file_path, f'{module_name}')
        modules.append(single_module)
        for single_method in all_methods:
            single_method.fully_qualified_name = f'{single_method.belong_module.name}.{single_method.belong_class.name}.{single_method.name}' if single_method.belong_class else f'{single_method.belong_module.name}.{single_method.name}'
            fully_qualified_name = single_method.fully_qualified_name
            if fully_qualified_name not in function_dict:
                function_dict[fully_qualified_name] = single_method
            # else:
            #     logger.warning(f"Duplicate function name found: {fully_qualified_name}. Skipping.")
    logger.info(f"Parsed {len(modules)} modules and {len(function_dict)} functions.")
    return modules, function_dict


def extract_call_chains(modules, function_dict, project_path, output_file):
    """
    Extract call chains from the modules and functions.
    """
    logger.info("Extracting call chains...")
    
    # n = 258  # 总步数
    # duration = 10  # 总耗时（秒）
    # step_time = duration / n
    # import time
    # for _ in tqdm(range(n)):
    #     time.sleep(step_time)  # 每一步 sleep 一点，保证总时长 = 5s
    for single_module in tqdm(modules, desc="Extracting call chains", total=len(modules)):
        module_path = single_module.module_path
        javis_cmd = ['conda', 'run', '-n', 'llm', 'python', f'{code_base}/assistant_tools/Jarvis/tool/Jarvis/jarvis_cli.py', module_path, '--package', project_path, '--output', output_file]
        try:
            subprocess.run(javis_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError as e:
            # logger.error(f"Error running Jarvis for {module_path}: {e}")
            continue
        # logger.info(f"Jarvis output for {module_path} saved to {output_file}")
        
        with open(output_file, 'r') as f:
            jarvis_output = json.load(f)
        
        for function_name, call_chain in jarvis_output.items():
            if function_name in function_dict:
                function = function_dict[function_name]
                for called_function in call_chain:
                    if called_function in function_dict:
                        function.add_called_function(function_dict[called_function].fully_qualified_name)
                        function_dict[called_function].add_callee_function(function.fully_qualified_name)
    
    function_called_list = [function.called_functions for function in function_dict.values()]
    for single_function in function_dict.values():
        paths_from_single_func = find_all_chains(function_dict, single_function)
        for i in paths_from_single_func:
            if len(i[1:]) != 0:
                single_function.add_called_chain(i[1:])
    
    function_called_chain_list = [function.called_chains for function in function_dict.values()]
    logger.info("Extracted call chains.")
    

def analyze_all_call_chains(function_dict):
    """
    Analyze all call chains in the function dictionary.
    """
    all_called_chains = []
    for function in function_dict.values():
        # 链条是最开头的函数
        if not function.callee_functions and function.called_chains:
            min_chain = {}
            for single_called_chain in function.called_chains:
                single_chain = []
                # 找到最短的一条
                if (single_called_chain[0], single_called_chain[-1]) in min_chain and len(single_called_chain) >= len(min_chain[(single_called_chain[0], single_called_chain[-1])]):
                    continue
                for function_name in single_called_chain:
                    single_function = function_dict[function_name]
                    single_chain.append({
                        'function_name': single_function.name,
                        'function_content': single_function.content,
                        'function_parameter': get_function_parameter(single_function.content),
                        'belong_class_content': single_function.belong_class.content if single_function.belong_class else None,
                        'belong_class_name': single_function.belong_class.name if single_function.belong_class else None,
                        'belong_class_init': '\n'.join(single_function.belong_class.init) if single_function.belong_class else None,
                    })
                min_chain[(single_called_chain[0], single_called_chain[-1])] = single_chain
            all_called_chains.extend(list(min_chain.values()))
    
    # slicing the call chain
    for call_chain in all_called_chains:
        for i in range(len(call_chain) - 1, 0, -1):
            called_function_name = call_chain[i]['function_name']
            caller_function_content = call_chain[i - 1]['function_content']
            split_result = splite_call_function(caller_function_content, called_function_name)
            call_chain[i - 1]['called_function_name'] = called_function_name
            call_chain[i - 1]['called_function_content'] = split_result['split_function']
            call_chain[i - 1]['called_arguments'] = split_result['called_arguments']
            call_chain[i - 1]['called_function_parameter'] = call_chain[i]['function_parameter']
            call_chain[i - 1]['split_result'] = split_result['result']
    return all_called_chains


def type_error_extract_focal_method_entry():
    base_res_dir = f'{code_base}/data/new_proj_res'
    os.makedirs(base_res_dir, exist_ok=True)
        
    for project_name, config in project_configs.items():
        src_path = config['src_path']
        base_module_name = config['base_module_name']
        project_path = config['project_path']

        project_res_dir = f'{base_res_dir}/{project_name}'
        
        os.makedirs(project_res_dir, exist_ok=True)
        logger.info(f"Parsing project {project_name} at {project_path}")
        jarvis_output_file = f'{project_res_dir}/jarvis_output.json'
        
        src_path = os.path.join(project_path, src_path)
        modules, function_dict = parser_project(project_path, base_module_name)
        extract_call_chains(modules, function_dict, project_path, jarvis_output_file)
        
        logger.info(f"Processing the extracted call graph...")
        all_called_chains = analyze_all_call_chains(function_dict)
        
        pkl_save_path = Path(f'{project_res_dir}/modules.pkl')
        # pkl_save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(pkl_save_path, 'wb') as f:
            pickle.dump(modules, f)
        
        function_dict_save_path = Path(f'{project_res_dir}/function_dict.pkl')
        with open(function_dict_save_path, 'wb') as f:
            pickle.dump(function_dict, f)
        
        all_called_chains_save_path = Path(f'{project_res_dir}/called_chains.pkl')
        with open(all_called_chains_save_path, 'wb') as f:
            pickle.dump(all_called_chains, f)
        
        logger.info(f"Finished processing project {project_name}.")
        

if __name__ == "__main__":
    base_res_dir = f'{code_base}/data/new_proj_res'
    os.makedirs(base_res_dir, exist_ok=True)
        
    for project_name, config in project_configs.items():
        src_path = config['src_path']
        base_module_name = config['base_module_name']
        project_path = config['project_path']

        project_res_dir = f'{base_res_dir}/{project_name}'
        
        os.makedirs(project_res_dir, exist_ok=True)
        logger.info(f"Parsing project {project_name} at {project_path}")
        jarvis_output_file = f'{project_res_dir}/jarvis_output.json'
        
        src_path = os.path.join(project_path, src_path)
        modules, function_dict = parser_project(project_path, base_module_name)
        extract_call_chains(modules, function_dict, project_path, jarvis_output_file)
        
        logger.info(f"Processing the extracted call graph...")
        all_called_chains = analyze_all_call_chains(function_dict)
        
        pkl_save_path = Path(f'{project_res_dir}/modules.pkl')
        # pkl_save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(pkl_save_path, 'wb') as f:
            pickle.dump(modules, f)
        
        function_dict_save_path = Path(f'{project_res_dir}/function_dict.pkl')
        with open(function_dict_save_path, 'wb') as f:
            pickle.dump(function_dict, f)
        
        all_called_chains_save_path = Path(f'{project_res_dir}/called_chains.pkl')
        with open(all_called_chains_save_path, 'wb') as f:
            pickle.dump(all_called_chains, f)
        
        logger.info(f"Finished analysis for project {project_name}.")
        
        # project_path = '{code_base}/data/bugsinpy/checkout_projects/fastapi/7/focal'
        # src_path = '{code_base}/data/bugsinpy/checkout_projects/fastapi/7/focal/fastapi'
        # base_module_name = 'fastapi.'
        # project_name = 'fastapi_7'
        # modules, function_dict = parser_project(src_path, project_name, base_module_name)
        # extract_call_chains(modules, function_dict, project_path)
        # logger.info("Finished extracting call chains.")
        