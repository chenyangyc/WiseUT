import os
import copy
import json
import sys
import time
import traceback
import sys
sys.path.extend(['.', '..'])

from data.Config import CONFIG, logger, code_base
from utils.preprocess_project import analyze_project, delete_existing_case_and_save, get_callable_methods, recovery_existing_case
from utils.llm_util_java import construct_prompt, invoke_llm
from utils.test_construct_utils import assembly_test_class_component, construct_test_class
from utils.strategy_utils import update_strategies
from utils.test_excute_utils import build_project, compile_and_collect_coverage_test


# 记录时间
time_dict = {}

def setup_expr_info(package_name, single_target):
    expr_info = {
        'package_name': package_name,
        "target_method": single_target.name,
        "test_class_sig": '',
        "strategy": '',
        "res": '',
        "compiled": '',
        'compile_err': '',
        'execution_err': '',
        "generated_test": '',
        "target_function_content": single_target.content,
        "stage1_prompt": '',
        "stage1_response": '',
        "stage2_prompt": '',
        "stage2_response": '',
        "processed_imports": '',
        'line_number': ','.join([str(i) for i in list(single_target.line_range)]),
        'origin_covered_lines':  ','.join([str(i) for i in list(single_target.get_covered_lines())]),
        'origin_covered_rate': len(single_target.get_covered_lines()) / len(single_target.line_range) if len(single_target.line_range) != 0 else 0,
        'covered_lines': ','.join([str(i) for i in list(single_target.get_covered_lines())]),
        'covered_rate': len(single_target.get_covered_lines()) / len(single_target.line_range) if len(single_target.line_range) != 0 else 0,
    }
    return expr_info

def run_method(single_target, project_name, all_packages, method_map, class_map, json_writer, debugging_mode=False):
    project_root = CONFIG['path_mappings'][project_name]['loc']
    test_root_dir = CONFIG['path_mappings'][project_name]['test']
    src_root_dir = CONFIG['path_mappings'][project_name]['src']

    package_name = single_target.get_package_name()
    # 记录结果
    expr_info = setup_expr_info(package_name, single_target)
    
    # 记录各种策略使用的情况
    strtegies_rounds = {
        'direct': list(),
        'indirect': list(),  
        'new': list()
    }
    direct_selected_examples = list()
    prompt_cache_dict = {}
    generated = False
    
    # 可选择的策略
    all_conditions = update_strategies(strtegies_rounds, single_target, direct_selected_examples)
    before_llm_cov_rate = len(single_target.get_covered_lines()) / len(single_target.line_range)
    
    while any(all_conditions):
        prompt, context, chosen_strategy, selected_examples = construct_prompt(single_target, all_conditions, direct_selected_examples, class_map)
        if chosen_strategy is None:
            logger.debug(f"Target does not chosen a strategy, stop generating")
            break  # As no strategy was chosen, exit the loop.
            
        logger.debug(f"Invoking the LLM")
        stage1_prompt, stage1_response, stage2_prompt, stage2_response, generated = invoke_llm(single_target, context, prompt, prompt_cache_dict, debugging_mode)
        
        if generated == False:
            logger.debug(f'LLM not generated, stop generating')
            break
        logger.debug(f"Get the LLM response, executing the tests")
        
        total_imports, fields, setup_methods, classes, uts = assembly_test_class_component(single_target, stage2_response, selected_examples, os.path.join(project_root, src_root_dir))
        
        origin_target_coverage = copy.deepcopy(single_target.get_covered_lines())
        origin_target_rate = len(single_target.get_covered_lines()) / len(single_target.line_range)
        
        # 先进行一次mvn编译
        logger.debug(f"Compiling the project")
        compile_result = build_project(project_root)
        if not compile_result['compile']:
            logger.debug(f"Project does not compile")
            break
        else:
            logger.debug(f"Project compiled")
        
        logger.debug(f"LLM generated test cases: {len(uts)}")
        for id, single_ut in enumerate(uts):
            logger.debug(f"Processing test case {id + 1} / {len(uts)}")
            
            single_origin_coverage_lines = copy.deepcopy(single_target.get_covered_lines())
            if single_origin_coverage_lines == 1:
                logger.debug(f"Target already fully covered, stop compiling")
                break
            test_class_content, test_class_sig = construct_test_class(single_target, total_imports, fields, setup_methods, classes, single_ut)
            compile_err, exec_err, is_compiled, res = compile_and_collect_coverage_test(single_target, project_root, test_root_dir, test_class_content, test_class_sig, all_packages, method_map, class_map)
            
            logger.debug(f"{id + 1}-th test case compiled : {is_compiled}")
            
            expr_info.update({
                        "test_class_sig": test_class_sig,
                        "strategy": chosen_strategy,
                        "res": res,
                        "compiled": is_compiled,
                        'compile_err': compile_err,
                        'execution_err': exec_err,
                        "generated_test": test_class_content,
                        "stage1_prompt": stage1_prompt,
                        "stage1_response": stage1_response,
                        "stage2_prompt": stage2_prompt,
                        "stage2_response": stage2_response,
                        "processed_imports": '\n'.join(total_imports),
                        'covered_lines': ','.join([str(i) for i in list(single_target.get_covered_lines())]),
                        'covered_rate': len(single_target.get_covered_lines()) / len(single_target.line_range) if len(single_target.line_range) != 0 else 0,
                    })
            json_writer.write(json.dumps(expr_info) + '\n')
            json_writer.flush()
            
            logger.debug(f"Finish processing test case {id + 1} / {len(uts)}")
        
        if len(single_target.get_covered_lines() - origin_target_coverage) > 0:
            res = 'better!'
        else:
            res = 'useless!'
            
        # print(res)
        # logger.debug(f"Coverage for target is {res}")
        # logger.debug(f"Origin coverage rate is {origin_target_rate}")
        # logger.debug(f"After LLM generate coverage rate is {expr_info['covered_rate']}\n\n")
            
        after_cov_rate = len(single_target.get_covered_lines()) / len(single_target.line_range)
        
        if after_cov_rate == 1:
            break
        
        strtegies_rounds[chosen_strategy].append(copy.deepcopy(single_target.get_covered_lines()))
        
        all_conditions = update_strategies(strtegies_rounds, single_target, direct_selected_examples)
        
    
    if not generated:
        expr_info.update({"res": 'No program generated.'})
        json_writer.write(json.dumps(expr_info) + '\n')
        json_writer.flush()
    pass
    after_llm_cov_rate = len(single_target.get_covered_lines()) / len(single_target.line_range)
    if after_llm_cov_rate > before_llm_cov_rate:
        res = 'better!'
    else:
        res = 'useless!'
    
    logger.debug(f"Coverage for target {single_target.signature} is {res}")

