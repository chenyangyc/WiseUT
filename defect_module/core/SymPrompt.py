import copy
import os
import pickle
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import re
from utils.file_parse import extract_functions_for_llm
from utils.tree_sitter_query import parser, BRANCH_QUERY, RETURN_QUERY
from core.chatbot import ChatBot
from data.configurations import api_key, base_url, model, temperature
import time
from loguru import logger


def reindent_model_output(model_output):
    pattern = r"```python(.*?)```"
    backup_pattern = r"```(.*?)```"
    # Find and extract the code snippet
    try:
        code_snippet = re.findall(pattern, model_output, re.DOTALL)[0]
    except:
        try:
            code_snippet = re.findall(backup_pattern, model_output, re.DOTALL)[0]
        except:
            code_snippet = model_output
    try:
        functions = extract_functions_for_llm(code_snippet)
    except:
        functions = []
        
    return code_snippet, functions 


def add_indent(origin_str, indent_num):
    new_str = []
    prefix_indent = '    ' * indent_num
    
    for i in origin_str.split('\n'):
        new_str.append(f'{prefix_indent}{i}')
    new_str = '\n'.join(new_str)
    return new_str

        
class SymPrompt:
    def __init__(self, single_function, used_framework='', all_imports='', all_fields='', all_test_imports=[], chatbot=None, prompt_cache=None, logger=None):
        self.single_function = single_function
        self.function_name = single_function.name
        self.function_content = single_function.content
        self.function_signature = single_function.signature
        self.belong_class = single_function.belong_class
        self.belong_module = single_function.belong_module
        
        self.all_imports = all_imports
        self.all_fields = all_fields
        self.all_test_imports = all_test_imports
        self.used_framework = used_framework
        self.chatbot = chatbot
        self.prompt_cache = prompt_cache
        self.logger = logger
        
        if 'unittest' in self.used_framework:
            self.all_test_imports.append('import unittest')
        elif 'pytest' in self.used_framework:
            self.all_test_imports.append('import pytest')
        
        self.branches = self.analyse_method_branch()
        self.class_context = self.construct_class_context(single_function)
        
        self.llm_system_prompt = f'''You are an intelligent programming assistant to help user writing python unit tests. 
If you provide code in your response, the code you write should be in format ```python <code> ```.
The target method is `{self.function_name}` in the module `{self.belong_module.name}`, the context is:
```python
{all_imports}\n\n{all_fields}\n\n{self.class_context}\n\n
```     '''
        self.chatbot.system_prompt = self.llm_system_prompt
    
    def analyse_method_branch(self):
        # 分支包括if statement和while statement
        root_node = parser.parse(bytes(self.function_content, 'utf8')).root_node
        branch_node_list = BRANCH_QUERY.captures(root_node).get('branch', [])
        
        branch_results = []
        for branch_node in branch_node_list:
            single_branch_result = {
                'branch_content': branch_node.text.decode('utf-8'),
                'conditions': []
            }
            all_condition_content = ''
            
            condition_node = branch_node.child_by_field_name('condition')
            if condition_node:
                condition_content = condition_node.text.decode('utf-8')
                if all_condition_content:
                    all_condition_content = f'{all_condition_content} and ({condition_content})'
                else:
                    all_condition_content = f'({condition_content})'
            else:
                condition_content = f'not ({all_condition_content})'
            
            return_node_list = RETURN_QUERY.captures(condition_node).get('return', [])
            return_node = None
            for single_return_node in return_node_list:
                if single_return_node.parent.parent == branch_node:
                    return_node = single_return_node
                    break
            
            single_branch_result['conditions'].append({
                'condition': condition_content,
                'return': return_node.text.decode('utf-8') if return_node else '',
            })
            
            else_node_list = branch_node.children_by_field_name('alternative')
            for else_node in else_node_list:
                else_condition_node = else_node.child_by_field_name('condition')
                if else_condition_node:
                    condition_content = else_condition_node.text.decode('utf-8')
                    if all_condition_content:
                        all_condition_content = f'{all_condition_content} and ({condition_content})'
                    else:
                        all_condition_content = f'({condition_content})'
                else:
                    condition_content = f'not ({all_condition_content})'
                
                return_node_list = RETURN_QUERY.captures(else_node).get('return', [])
                return_node = None
                for single_return_node in return_node_list:
                    if single_return_node.parent.parent == else_node:
                        return_node = single_return_node
                        break
                
                single_branch_result['conditions'].append({
                    'condition': condition_content,
                    'return': return_node.text.decode('utf-8') if return_node else '',
                })
            branch_results.append(single_branch_result)

        return branch_results
    
    def path_minimization(self):
        paths = []
        
        def dfs(now, max, current_path):
            if now == max:
                paths.append(copy.deepcopy(current_path))
                return
            
            for i in range(len(self.branches[now]['conditions'])):
                condition = self.branches[now]['conditions'][i]['condition']
                return_value = self.branches[now]['conditions'][i]['return']
                if return_value:
                    current_path.append(condition)
                    current_path.append(f'returns: {return_value}')
                    paths.append(copy.deepcopy(current_path))
                    current_path.pop()
                    current_path.pop()
                else:
                    current_path.append(condition)
                    dfs(now + 1, max, current_path)
                    current_path.pop()
        dfs(0, len(self.branches), [])
        
        minconstraints = []
        minpaths = []
        for path in paths:
            constraints = []
            for condition in path:
                if 'returns' not in condition:
                    constraints.append(condition)
            if any(constraint not in minconstraints for constraint in constraints):
                minpaths.append(path)
                for constraint in constraints:
                    if constraint not in minconstraints:
                        minconstraints.append(constraint)
        return paths


    def construct_class_context(self, method):
        belong_class = method.belong_class
        if belong_class:
            class_definition = f'class {belong_class.name}:'
            
            class_attrs = [add_indent(line, indent_num=1) for line in belong_class.attributes]
            class_attrs = '\n'.join(class_attrs)
            
            class_constructor = [add_indent(init_method, indent_num=1) for init_method in belong_class.init]
            class_constructor = '\n\n'.join(class_constructor)
            
            indented_method = add_indent(method.content, indent_num=1)
            class_context = f'# Focal class\n{class_definition}\n\n{class_attrs}\n\n{class_constructor}\n\n    # Focal method\n{indented_method}'
        else:
            class_context = '# Focal method' + '\n' + method.content
            
        return class_context


    def generate_prompt(self, test_class, cnt):
        user_prompt = f'''You should cover the provided branch with the required condition. Here is the test file:
```python
{test_class}
```
The test function to be completed is 'test_case_{cnt}'.
Please complete the test function and provide the complete executable test file. Do not omit any code in the provided test file.
        '''
        return user_prompt


    def construct_test_class(self):
        all_test_imports_str = '\n'.join(self.all_test_imports)
        
        if 'unittest' in self.used_framework:
            previous_class_context = f'''{all_test_imports_str}
        
class TestFocalClass(unittest.TestCase):    
'''
            indent_num = 1
        else:
            previous_class_context = f'''{all_test_imports_str}'''
            indent_num = 0
            
        cnt = 0
        final_response = ''

        if not self.branches:
            user_prompt = f'You are a professional who writes Python test methods.\nPlease write one test case for the "{self.function_name}" with the given method intension in {self.used_framework}.\nThe import statements of the test class include \n```\n{all_test_imports_str}\n```'
            
            self.logger.debug(f'No branches found, using direct prompt')
            if user_prompt not in self.prompt_cache:
                final_response = self.chatbot.chat(user_prompt, '', True)
                self.prompt_cache[user_prompt] = final_response
            else:
                self.logger.debug(f'Direct prompt hit the cache!')
                final_response = self.prompt_cache[user_prompt]
            return [user_prompt], [final_response]
        
        all_prompts = []
        all_responses = []
        for single_branch in self.branches:
            for condition in single_branch['conditions']:
                self.logger.debug(f'Generating for cnt {cnt}')
                test_method_content = f'''
def test_case_{cnt}(self):
    """
    TestCase for {self.function_signature}
    Where: {condition['condition']}
    Returns: {condition['return']}
    """
    '''
                test_method_contents = [add_indent(line, indent_num=indent_num) for line in test_method_content.strip('\n').split('\n')]
                test_method_content = '\n'.join(test_method_contents)
        
                test_class_context = previous_class_context + '\n\n' + test_method_content

                user_prompt = self.generate_prompt(test_class_context, cnt)
                
                try:
                    if user_prompt not in self.prompt_cache:
                        final_response = self.chatbot.chat(user_prompt, '', False)
                        self.prompt_cache[user_prompt] = final_response
                    else:
                        self.logger.debug(f'Prompt hit the cache!')
                        final_response = self.prompt_cache[user_prompt]
                        # self.chatbot.add_history(user_prompt, final_response)
                except:
                    self.logger.debug(f'Chatbot error')
                    time.sleep(30)
                    continue
                
                all_prompts.append(user_prompt)
                all_responses.append(final_response)
                # previous_class_context, test_cases = reindent_model_output(final_response)
                # cnt += 1
        
        return all_prompts, all_responses

    # def main(self):
    #     chat_bot = ChatBot(api_key, base_url, model, self.llm_system_prompt, temperature)
    #     for test_class in self.test_classes:
    #         user_prompt = self.generate_prompt(test_class)
    #         self.llm_prompt.append([
    #             {'role': 'user', 'content': user_prompt}
    #         ])
    #         response = chat_bot.chat(user_prompt, '', True)
    #         self.llm_response.append(response)
        

