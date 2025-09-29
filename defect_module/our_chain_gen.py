import os
import re
import json
import pickle
from core.chatbot import ChatBot
from data.configurations import example_response, verification_api_key, verification_base_url, verification_model, verification_temperature, semantic_verification_system_prompt, coordinator_system_prompt, generation_system_prompt, type_verification_system_prompt, api_key, base_url, model, temperature, logger

from utils.file_parse import extract_functions_for_llm, extract_module, change_assert_to_pass_in_test, refactor_test_res
from utils.run_test_util import write_test_file, run_test_and_collect_cov_lightweight, is_triggered
from utils.construct_prompts import construct_type_constraints_verification_prompt_non_buggy,construct_semantic_verification_prompt, construct_refine_prompt_non_buggy, construct_coordinator_prompt
from extract_triggering_focal_method import extract_method_from_file_and_line, extract_method_chain_from_test_output


def reformat_prompt(prompt):
    prompt_lines = prompt.split('\n')
    prompt_lines = [i for i in prompt_lines if not i.startswith('================')]
    prompt = '\n'.join(prompt_lines)
    return prompt


def reindent_model_output(model_output):
    pattern = r"```python(.*?)```"

    # Find and extract the code snippet
    code_snippet = re.findall(pattern, model_output, re.DOTALL)[0]

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


def construct_module_context(method):
    belong_module = method.belong_module
    
    all_imports = '\n'.join([i for i in belong_module.imports if 'import Queue' not in i])
    all_fields = '\n'.join(belong_module.fields)
    all_classes = [i.name for i in belong_module.classes]
    
    module_name = belong_module.name.replace('.py', '')

    return all_imports, all_fields, all_classes, module_name
                    
    
def construct_class_context(method):
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

def construct_test_skeleton(origin_test_file_location, origin_test_func):
    single_test_module, all_test_classes, all_test_functions = extract_module(origin_test_file_location)
    
    filtered_funcs = []
    for single_func in all_test_functions:
        is_top_defined = True
        for other_func in all_test_functions:
            if single_func.name != other_func.name and all([i in other_func.line_range for i in single_func.line_range]):
                is_top_defined = False
                break
        if is_top_defined:
            filtered_funcs.append(single_func)
    
    all_test_functions = filtered_funcs
    
    all_imports = '\n'.join([i for i in single_test_module.imports if 'import Queue' not in i])
    all_fields = '\n'.join(single_test_module.fields)
    
    within_class_functions = [i for i in all_test_functions if i.func_type == 'within_class']
    standalone_functions = [i for i in all_test_functions if i.func_type == 'standalone']

    test_func = None
    for single_func in all_test_functions:
        if single_func.name == origin_test_func:
            test_func = single_func
            break

    standalone_should_keep_functions = []
    for single_func in standalone_functions:
        if 'test' not in single_func.name or single_func.content.startswith('@pytest.fixture()'):
            standalone_should_keep_functions.append(single_func)
    
    standalone_should_keep_function_content = '\n\n'.join([add_indent(i.content, indent_num=0) for i in standalone_should_keep_functions])
    module_context = f'{all_imports}\n\n{all_fields}\n\n{standalone_should_keep_function_content}'
    
    within_class_should_keep_functions = []
    
    if origin_test_func == '':
        test_skeleton = module_context
        return test_skeleton
    
    test_class = test_func.belong_class
    
    truncated_test_method = test_func.content.split(f'def {test_func.name}')[0] + f'def {test_func.signature}:\n'
    
    if test_class:
        functions_within_test_class = [func for func in within_class_functions if func.belong_class.name == test_class.name]
        
        for single_func in functions_within_test_class:
            if 'test' not in single_func.name or single_func.content.startswith('@pytest.fixture()') or 'setup' in single_func.name.lower():
                within_class_should_keep_functions.append(single_func)
    
        class_definition = f'class {test_class.name}:'
            
        class_attrs = [add_indent(line, indent_num=1) for line in test_class.attributes]
        class_attrs = '\n'.join(class_attrs)
        if class_attrs != '':
            class_attrs = '\n\n' + class_attrs
        
        class_constructor = [add_indent(init_method, indent_num=1) for init_method in test_class.init]
        class_constructor = '\n\n'.join(class_constructor)
        if class_constructor != '':
            class_constructor = '\n\n' + class_constructor
        
        within_class_should_keep_function_content = '\n\n'.join([add_indent(i.content, indent_num=1) for i in within_class_should_keep_functions])
        if within_class_should_keep_function_content != '':
            within_class_should_keep_function_content = '\n\n' + within_class_should_keep_function_content
        
        indented_method = add_indent(truncated_test_method, indent_num=1)
    
        class_context = f'# Test class\n{class_definition}{class_attrs}{class_constructor}{within_class_should_keep_function_content}\n\n    # Test method\n{indented_method}'
    
    else:
        class_context = truncated_test_method

    test_skeleton = module_context + '\n\n' + class_context
    return test_skeleton


