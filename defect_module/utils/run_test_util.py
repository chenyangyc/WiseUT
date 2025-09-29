from io import StringIO
import os
import json
from data.configurations import coverage_tool, code_base
import subprocess


def assemble_test_file(module_dir, module_name, index, processed_imports, test_case):
    tmp_name = module_name.replace('.', '_')
    test_file = os.path.join(module_dir, f'test_case_{tmp_name}_{index}.py')
    test_content = StringIO('')
    
    for imp in processed_imports:
        test_content.write(f'{imp}\n')
        
    test_content.write('\n')
    test_content.write('class Test(unittest.TestCase):\n')

    test_content.write('\n    @timeout_decorator.timeout(1)\n')
    for line in test_case.split('\n'):
        test_content.write(f'    {line}\n')

    test_content.write('\nif __name__ == "__main__":\n')
    test_content.write('    unittest.main()\n')
    
    final_content = test_content.getvalue()
    test_content.close()
    
    with open(test_file, 'w') as f:
        f.write(final_content)
    return test_file, final_content


def run_test_and_collect_cov(module_dir, module_path, test_file, report_dir, index, module_tmp_dir):
    original_dir_and_files = os.listdir(module_dir)

    if os.path.exists(module_tmp_dir):
        os.system(f'rm -rf {module_tmp_dir}')
    
    os.makedirs(module_tmp_dir)
    
    user_home = os.environ['HOME']
    os.environ['HOME'] = module_tmp_dir

    os.chdir(module_tmp_dir)
    os.system(f'{coverage_tool} erase')

    permission = 0o555
    try:
        # 修改文件夹的权限
        os.chmod(code_base, permission)
        print("成功设置父文件夹的不可删除权限！")
    except OSError:
        print("设置父文件夹的权限失败！")

    # run_output_file = os.popen(f'timeout 10 {coverage_tool} run ' + test_file)
    # run_output = run_output_file.read()
    # run_output_file.close()

    cmd = f'timeout 10 {coverage_tool} run --branch ' + test_file
    process_output = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
    run_output = process_output.stderr
    
    
    report_file = os.path.join(report_dir, str(index) + '_report.json')
    report_output_file = os.popen(f'{coverage_tool} json -o {report_file} --pretty-print --show-contexts --include={module_path}')
    report_output = report_output_file.read()
    report_output_file.close()
    
    try:
        with open(report_file, 'r') as f:
            raw_coverage = json.load(f)

        file_info = list(raw_coverage['files'].values())[0]
        executed_lines = set(file_info['executed_lines'])
        missing_lines = set(file_info['missing_lines'])
        executed_branches = file_info['executed_branches']
        missing_branches = file_info['missing_branches']
        
        coverage = {
            'file': file_info,
            'exec': executed_lines,
            'miss': missing_lines,
            'exec_branch': executed_branches,
            'miss_branch': missing_branches,
            'all': executed_lines.union(missing_lines)
        }
    except:
        coverage = None
    
    if not os.path.exists(module_tmp_dir):
        os.makedirs(module_tmp_dir)
    
    for thing in os.scandir(module_dir):
        if thing.name in original_dir_and_files:
            continue
        else:
            if 'test_case_' not in thing.name:
                os.system('rm -r ' + thing.name)
                
    # os.system(f'rm {test_file}' )
    os.environ['HOME'] = user_home
    
    return run_output, report_output, coverage

def run_test_and_get_output(module_dir, test_file, module_tmp_dir):
    original_dir_and_files = os.listdir(module_dir)

    # 删除临时目录，如果存在
    if os.path.exists(module_tmp_dir):
        os.system(f'rm -rf {module_tmp_dir}')
    
    # 创建临时目录
    os.makedirs(module_tmp_dir)
    
    user_home = os.environ['HOME']
    os.environ['HOME'] = module_tmp_dir
    os.chdir(module_tmp_dir)
    
    permission = 0o555
    try:
        # 修改文件夹的权限
        os.chmod(code_base, permission)
        # print("成功设置父文件夹的不可删除权限！")
    except OSError:
        print("设置父文件夹的权限失败！")

    # 执行测试命令，超时时间设为10秒
    cmd = f'timeout 10 {coverage_tool} run --branch ' + test_file
    process_output = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
    
    # 检查测试执行的返回状态
    if process_output.returncode != 0:
        # 如果返回码不为零，说明出现了错误
        error_message = f"Test execution failed with error code {process_output.returncode}. "
        error_message += "Error details: " + process_output.stderr
        return error_message

    # 获取标准输出（正常输出）
    run_output = process_output.stdout
    
    # 清理临时目录中的文件
    if not os.path.exists(module_tmp_dir):
        os.makedirs(module_tmp_dir)
    
    for thing in os.scandir(module_dir):
        if thing.name in original_dir_and_files:
            continue
        else:
            if 'test_case_' not in thing.name:
                os.system('rm -r ' + thing.name)

    os.environ['HOME'] = user_home  # 恢复原来的HOME环境变量
    
    return run_output


def write_test_file(module_dir , new_test_file, test_case):
    test_file_location = os.path.join(module_dir, new_test_file)
    
    with open(test_file_location, 'w') as f:
        f.write(test_case)
    return test_file_location, test_case


