import copy
import sys

from utils._coverage_utils import update_coverage
from utils._output_analyser import assemble_single_ut_test_class_mvn
from utils._static_analysis_call_chaining import extract_called_functions
from utils.test_construct_utils import construct_test_class

sys.path.extend([".", ".."])
from core.base_test_program import TestProgram
from utils._write_test_class import *
from utils._run_mvn_test import *
from utils._analyze_jacoco_output import parse_coverage_xml


def write_test_class_and_execute(project_root, test_root_dir, test_class_sig, test_class_content, type, existing=False):   
    write_test_class(project_root, test_root_dir, test_class_sig, test_class_content)
    
    if type == 'clean test':
        result = run_mvn_test((project_root, test_class_sig, None))
    elif type == 'only test':
        result = run_mvn_test_no_clean((project_root, test_class_sig, None))
    
    if result['result'] == 'Passed':
        coverage_info = parse_coverage_xml(os.path.join(result['directory'], 'target/site/jacoco/jacoco.xml'))
    elif result['result'] == 'Failed Compilation':
        coverage_info = None
    elif result['result'] == 'Failed Execution':
        coverage_info = parse_coverage_xml(os.path.join(result['directory'], 'target/site/jacoco/jacoco.xml'))
    else:
        coverage_info = None
        raise NotImplementedError("Unknown result. Please check.")
    result['coverage'] = coverage_info
    # 删除测试类
    if not existing:
        clear_test_class(project_root, test_root_dir, test_class_sig)
    # logger.info(f"Report: {result['result']}")
    
    return result

def build_project(project_root):
    '''mvn clean compile项目'''
    mvn_stdout, mvn_stderr = run_mvn_compile(project_root)
    compile_result = {
        "compile": True if "BUILD SUCCESS" in mvn_stdout else False,
        "stdout": mvn_stdout,
        "stderr": mvn_stderr
    }

    return compile_result

def process_test_case(single_target, all_packages, method_map, class_map, test_class_content, compile_res):
    compile_err = compile_res["stdout"]
    exec_err = compile_res["stderr"]
    is_compiled = False
    res = 'useless!'
    original_coverage_lines = copy.deepcopy(single_target.get_covered_lines())
    
    all_methods_in_package = single_target.belong_package.methods
    if compile_res["result"] == 'Passed' or compile_res["result"] == 'Failed Execution':
        coverage = compile_res["coverage"]
        is_compiled = True
        if coverage is not None:
            new_test_case = TestProgram(content=test_class_content, target_function=single_target, coverage=coverage)
            case_called_functions = extract_called_functions(test_class_content, all_packages, method_map, class_map)
            
            update_coverage(all_methods_in_package, method_map, class_map, new_test_case, case_called_functions, is_llm=True)
            
            if len(single_target.get_covered_lines()) - len(original_coverage_lines) > 0:
                res = 'better!'
        else: # 执行错误，没有覆盖率
            pass   
    else: # 编译错误
        pass
    return compile_err, exec_err, is_compiled, res

def compile_and_collect_coverage_test(single_target, project_root, test_root_dir, test_class_content, test_class_sig, all_packages, method_map, class_map):
    
    compile_res = write_test_class_and_execute(project_root, test_root_dir, test_class_sig, test_class_content, 'only test')
    compile_err, exec_err, is_compiled, res = process_test_case(single_target, all_packages, method_map, class_map, test_class_content, compile_res)
    return compile_err, exec_err, is_compiled, res