# python_code = '''
# def complex_method(a, b, c, d):
#     if a > 0:
#         if b < 10:
#             if c == 1:
#                 return "A"
#             elif c == 2:
#                 return "B"
#             else:
#                 return "C"
#         else:
#             if d:
#                 return "D"
#             else:
#                 return "E"
#     else:
#         if b >= 10:
#             if c != 1:
#                 return "F"
#             else:
#                 return "G"
#         else:
#             if d:
#                 return "H"
#             else:
#                 return "I"
# '''

if __name__ == '__main__':
    extracted_focal_method = 'data/extracted_focal_methods_bugsinpy_0412.pkl'
    with open(extracted_focal_method, 'rb') as f:
        all_focals = pickle.load(f)
        
    all_focal_methods = []
    for proj_name, proj_info in all_focals.items():
        print(f'Begin project {proj_name}')
        logger.debug(f'Begin project {proj_name}')
        
        for bug_id, bug_tests in proj_info.items():
            print(f'Begin bug id {proj_name}-{bug_id}')
            logger.debug(f'Begin bug id {proj_name}-{bug_id}')
            
            final_result = {
                'proj_name': proj_name,
                'bug_id': bug_id,
                'test_reses': []
            }
                
            for test_cmd, test_res in bug_tests.items():
                chains = test_res['all_failed_methods']
                
                for single_chain in chains:
                    focal_method = None
                    for method in reversed(single_chain):
                        method_file = method[0]
                        method_obj = method[1]
                        
                        if 'env' not in method_file and 'test' not in method_file:
                            focal_method = method_obj
                    
                    if focal_method:
                        print(f'Bug id {proj_name}-{bug_id}: focal method extracted, begin testing')
                        logger.debug(f'Bug id {proj_name}-{bug_id}: focal method extracted, begin testing')
                        all_focal_methods.append(focal_method)
    
    for focal_method in all_focal_methods:
        symprompt = SymPrompt(focal_method, used_framework='pytest')
        symprompt.construct_test_class()
        a = 1