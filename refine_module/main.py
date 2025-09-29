from run_llm_refine import refine_single_test
from run_code_slicing import splited_code
from data.config import logger, CONFIG, project_names
from code_parser import Code_AST
from pathlib import Path
from collections import defaultdict
import os
import shutil


def collect_existing_test_cases(project_dir, test_dir):
    test_dir = Path(os.path.join(project_dir, test_dir))
    all_test_files = test_dir.rglob('*Test.java')
    all_test_cases_dict = defaultdict()
    
    for single_file in all_test_files:
        # extract test cases
        with open(single_file, 'r') as fr:
            content = fr.read()
            
        if content not in all_test_cases_dict:
            all_test_cases_dict[content] = {
                'path': str(single_file),
                'tests': []
            }

        current_ast = Code_AST(code=content, lang="java").ast
        functions = current_ast.get_functions()
        
        for func in functions:
            all_test_cases_dict[content]['tests'].append(func.source)
    return all_test_cases_dict
    

def refine_tests():
    for project_name in project_names:
        project_dir = CONFIG['path_mappings'][project_name]['loc']
        project_test_dir = os.path.join(project_dir, CONFIG['path_mappings'][project_name]['test'])
        backup_test_dir = os.path.join(project_dir, 'origin_test_backup')
        
        # 如果备份目录已经存在，可以先删除或先检查
        if os.path.exists(backup_test_dir):
            logger.debug('Backup dir already exists')
            # print(f"备份目录已存在，先删除: {backup_test_dir}")
            shutil.rmtree(backup_test_dir)

        # 拷贝整个目录
        shutil.copytree(project_test_dir, backup_test_dir)

        all_test_cases_dict = collect_existing_test_cases(project_dir, project_test_dir)
        
        total_index = 1
        for test_file, file_dict in all_test_cases_dict.items():
            for index, single_case in enumerate(file_dict['tests']):
                logger.debug(f'Refining test {total_index}.')
                refined_cases = main_single_code(single_case)
                refined_cases_content = '\n\n'.join(refined_cases)
                
                refined_test_file = test_file.replace(single_case, refined_cases_content)
                
                with open(file_dict['path'], 'w') as fw:
                    fw.write(refined_test_file)
                pass
                total_index += 1

def main_single_code(code):
    '''
    输入是java代码
    1. 切片
    2. 对切片结果进行refine
    '''
    logger.debug('Begin test purification...')
    slicing_codes = splited_code(code)
    if len(slicing_codes) == 0:
        slicing_codes = [code]
    new_results = []
    
    logger.debug('Begin semantic refinement...')
    for index, single_code in enumerate(slicing_codes):
        single_code = refine_single_test(single_code)
        new_results.append(single_code)
    return new_results


# JAVA_CODE = '''
# public void testCreateCategoryDataset1() {
#     String[] rowKeys = {"R1", "R2", "R3"};
#     String[] columnKeys = {"C1", "C2"};
#     double[][] data = new double[3][];
#     data[0] = new double[] {1.1, 1.2};
#     data[1] = new double[] {2.1, 2.2};
#     data[2] = new double[] {3.1, 3.2};
#     CategoryDataset dataset = DatasetUtilities.createCategoryDataset(
#             rowKeys, columnKeys, data);
#     assertTrue(dataset.getRowCount() == 3);
#     assertTrue(dataset.getColumnCount() == 2);
# }
# '''
# slicing_codes = main_single_code(JAVA_CODE)
# print(slicing_codes)

# project_names = ['jfreechart']
# refine_tests()