def add_prompt_cache(chatbot, prompt, response, prompt_cache_dict, type_inference_history):
    chat_history = chatbot.get_history(additional_history=type_inference_history)
    actual_prompt = chat_history + f"Question: {prompt}\n"
    prompt_cache_dict[actual_prompt] = response


def check_if_properly_triggered(focal_test_res, test_cmd, focal_dir, trigger_contents):
    real_trigger_methods = []
    all_chain_methods = extract_method_chain_from_test_output(focal_test_res, test_cmd, focal_dir)
    all_failed_methods = extract_method_from_file_and_line(all_chain_methods)
    for each_chain in all_failed_methods:  
        real_trigger_method = each_chain[-1][1]
        real_trigger_methods.append(real_trigger_method.content)
        
    if real_trigger_methods and not any([i in trigger_contents for i in real_trigger_methods]):
        return False
    
    return True
    


def run_single_method(origin_test_file, origin_test_func, proj_name, bug_id, focal_method, focal_dir, fixed_dir, env_name, debugging_mode, prompt_cache_dict, tmp_dir_for_test, type_inference_history, run_dataset, triggering_method, called_name_chain, run_rethink, run_type):
    all_imports, all_fields, all_classes, module_name = construct_module_context(focal_method)
    
    module_path = focal_method.belong_module.module_path
    focal_module_dir = focal_dir + '/' if 'ansible' not in focal_dir else focal_dir + '/lib/'
    fixed_module_dir = fixed_dir + '/' if 'ansible' not in fixed_dir else fixed_dir + '/lib/'
    
    if run_type == 'buggy':
        module_relative_dir = module_path.replace(focal_module_dir, '').replace('.py', '').replace('/', '.')
    elif run_type == 'non_buggy':
        module_relative_dir = module_path.replace(fixed_module_dir, '').replace('.py', '').replace('/', '.')
    
    class_context = construct_class_context(focal_method)
    
    if run_dataset == 'typebugs':
        real_bug_id = bug_id.split('_')[0]
        used_framework = test_related_info[proj_name][real_bug_id]['used_framework']
        py_version = test_related_info[proj_name][real_bug_id]['py_version']
    else:
        used_framework = test_related_info[proj_name][bug_id]['used_framework']
        py_version = test_related_info[proj_name][bug_id]['py_version']
    
    origin_test_file_location = os.path.join(focal_dir, origin_test_file)
    test_skeleton = construct_test_skeleton(origin_test_file_location, origin_test_func)
    
    system_prompt = (
        "You are an intelligent and expert programming assistant that helps users write high-quality Python unit tests.\n"
        "You will first be provided with one or more rounds of type inference results. These describe the types, fields, methods, "
        "and built-in characteristics of parameters involved in a chain of function calls, inferred through their usage.\n"
        "After the type inference phase is complete, you will be provided with the focal function's code context.\n"
        "Your task is to generate meaningful and thorough Python unit tests for the focal function using the combined context "
        "from type inference and the function implementation.\n"
        "When generating code, always format it using triple backticks and the 'python' tag, like this: ```python <code> ```.\n"
        "Make sure the generated tests are syntactically correct, logically sound, and cover normal behavior, edge cases, "
        "and valid inputs based on the inferred types and structure."
    )
    
    stage1_prompt = f'The focal function is \"{focal_method.name}\", it is located in module {module_relative_dir}, and its context is as follows: \n```\n{all_imports}\n\n{all_fields}\n\n{class_context}\n```\n\nPlease infer the intension of the \"{focal_method.name}\"'
    
    # # all_refined_imports = all_imports.split('\n')
    # all_refined_imports = []
    # # all_refined_imports.append(f'from .{module_name} import *')
    # # all_refined_imports.append(f'from . import {module_name}')
    
    # # all_imports_from_focal = [f'from .{module_name} import {i}' for i in all_classes]
    # # all_refined_imports = all_refined_imports + all_imports_from_focal
    # all_refined_imports.append(f'import {module_relative_dir}')
    # all_refined_imports.append(f'from {module_relative_dir} import *')

    # all_refined_imports_str = '\n'.join(all_refined_imports)
    if run_dataset == 'typebugs':
        test_function_description = f'\nThe test function to be completed is \'{origin_test_func}\'.\n' if origin_test_func != '' else ''
        stage2_prompt = f'\n The test file for the above mentioned method is:\n ```\n {test_skeleton}\n```\n{test_function_description}The focal method is \'{focal_method.name}\'.\n\nPlease complete the test function and provide the complete executable test file. Do not use `with pytest.raises(TypeError)` or `try-except` to catch the error. Instead, let the test fail naturally when a TypeError is raised. Do not omit any code in the provided test file.'
    else:
        stage2_prompt = f'\nThe test file for the above mentioned method is:\n ```\n {test_skeleton}\n```\n\nThe test function to be completed is \'{origin_test_func}\'.\nThe focal method is \'{focal_method.name}\'.\n\nPlease complete the test function and provide the complete executable test file. Do not use `with pytest.raises(TypeError)` or `try-except` to catch the error. Instead, let the test fail naturally when a TypeError is raised. Do not omit any code in the provided test file.'

    print('Querying the LLM...')
    logger.debug('Querying the LLM...')
    
    if not debugging_mode:
        chat_bot = ChatBot(api_key, base_url, model, system_prompt, temperature)
        if stage1_prompt in prompt_cache_dict.keys():
            logger.debug('Stage 1 hit the cache!')
            stage1_response = prompt_cache_dict.get(stage1_prompt)
            chat_bot.add_history(stage1_prompt, stage1_response)
        else:
            stage1_response = chat_bot.chat_with_additional_history(stage1_prompt, prefix_output='', add_to_history=True, additional_history=type_inference_history)
            prompt_cache_dict[stage1_prompt] = stage1_response
        
        new_prop = f"{stage1_prompt}\n{stage1_response}\n{stage2_prompt}"
        if new_prop in prompt_cache_dict.keys():
            logger.debug('Stage 2 hit the cache!')
            stage2_response = prompt_cache_dict.get(new_prop)
            chat_bot.add_history(stage2_prompt, stage2_response)
        else:
            stage2_response = chat_bot.chat_with_additional_history(stage2_prompt, prefix_output='', add_to_history=True, additional_history=type_inference_history)
            prompt_cache_dict[new_prop] = stage2_response
        
        # actual_stage1_prompt = chat_bot.get_history(additional_history=type_inference_history) + f"Question: {stage1_prompt}\n"
        # if actual_stage1_prompt in prompt_cache_dict.keys():
        #     logger.debug('Stage 1 hit the cache!')
        #     stage1_response = prompt_cache_dict.get(actual_stage1_prompt)
        #     chat_bot.add_history(stage1_prompt, stage1_response)
        # else:
        #     stage1_response = chat_bot.chat_with_additional_history(stage1_prompt, prefix_output='', add_to_history=True, additional_history=type_inference_history)
        # prompt_cache_dict[actual_stage1_prompt] = stage1_response
        
        # actual_stage2_prompt = chat_bot.get_history(additional_history=type_inference_history) + f"Question: {stage2_prompt}\n"
        # if actual_stage2_prompt in prompt_cache_dict.keys():
        #     logger.debug('Stage 2 hit the cache!')
        #     stage2_response = prompt_cache_dict.get(actual_stage2_prompt)
        #     chat_bot.add_history(stage2_prompt, stage2_response)
        # else:
        #     stage2_response = chat_bot.chat_with_additional_history(stage2_prompt, prefix_output='', add_to_history=True, additional_history=type_inference_history)
        #     # add_prompt_cache(chat_bot, stage2_prompt, stage2_response, prompt_cache_dict, type_inference_history)
        # prompt_cache_dict[actual_stage2_prompt] = stage2_response
    else:
        stage1_prompt = ''
        stage1_response =  ''
        stage2_response = example_response
    
    print('Get the response!')
    logger.debug('Get the response!')
    
    with open(prompt_cache, 'wb') as f:
        pickle.dump(prompt_cache_dict, f)
    
    code_content, test_cases = reindent_model_output(stage2_response)
    code_content = change_assert_to_pass_in_test(code_content)

    new_test_file = '/'.join(origin_test_file.split('/')[:-1]) + f'/test_{focal_method.name}_tttmp.py'
    
    focal_test_res, fixed_test_res, focal_stderr = execute_test(code_content, new_test_file, focal_method, used_framework, env_name, tmp_dir_for_test, focal_dir, fixed_dir)

    triggered, focal_type_error, fixed_type_error, focal_passed, fixed_passed = is_triggered(focal_test_res, fixed_test_res)
    logger.debug(f'focal type error: {focal_type_error}, focal passed: {focal_passed}')
    logger.debug(f'fixed type error: {fixed_type_error}, fixed passed: {fixed_passed}')
    
    if run_type == 'buggy':
        repair_condition = (not focal_type_error and not focal_passed)
    elif run_type == 'non_buggy':
        repair_condition = (not fixed_type_error and not fixed_passed)     
    
    if repair_condition:
        repair_tries = 0
        while repair_tries < 3 and repair_condition:
            logger.debug(f'Bug id {proj_name}-{bug_id}: repair try {repair_tries + 1}')
            
            if run_type == 'buggy':
                refactored_focal_test_res = refactor_test_res(focal_test_res)
                error_msg = refactored_focal_test_res
            elif run_type == 'non_buggy':
                refactored_fixed_test_res = refactor_test_res(fixed_test_res)
                error_msg = refactored_fixed_test_res
            
            repair_prompt = f'The test file you provided is not working. It encounters unexpected errors. Please fix the test file and make it executable.\n\nThe error message is:\n```\n{error_msg}\n```\n\nPlease provide the complete fixed executable test file.'
            
            if repair_prompt in prompt_cache_dict.keys():
                repair_response = prompt_cache_dict.get(repair_prompt)
                logger.debug('Repair prompt hit the cache!')
                chat_bot.add_history(repair_prompt, repair_response)
            else:
                logger.debug('Repair prompt not in cache, querying the LLM...')
                logger.debug('Focal output: ' + error_msg)
                repair_response = chat_bot.chat(repair_prompt, prefix_output='', add_to_history=True)
                prompt_cache_dict[repair_prompt] = repair_response
                
            prompt_cache_dict[repair_prompt] = repair_response
            with open(prompt_cache, 'wb') as f:
                pickle.dump(prompt_cache_dict, f)
    
            code_content, test_cases = reindent_model_output(repair_response)
            code_content = change_assert_to_pass_in_test(code_content)
            
            new_test_file = '/'.join(origin_test_file.split('/')[:-1]) + f'/test_{focal_method.name}_tttmp.py'
    
            focal_test_res, fixed_test_res, focal_stderr = execute_test(code_content, new_test_file, focal_method, used_framework, env_name, tmp_dir_for_test, focal_dir, fixed_dir)

            triggered, focal_type_error, fixed_type_error, focal_passed, fixed_passed = is_triggered(focal_test_res, fixed_test_res)
            logger.debug(f'focal type error: {focal_type_error}, focal passed: {focal_passed}')
            logger.debug(f'fixed type error: {fixed_type_error}, fixed passed: {fixed_passed}')
            
            if run_type == 'buggy':
                repair_condition = (not focal_type_error and not focal_passed)
            elif run_type == 'non_buggy':
                repair_condition = (not fixed_type_error and not fixed_passed)
        
            repair_tries += 1
    
    if run_type == 'buggy':
        rethink_condition = (focal_type_error and run_rethink)
    elif run_type == 'non_buggy':
        rethink_condition = (fixed_type_error and run_rethink)
            
    # NOTE: if the error does not occcur in the expected focal method (the last method in the chain), then it needs checking
    if rethink_condition:
        if run_type == 'buggy':
            properly_triggered = check_if_properly_triggered(focal_test_res, used_framework, focal_dir, [triggering_method.content])
        elif run_type == 'non_buggy':
            properly_triggered = check_if_properly_triggered(fixed_test_res, used_framework, fixed_dir, [triggering_method.content])
            
        # NOTE: Use another angent to re-think whether this is a true positive or false positive 
        if not properly_triggered:
            verification_tries = 0

            type_verification_bot = ChatBot(verification_api_key, verification_base_url, verification_model, type_verification_system_prompt, verification_temperature)
            
            type_verification_bot.add_history('Below you will be provided the parameter tracing analysis', 'OK, I am ready')
            for single_parameter_step in type_inference_history:
                type_verification_bot.add_history(single_parameter_step['question'], single_parameter_step['answer'])
            
            semantic_verification_bot = ChatBot(verification_api_key, verification_base_url, verification_model, semantic_verification_system_prompt, verification_temperature)
            semantic_verification_bot.add_history('Below you will be provided the type analysis through a call chain', 'OK, I am ready')
            for single_parameter_step in type_inference_history:
                semantic_verification_bot.add_history(single_parameter_step['question'], single_parameter_step['answer'])
                
            coordinator_bot = ChatBot(verification_api_key, verification_base_url, verification_model, coordinator_system_prompt, verification_temperature)
            
            generation_bot = ChatBot(api_key, base_url, model, generation_system_prompt, temperature)
            
            
            # while verification_tries < 3 and not properly_triggered:
            logger.debug(f'Bug id {proj_name}-{bug_id}: verification try {verification_tries + 1}')
            
            if rethink_condition:
                if run_type == 'buggy':
                    refactored_focal_test_res = refactor_test_res(focal_test_res)
                elif run_type == 'non_buggy':
                    refactored_focal_test_res = refactor_test_res(fixed_test_res)
            
                type_consistency_user_prompt = construct_type_constraints_verification_prompt_non_buggy(focal_method, module_relative_dir, triggering_method, called_name_chain, code_content, refactored_focal_test_res)

                actual_type_verification_prompt = type_verification_bot.get_history() + f"Question: {type_consistency_user_prompt}\n"
                if actual_type_verification_prompt in prompt_cache_dict.keys():
                    logger.debug('Type verification prompt hit the cache!')
                    type_verification_response = prompt_cache_dict.get(actual_type_verification_prompt)
                else:
                    logger.debug('Querying type verification...')
                    logger.info(f'Focal test res: {refactored_focal_test_res}')
                    type_verification_response = type_verification_bot.chat(type_consistency_user_prompt, prefix_output='', add_to_history=False)
                    
                logger.info(f'Type verification response: {type_verification_response}')
                prompt_cache_dict[actual_type_verification_prompt] = type_verification_response

                with open(prompt_cache, 'wb') as f:
                    pickle.dump(prompt_cache_dict, f)

                semantic_user_prompt = construct_semantic_verification_prompt(focal_method, module_relative_dir, code_content, refactored_focal_test_res)
                
                actual_semantic_verification_prompt = semantic_verification_bot.get_history() + f"Question: {semantic_user_prompt}\n"
                if actual_semantic_verification_prompt in prompt_cache_dict.keys():
                    logger.debug('Semantic verification prompt hit the cache!')
                    semantic_verification_response = prompt_cache_dict.get(actual_semantic_verification_prompt)
                else:
                    logger.debug('Querying semantic verification...')
                    semantic_verification_response = semantic_verification_bot.chat(semantic_user_prompt, prefix_output='', add_to_history=False)
                    
                logger.info(f'Semantic verification response: {semantic_verification_response}')
                
                prompt_cache_dict[actual_semantic_verification_prompt] = semantic_verification_response
                with open(prompt_cache, 'wb') as f:
                    pickle.dump(prompt_cache_dict, f)
                
                coordinator_prompt = construct_coordinator_prompt(focal_method, module_relative_dir, code_content, type_verification_response, semantic_verification_response)
                
                actual_coordinator_prompt = coordinator_bot.get_history() + f"Question: {coordinator_prompt}\n"
                if actual_coordinator_prompt in prompt_cache_dict.keys():
                    logger.debug('Coordinator prompt hit the cache!')
                    coordinator_response = prompt_cache_dict.get(actual_coordinator_prompt)
                else:
                    logger.debug('Querying coordinator...')
                    coordinator_response = coordinator_bot.chat(coordinator_prompt, prefix_output='', add_to_history=False)
                    
                logger.info(f'Coordinator response: {coordinator_response}')
                prompt_cache_dict[actual_coordinator_prompt] = coordinator_response
                with open(prompt_cache, 'wb') as f:
                    pickle.dump(prompt_cache_dict, f)
                
                if 'true_positive' in coordinator_response.lower() or 'true positive' in coordinator_response.lower():
                    logger.debug('The LLM thinks it is a true positive!')
                    print(coordinator_response)
                    properly_triggered = True
                    
                    return {
                        'triggered': triggered,
                        'focal_type_error': focal_type_error,
                        'fixed_type_error': fixed_type_error,
                        'focal_passed': focal_passed,
                        'fixed_passed': fixed_passed,
                        'focal_method': focal_method.content,
                        'code_content': code_content,
                        'focal_test_res': focal_test_res,
                        'fixed_test_res': fixed_test_res,
                        'module_path': module_path,
                        'focal_module_dir': focal_module_dir,
                        'module_relative_dir': module_relative_dir, 
                    }
                else:
                    current_condition = 'The Re-think Agents thinks that the test file you provided is a false positive. It raises a TypeError, but it is not correct.'
                    verification_response = f'\nBelow is a detailed explanation of why this test is a false positive:\n{coordinator_response}\n\n'
            else:
                current_condition = 'The test file you provided does not raise a TypeError, but it should.'
                verification_response = ''
                
            repair_fp_prompt = construct_refine_prompt_non_buggy(current_condition, focal_method, triggering_method, called_name_chain, verification_response, code_content, refactored_focal_test_res)

            actual_repair_prompt = generation_bot.get_history(type_inference_history) + f"Question: {repair_fp_prompt}\n"
            if actual_repair_prompt in prompt_cache_dict.keys():
                repair_fp_response = prompt_cache_dict.get(actual_repair_prompt)
                generation_bot.add_history(repair_fp_prompt, repair_fp_response)
                logger.debug('FP Repair prompt hit the cache!')
            else:
                logger.debug('FP Repair prompt not in cache, querying the LLM...')
                repair_fp_response = generation_bot.chat_with_additional_history(repair_fp_prompt, prefix_output='', add_to_history=True, additional_history=type_inference_history)
                logger.debug('Get the response!')
            
            prompt_cache_dict[actual_repair_prompt] = repair_fp_response
            
            with open(prompt_cache, 'wb') as f:
                pickle.dump(prompt_cache_dict, f)
    
            code_content, test_cases = reindent_model_output(repair_fp_response)
            code_content = change_assert_to_pass_in_test(code_content)
            
            new_test_file = '/'.join(origin_test_file.split('/')[:-1]) + f'/test_{focal_method.name}_tttmp.py'
    
            focal_test_res, fixed_test_res, focal_stderr = execute_test(code_content, new_test_file, focal_method, used_framework, env_name, tmp_dir_for_test, focal_dir, fixed_dir)

            triggered, focal_type_error, fixed_type_error, focal_passed, fixed_passed = is_triggered(focal_test_res, fixed_test_res)
            logger.debug(f'focal type error: {focal_type_error}, focal passed: {focal_passed}')
            logger.debug(f'fixed type error: {fixed_type_error}, fixed passed: {fixed_passed}')
            
            verification_tries += 1

            if run_type == 'buggy':
                rethink_condition = (focal_type_error and run_rethink)
                properly_triggered = check_if_properly_triggered(focal_test_res, used_framework, focal_dir, [triggering_method.content])
            elif run_type == 'non_buggy':
                rethink_condition = (fixed_type_error and run_rethink)
                properly_triggered = check_if_properly_triggered(fixed_test_res, used_framework, fixed_dir, [triggering_method.content])
            
            if rethink_condition and properly_triggered:
                logger.debug('Pass the properly triggered check!')
                return {
                    'triggered': triggered,
                    'focal_type_error': focal_type_error,
                    'fixed_type_error': fixed_type_error,
                    'focal_passed': focal_passed,
                    'fixed_passed': fixed_passed,
                    # 'properly_triggered': properly_triggered if 'properly_triggered' in locals() else False,
                    'focal_method': focal_method.content,
                    'code_content': code_content,
                    'focal_test_res': focal_test_res,
                    'fixed_test_res': fixed_test_res,
                    'module_path': module_path,
                    'focal_module_dir': focal_module_dir,
                    'module_relative_dir': module_relative_dir, 
                    # 'stage1_prompt': stage1_prompt,
                    # 'stage2_prompt': stage2_prompt,
                    # 'stage1_response': stage1_response,
                    # 'stage2_response': stage2_response
                }

        if not properly_triggered:
            focal_type_error = False
            fixed_type_error = False

    return {
        'triggered': triggered,
        'focal_type_error': focal_type_error,
        'fixed_type_error': fixed_type_error,
        'focal_passed': focal_passed,
        'fixed_passed': fixed_passed,
        'properly_triggered': properly_triggered if 'properly_triggered' in locals() else False,
        'focal_method': focal_method.content,
        'code_content': code_content,
        'focal_test_res': focal_test_res,
        'fixed_test_res': fixed_test_res,
        'module_path': module_path,
        'focal_module_dir': focal_module_dir,
        'module_relative_dir': module_relative_dir, 
        'stage1_prompt': stage1_prompt,
        'stage2_prompt': stage2_prompt,
        'stage1_response': stage1_response,
        'stage2_response': stage2_response
        # 'processed_imports': processed_imports,
        # 'all_refined_imports': all_refined_imports
    }