def run_test_and_collect_cov_from_scratch(module_dir, module_name, module_path, test_file, report_dir, index, module_tmp_dir):
    original_dir_and_files = os.listdir(module_dir)

    if os.path.exists(module_tmp_dir):
        os.system(f'rm -rf {module_tmp_dir}')
    
    os.makedirs(module_tmp_dir)
    
    user_home = os.environ['HOME']
    os.environ['HOME'] = module_tmp_dir
    os.environ['COVERAGE_FILE'] = os.path.join(module_tmp_dir, '.coverage')

    os.chdir(module_tmp_dir)
    os.system(f'{coverage_tool} erase')

    permission = 0o555
    try:
        # 修改文件夹的权限
        os.chmod(code_base, permission)
        print("成功设置父文件夹的不可删除权限！")
    except OSError:
        print("设置父文件夹的权限失败！")

    # run_output_file = os.popen(f'timeout 10 {coverage_tool} run ' + test_file)
    # run_output = run_output_file.read()
    # run_output_file.close()

    os.chdir(module_dir)
    # test_name = test_file.split('/')[-1].split('.')[0]
    # module_file = module_name.split('.')[-1]
    # test_module = module_name.replace(module_file, test_name)
    # cmd = f'timeout 10 {coverage_tool} run --branch -m ' + test_module
    
    cmd = f'timeout 10 {coverage_tool} run ' + test_file
    process_output = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
    run_output = process_output.stdout + process_output.stderr
    
    os.chdir(module_tmp_dir)
    report_file = os.path.join(report_dir, str(index) + '_report.json')
    report_output_file = os.popen(f'{coverage_tool} json -o {report_file} --pretty-print --show-contexts --include={module_path}')
    report_output = report_output_file.read()
    report_output_file.close()
    
    try:
        with open(report_file, 'r') as f:
            raw_coverage = json.load(f)

        file_info = list(raw_coverage['files'].values())[0]
        executed_lines = set(file_info['executed_lines'])
        missing_lines = set(file_info['missing_lines'])
        executed_branches = file_info['executed_branches']
        missing_branches = file_info['missing_branches']
        
        coverage = {
            'file': file_info,
            'exec': executed_lines,
            'miss': missing_lines,
            'exec_branch': executed_branches,
            'miss_branch': missing_branches,
            'all': executed_lines.union(missing_lines)
        }
    except:
        coverage = None
    
    if not os.path.exists(module_tmp_dir):
        os.makedirs(module_tmp_dir)
    
    for thing in os.scandir(module_dir):
        if thing.name in original_dir_and_files:
            continue
        else:
            if 'test_case_' not in thing.name:
                os.system('rm -r ' + thing.name)
                
    os.system(f'rm {test_file}')
    os.environ['HOME'] = user_home
    del os.environ['COVERAGE_FILE']
    return run_output, report_output, coverage


def run_test_and_collect_cov_lightweight(module_dir, test_file, relative_test_file, used_framework, module_tmp_dir, python_bin):
    original_dir_and_files = os.listdir(module_dir)

    if os.path.exists(module_tmp_dir):
        os.system(f'rm -rf {module_tmp_dir}')
    
    os.makedirs(module_tmp_dir)

    permission = 0o555
    try:
        # 修改文件夹的权限
        os.chmod(code_base, permission)
        # print("成功设置父文件夹的不可删除权限！")
    except OSError:
        pass
        # print("设置父文件夹的权限失败！")

    os.chdir(module_dir)
    relative_test_name = relative_test_file.replace('/', '.').replace('.py', '')
    
    if used_framework == 'unittest':
        cmd = f'{python_bin} -m unittest {relative_test_name}'
    elif used_framework == 'pytest':
        cmd = f'{python_bin} -m pytest {relative_test_file}'
    elif used_framework == 'py.test':
        cmd = f'py.test {relative_test_file}'
    else:
        raise ValueError("Unsupported testing framework. Please use 'unittest' or 'pytest'.")
    
    # cmd = f'{python_bin} {test_file}'
    cmd = 'PYTHONPATH=./ timeout 60 ' + cmd
    process_output = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8', errors='replace')
    run_output = process_output.stdout + process_output.stderr

    for thing in os.scandir(module_dir):
        if thing.name in original_dir_and_files:
            continue
        else:
            if 'test_case_' not in thing.name:
                os.system('rm -r ' + thing.name)
                
    os.system(f'rm {test_file}')
    return run_output, process_output.stdout, process_output.stderr

    
def is_triggered(focal_output, fixed_output):
    focal_passed = True
    fixed_passed = True
    focal_type_error = False
    fixed_type_error = False
    triggered = False
    if 'error' in focal_output.lower():
        focal_passed = False
    if 'error' in fixed_output.lower():
        fixed_passed = False
    
    processed_focal_output = focal_output.replace('(TypeError)', '')
    processed_focal_output = processed_focal_output.replace('DID NOT RAISE <class \'TypeError\'>', '')
    processed_focal_output = processed_focal_output.replace('trigger TypeError', '')
    processed_focal_output = processed_focal_output.replace('a TypeError', '')
    processed_focal_output = processed_focal_output.replace('TypeError\"\"\"', '')
    
    processed_fixed_output = fixed_output.replace('(TypeError)', '')
    processed_fixed_output = processed_fixed_output.replace('DID NOT RAISE <class \'TypeError\'>', '')
    processed_fixed_output = processed_fixed_output.replace('trigger TypeError', '')
    processed_fixed_output = processed_fixed_output.replace('a TypeError', '')
    processed_fixed_output = processed_fixed_output.replace('TypeError\"\"\"', '')
    
    if ': TypeError' in processed_focal_output or 'TypeError:' in processed_focal_output:
        focal_type_error = True
        
    if ': TypeError' in processed_fixed_output or 'TypeError:' in processed_fixed_output:
        fixed_type_error = True
        
    if focal_type_error and not fixed_type_error:
        triggered = True
    return  triggered, focal_type_error, fixed_type_error, focal_passed, fixed_passed
    