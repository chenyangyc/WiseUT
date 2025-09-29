import os
import re
import json
import subprocess
from collections import defaultdict
from utils.file_parse import extract_module
from data.configurations import code_base


def generate_cg_for_triggering_test(proj_dir, proj_name, bug_id, absolute_test_files):
    # python3 tool/Jarvis/jarvis_cli.py /data/yangchen/llm_teut/data/bugsinpy/checkout_projects/ansible/1/buggy/lib/ansible/galaxy/collection.py --package /data/yangchen/llm_teut/data/bugsinpy/checkout_projects/ansible/1/buggy -o example_ooo.json
    
    jarvis_dir = f'{code_base}/assistant_tools/Jarvis'
    jarvis_tool = 'tool/Jarvis/jarvis_cli.py'
    
    module_paths = ' '.join(absolute_test_files)
    
    output_file = f'{code_base}/data/triggering_test_cgs/{proj_name}_{bug_id}.json'
    
    generate_cmd = f'conda run -n llm python3 {jarvis_tool} {module_paths} --package {proj_dir} -o {output_file}'
    
    try:
        subprocess.run([generate_cmd], cwd=jarvis_dir, check=True, shell=True)
    except subprocess.CalledProcessError as e:
        raise e
    
    with open(output_file, 'r') as f:
        cg = json.load(f)
        
    return cg


def extract_method_chain_from_test_output(output, test_cmd, focal_dir):
    if 'pytest' in test_cmd:
        pattern = r".*?([\w./-]+):(\d+):.*"
        test_func_name = test_cmd.strip().split('::')[-1]
        # test_path = test_cmd.strip().split(' ')[-1].split('::')[0]
        # test_file_name = test_cmd.strip().split(' ')[-1].split('::')[0]
        split_format = f'{test_func_name}'
    elif 'unittest' in test_cmd:
        pattern = r'File "(.*)", line (\d+), in'
        test_func_name = test_cmd.strip().split('.')[-1]
        # test_path = test_cmd.strip().split(' ')[-1].split('.')[]
        split_format = f'ERROR: {test_func_name}'
        
    # split_format = test_func_name
    # if 'pytest' in test_cmd:
    #     split_format = '______________________________ test'
    # elif 'unittest' in test_cmd:
    #     split_format = '______________________________ test'

    # truncate till '------ Captured'
    if '------ Captured' in output:
        output = output.split('------ Captured')[0]
    
    if 'warnings summary' in output:
        output = output.split('warnings summary')[0]
        
    # matches = re.findall(pattern, output)
    
    splited_test_ouput = output.split(split_format)
    
    all_methods = []
    for single_output in splited_test_ouput:
        matches = re.findall(pattern, single_output)
        single_methods = []
        
        flag = False
        for single_match in matches:
            file_path = single_match[0]
            line_no = single_match[1]
            
            if '.py' not in file_path:
                continue
            
            if 'pytest' in test_cmd:
                file_path = os.path.join(focal_dir, file_path)
            
            if flag == False and 'test' not in file_path:
                continue
            else:
                flag = True
                
            # if (file_path, line_no) not in single_methods:
            if not single_methods:
                single_methods.append((file_path, line_no))
            elif (file_path, line_no) != single_methods[-1]:
                single_methods.append((file_path, line_no))
    
        if single_methods and single_methods not in all_methods:
            all_methods.append(single_methods)

    return all_methods


def extract_patched_methods(proj_name, bug_id, bug_info):
    code_files = bug_info['code_files']
    buggy_proj_dir = os.path.join(bugs_in_py_checkout_proj_dir, proj_name, bug_id, 'focal')
    
    buggy_methods = set()
    for code_file in code_files:
        absolute_code_file = os.path.join(buggy_proj_dir, code_file)
        
        buggy_lines = bug_info['buglines'][code_file]

        for line in buggy_lines:
            buggy_methods.add((absolute_code_file, line))
    return list(buggy_methods)


def extract_method_from_file_and_line(file_and_lines):
    final_methods = []
    for single_chain in file_and_lines:
        single_final_methods = []
        for file_and_line in single_chain:
            file_path = file_and_line[0]
            line_no = file_and_line[1]
            try:
                single_module, all_classes, all_methods = extract_module(file_path)

                line2method = defaultdict()
                for single_method in all_methods:
                    for line in single_method.line_range:
                        line2method[line] = single_method

                # if int(line_no) in line2method and (file_path, line2method[int(line_no)]) not in single_final_methods:
                # if int(line_no) in line2method:
                #     single_final_methods.append((file_path, line2method[int(line_no)]))
                
                if int(line_no) in line2method:
                    if not single_final_methods:
                        single_final_methods.append((file_path, line2method[int(line_no)]))
                    elif (file_path, line2method[int(line_no)]) != single_final_methods[-1]:
                        single_final_methods.append((file_path, line2method[int(line_no)]))
    
            except:
                # print(f'Extract method from file and line error: {file_path}')
                continue
        if single_final_methods:
            final_methods.append(single_final_methods)
    return final_methods