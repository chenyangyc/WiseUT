import json
import os
import time
from data.Config import CONFIG
from utils._data_preparation import load_focal_method, load_packages
from utils._run_mvn_test import run_mvn_test
from utils._write_test_class import clear_test_class, write_test_class
from utils._coverage_utils import analyze_method_signature_for_coverage
from utils._analyze_jacoco_output import parse_coverage_xml


# 读取jsonl里面的内容
def read_jsonl(file_path):
    data_list = []
    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            data_list.append(json.loads(line))
    return data_list

def get_all_test_use_json(project_data):
    all_uts = []
    cnt = 1
    for data in project_data:
        if data["compiled"]:
            class_name = data['test_class_sig'].split('.')[-1]
            new_class_name = class_name[0].upper() + class_name[1:]
            all_uts.append({
                'generated_test': data['generated_test'].replace(class_name, new_class_name),
                'test_class_sig': data['test_class_sig'].replace(class_name, new_class_name),
            })
            cnt += 1
    return all_uts

def setup_single_project(date, project_name):
    jsonl_path = os.path.join(CONFIG["json_res_dir"], date, f'{project_name}.jsonl')
    project_data = read_jsonl(jsonl_path)
    all_uts = get_all_test_use_json(project_data)
    return all_uts


def get_covage_info(total_coverage_info, method_signature):
    (package_name, package_dir, class_name, clazz_dir, method_name, parameter_tuple) = analyze_method_signature_for_coverage(method_signature)
    data = total_coverage_info.get(package_name)
    if data is None:
        return None
    data = data.get(clazz_dir)
    if data is None:
        return None
    data = data.get(method_name)
    if data is None:
        return None
    data = data.get(tuple(parameter_tuple))
    if data is None:
        return None
    result = {
        'LINE': data.get('line_coverage') if data.get('line_coverage') else {'covered': 0, 'missed': 0},
        'BRANCH': data.get('branch_coverage') if data.get('branch_coverage') else {'covered': 0, 'missed': 0}
    }
    return result

def set_up_coveragee_info(result, focal_method, coverage_info, mark):
    if focal_method not in result:
        result[focal_method] = {}
    if coverage_info is None:
        result[focal_method][mark] = {
            'covered_lines': 0,
            'missed_lines': 0,
            'line_coverage_rate': 0,
            'covered_branches': 0,
            'missed_branches': 0,
            'branch_coverage_rate': 0
        }
    else:
        result[focal_method][mark] = {
            'covered_lines': int(coverage_info['LINE']['covered']),
            'missed_lines': int(coverage_info['LINE']['missed']),
            'line_coverage_rate': int(coverage_info['LINE']['covered']) / (
                        int(coverage_info['LINE']['covered']) + int(coverage_info['LINE']['missed'])) if int(coverage_info['LINE']['covered']) + int(coverage_info['LINE']['missed']) > 0 else 0,
            'covered_branches': int(coverage_info['BRANCH']['covered']),
            'missed_branches': int(coverage_info['BRANCH']['missed']),
            'branch_coverage_rate': int(coverage_info['BRANCH']['covered']) / (
                        int(coverage_info['BRANCH']['covered']) + int(coverage_info['BRANCH']['missed'])) if int(coverage_info['BRANCH']['covered']) + int(coverage_info['BRANCH']['missed']) > 0 else 0,
        }

def collect_coverage_info(all_packages, project_name, coverage_info, coverage_result, mode):
    for package in all_packages:
        if package not in coverage_result:
            coverage_result[package] = {}
        focal_method_sigs = load_focal_method(project_name, package)
        # focal_method_sigs = [('org.llm#NonGenericClass#createContainer(java.lang#String)', '')]
        for focal_method_sig, _ in focal_method_sigs:
            single_coverage_info = get_covage_info(coverage_info, focal_method_sig)
            set_up_coveragee_info(coverage_result[package], focal_method_sig, single_coverage_info, mode)
    return coverage_result