def run_package(project_name, single_package, collect_type):
    package_name = single_package.name
    time_dict[project_name][package_name] = {}
    
    callable_methods = get_callable_methods(project_name, single_package, collect_type)
    if len(callable_methods) == 0:
        # logger.debug(f"No target methods in package {package_name}")
        return []
    return callable_methods
    
def run_projcet(project_name, json_res_dir, tmp_test_dir, debugging_mode=False):
    json_res_file = os.path.join(json_res_dir, project_name + '.jsonl')
    json_writer = open(json_res_file, "w",)
    
    time_dict[project_name] = {}
    
    ## 防止出现之前的结果没有重新写回的情况
    # logger.debug(f"Before static analysis, recover existing case in projcet {project_name}")
    # recovery_existing_case(project_name, tmp_test_dir)
    
    # 通过静态分析提取到项目中的代码调用关系, 以及现有测试程序对应方法的映射
    logger.debug(f"Begin static analysis project for {project_name}")
    all_packages, method_map, class_map = analyze_project(project_name, debugging_mode)
    logger.debug(f"Finish static analysis project for {project_name}")
    
    # 在项目中把已有的test都删掉，节省编译时间
    logger.debug(f"Begin deleting existing case in projcet {project_name}")
    delete_existing_case_and_save(project_name, tmp_test_dir)
    logger.debug(f"Finish deleting existing case in projcet {project_name}")
    
    all_callable_methods = []
    if debugging_mode:
        all_packages = [i for i in all_packages if i.name == 'org.llm']
    
    collect_type = CONFIG['path_mappings'][project_name]['test_scale']
    logger.debug(f"Collecting target methods.")
    try:
        for package_index, single_package in enumerate(all_packages):
            package_name = single_package.name
            # logger.debug(f"Processing package {package_name}, {package_index + 1} / {len(all_packages)}")

            collected_methods = run_package(project_name, single_package, collect_type)
            all_callable_methods.extend(collected_methods)
        pass

        logger.debug(f"Collected {len(all_callable_methods)} target methods.")
        for target_index, single_target in enumerate(all_callable_methods):
            logger.debug(f"Processing target: {single_target.signature}, {target_index + 1} / {len(all_callable_methods)}")
            
            run_time = time.time()
            run_method(single_target, project_name, all_packages, method_map, class_map, json_writer, debugging_mode)
            run_time = time.time() - run_time
            logger.debug(f"Time elapsed: {run_time}")
            
            time_dict[project_name][package_name][single_target.signature] = run_time
            logger.debug(f"Generation for target: {single_target.signature}, {target_index + 1} / {len(all_callable_methods)} finished!\n\n")

    except Exception as e:
        print('Exception:', e)
        traceback.print_exc()
    finally:
        # 把所有的测试程序写回原项目
        logger.debug(f"Begin recovery existing case in projcet {project_name}")
        recovery_existing_case(project_name, tmp_test_dir)
        logger.debug(f"Finish recovery existing case in projcet {project_name}")
        pass