def execute_test(test_content, relative_test_file, focal_method, used_framework, env_name, tmp_dir_for_test, focal_proj_dir, fixed_proj_dir):
    belong_module = focal_method.belong_module
    
    module_name = belong_module.name.replace('.py', '')
    module_path = belong_module.module_path
    
    focal_module_dir = focal_proj_dir
    fixed_module_dir = focal_module_dir.replace(focal_proj_dir, fixed_proj_dir)
    
    module_tmp_dir = os.path.join(tmp_dir_for_test, module_name)
    python_bin = f'{conda_base}/envs/{env_name}/bin/python'
    
    test_case = test_content
    
    test_file, test_content = write_test_file(focal_module_dir, relative_test_file, test_case)

    focal_run_output, focal_stdout, focal_stderr = run_test_and_collect_cov_lightweight(focal_module_dir, test_file, relative_test_file, used_framework, module_tmp_dir, python_bin)
    
    # fixed test
    test_file, test_content = write_test_file(fixed_module_dir, relative_test_file, test_case)
    
    fixed_run_output, fixed_stdout, fixed_stderr = run_test_and_collect_cov_lightweight(fixed_module_dir, test_file, relative_test_file, used_framework, module_tmp_dir, python_bin)
    
    return focal_run_output, fixed_run_output, focal_stderr
    

def load_type_inference_history(proj_name, bug_id, chain_index, type_inference_result_dir):
    corresponding_chain_res = os.path.join(type_inference_result_dir, f'{proj_name}_{bug_id}_chain_{chain_index}.jsonl')
    if not os.path.exists(corresponding_chain_res):
        return []
    with open(corresponding_chain_res, 'r') as f:
        all_chain_res = f.readlines()
    all_chain_res = [json.loads(i) for i in all_chain_res]
    history = []
    for i in all_chain_res:
        history.append({"question":i['user_prompt'],"answer":i['llm_output']})
    return history