def run(project_name, llm_generate_case):
    project_root = CONFIG['path_mappings'][project_name]['loc']
    test_root_dir = CONFIG['path_mappings'][project_name]['test']
    
    coverage_result = {}
    all_packages = load_packages(project_name)
    # all_packages = ['org.llm']
    # 先跑一下现有结果
    exist_result = run_mvn_test((project_root, None, None))
    
    coverage_info = get_coverage_info(exist_result)
    
    coverage_result = collect_coverage_info(all_packages, project_name, coverage_info, coverage_result, 'existing')
    
    # 跑生成后的结果
    for case in llm_generate_case:
        write_test_class(project_root, test_root_dir, case['test_class_sig'], case['generated_test'])
    
    llm_result = run_mvn_test((project_root, None, None))
    
    # for case in llm_generate_case:
    #     clear_test_class(project_root, test_root_dir, case['test_class_sig'])
    
    coverage_info = get_coverage_info(llm_result)
    
    coverage_result = collect_coverage_info(all_packages, project_name, coverage_info, coverage_result, 'llm')
    
    existing_line_total = 0
    existing_line_covered = 0
    existing_branch_total = 0
    existing_branch_covered = 0
    llm_line_total = 0
    llm_line_covered = 0
    llm_branch_total = 0
    llm_branch_covered = 0
    for info in coverage_result.values():
        for focal_method, data in info.items():
            existing_line_total += data['existing']['covered_lines'] + data['existing']['missed_lines']
            existing_line_covered += data['existing']['covered_lines']
            existing_branch_total += data['existing']['covered_branches'] + data['existing']['missed_branches']
            existing_branch_covered += data['existing']['covered_branches']
            llm_line_total += data['llm']['covered_lines'] + data['llm']['missed_lines']
            llm_line_covered += data['llm']['covered_lines']
            llm_branch_total += data['llm']['covered_branches'] + data['llm']['missed_branches']
            llm_branch_covered += data['llm']['covered_branches']
    existing_line_rate = existing_line_covered / existing_line_total if existing_line_total > 0 else 0
    existing_branch_rate = existing_branch_covered / existing_branch_total if existing_branch_total > 0 else 0
    llm_line_rate = llm_line_covered / llm_line_total if llm_line_total > 0 else 0
    llm_branch_rate = llm_branch_covered / llm_branch_total if llm_branch_total > 0 else 0
    line_improve = (llm_line_rate - existing_line_rate) / existing_line_rate if existing_line_rate > 0 else 0
    branch_improve = (llm_branch_rate - existing_branch_rate) / existing_branch_rate if existing_branch_rate > 0 else 0
    
    return line_improve, branch_improve, existing_line_rate, existing_branch_rate, llm_line_rate, llm_branch_rate

def get_coverage_info(result):
    if result['result'] == 'Passed':
        coverage_info = parse_coverage_xml(os.path.join(result['directory'], 'target/site/jacoco/jacoco.xml'))
    elif result['result'] == 'Failed Compilation':
        coverage_info = None
    elif result['result'] == 'Failed Execution':
        coverage_info = parse_coverage_xml(os.path.join(result['directory'], 'target/site/jacoco/jacoco.xml'))
    else:
        coverage_info = None
        raise NotImplementedError("Unknown result. Please check.")
    return coverage_info

def main():
    all_projects = list(CONFIG['path_mappings'].keys())
    date = CONFIG['expr_identifier']
    for project in all_projects:
        print(f'Running on {project}')
        llm_generate_case = setup_single_project(date, project)
        line_improve, branch_improve, existing_line_rate, existing_branch_rate, llm_line_rate, llm_branch_rate = run(project, llm_generate_case)
        print(f'Line Rate Improvement: {line_improve}')
        print(f'Branch Rate Improvement: {branch_improve}')
        print(f'Existing Line Rate: {existing_line_rate}')
        print(f'Existing Branch Rate: {existing_branch_rate}')
        print(f'LLM Line Rate: {llm_line_rate}')
        print(f'LLM Branch Rate: {llm_branch_rate}')
        print('--------------------------')
        
if __name__ == '__main__':
    main()