def run(json_res_dir, tmp_test_dir, debugging_mode=False):
    # 获取需要执行的project列表
    # done_projs = []
    # if os.path.exists(done_proj_file):
    #     with open(done_proj_file, 'r') as f:
    #         for line in f:
    #             project_name = line.strip()
    #             done_projs.append(project_name)
    # todo_projects = [project for project in list(CONFIG['path_mappings'].keys()) if project not in done_projs]
    
    todo_projects = [project for project in list(CONFIG['path_mappings'].keys())]
    # logger.debug(f"Total number of projects: {len(todo_projects)}")
    
    for proj_index, project_name in enumerate(todo_projects):
        logger.debug(f"Begin processing project {project_name}")
        
        run_projcet(project_name, json_res_dir, tmp_test_dir, debugging_mode)
        
        # with open(done_proj_file, 'a+') as f:
        #     f.write(project_name + '\n')
        logger.debug(f"Finished project {project_name}\n\n")
        logger.debug(f"Collect generated suite and overall coverage\n\n")

def record_time(time_dict, date):
    total_time = 0
    total_method = 0
    
    for project, package_dict in time_dict.items():
        for package, method_dict in package_dict.items():
            for method, time in method_dict.items():
                total_time += time
                total_method += 1
    
    if total_method == 0:
        logger.debug(f"No method processed, return")
        return
    logger.debug(f"Total time elapsed: {total_time}")
    logger.debug(f"Total method processed: {total_method}")
    logger.debug(f"Average time elapsed: {total_time / total_method}")
    
    time_dict['total_time'] = total_time
    time_dict['total_method'] = total_method
    time_dict['average_time'] = total_time / total_method
    
    time_dir = os.path.join(code_base, 'data', 'time')
    if not os.path.exists(time_dir):
        os.makedirs(time_dir)
    time_file = os.path.join(code_base, 'data', 'time', date + '.json')
    with open(time_file, 'w') as f:
        json.dump(time_dict, f)


def coverage_entry():
    # 获取当前时间的时间戳
    timestamp = time.time()
    # 将时间戳转换为可读的时间字符串（例如：2023-04-01 12:34:56）
    readable_time = time.strftime('%Y-%m-%d_%H:%M:%S', time.localtime(timestamp))
    
    # 用于标记区分每一次运行
    date = CONFIG['expr_identifier']
    # date = 'test_926'
    # 本项目路径
    code_base = CONFIG['code_base']
    
    # # 已经跑完的项目
    # done_proj_file = os.path.join(code_base, CONFIG['done_project'])
    
    # 存储所有的大模型生成后的结果
    json_res_dir = os.path.join(code_base, CONFIG['json_res_dir'], date)
    os.makedirs(json_res_dir, exist_ok=True)
    
    # 存储所有现有的test case的路径
    tmp_test_dir = os.path.join(code_base, CONFIG['tmp_test_dir'], date)
    os.makedirs(tmp_test_dir, exist_ok=True)
    
    logger.debug("Generation begins!")
    run(json_res_dir, tmp_test_dir, debugging_mode=False)
    logger.debug("Generation completed!")
    
    record_time(time_dict, date)
    
    
if __name__ == '__main__':
    # 获取当前时间的时间戳
    timestamp = time.time()
    # 将时间戳转换为可读的时间字符串（例如：2023-04-01 12:34:56）
    readable_time = time.strftime('%Y-%m-%d_%H:%M:%S', time.localtime(timestamp))
    
    # 用于标记区分每一次运行
    date = CONFIG['expr_identifier']
    # date = 'test_926'
    # 本项目路径
    code_base = CONFIG['code_base']
    
    # # 已经跑完的项目
    # done_proj_file = os.path.join(code_base, CONFIG['done_project'])
    
    # 存储所有的大模型生成后的结果
    json_res_dir = os.path.join(code_base, CONFIG['json_res_dir'], date)
    os.makedirs(json_res_dir, exist_ok=True)
    
    # 存储所有现有的test case的路径
    tmp_test_dir = os.path.join(code_base, CONFIG['tmp_test_dir'], date)
    os.makedirs(tmp_test_dir, exist_ok=True)
    
    logger.debug("Generation begins!")
    run(json_res_dir, tmp_test_dir, debugging_mode=False)
    logger.debug("Generation completed!")
    
    record_time(time_dict, date)