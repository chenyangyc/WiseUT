import os
import json
import pickle
import logging
from pathlib import Path
from collections import defaultdict
from core.chatbot import ChatBot
from data.configurations import example_prompt_1, example_prompt_2, example_response_1, example_response_2, iterative_infer_system_prompt, infer_system_prompt, infer_instruction_prompt, example_response, verification_api_key, verification_base_url, verification_model, verification_temperature,semantic_verification_system_prompt, coordinator_system_prompt, generation_system_prompt, type_verification_system_prompt, api_key, base_url, model, temperature, code_base, conda_base, project_configs, logger, expr_identifier

from utils.file_parse import change_assert_to_pass_in_test, refactor_test_res
from utils.run_test_util import write_test_file, run_test_and_collect_cov_lightweight, is_triggered
from utils.construct_prompts import construct_type_constraints_verification_prompt_non_buggy,construct_semantic_verification_prompt, construct_refine_prompt_non_buggy, construct_coordinator_prompt
from our_chain_gen import construct_module_context, construct_class_context, construct_test_skeleton, reindent_model_output, check_if_properly_triggered


def generate_seperate_prompt(function_info, backward=True):
    # 利用被调用函数的type结果
    if backward:
        belong_function_name_info = f'The function belongs to class `{function_info["belong_class_name"]}`.\n' if function_info['belong_class_name'] else ''
        belong_function_init_info = f'The constructor of the class is:\n```python\n{function_info["belong_class_init"]}\n```\n' if function_info['belong_class_init'] else ''

        if function_info.get('split_result', 'false') == 'success':
            argument_info = f'Arguments passed to this called function: `{function_info["called_arguments"]}`.\n'
        else:
            argument_info = f''
        
        backward_info = f'''You are provided with type information for the arguments of the called function. Use this as backward-flow type information to guide your inference in the caller.
Function being called: `{function_info['called_function_name']}`.

Arguments defined in this called function: `{function_info['called_function_parameter']}`.
{argument_info}{belong_function_name_info}{belong_function_init_info}

Known type information for this called function's parameters:
{function_info['known_type_info']}'''

    else:
        backward_info = ''
    
    user_prompt = f'''The function `{function_info['function_name']}` needs to be analyzed is as below:
```python
{function_info['function_content']}
```
{backward_info}
Please infer the type, fields, methods, and built-in characteristics of each parameter based on its usage within the function `{function_info['function_name']}`, and using any constraints from the callee if available. Provide the result in JSON format. Please only output the JSON result without any additional explanations or comments.'''

    return user_prompt


def generate_type_seperate_prompt(call_chain, inference_prompt_cache_dict, infered_results):
    logger.debug(f'Activate non-error-seeking agent for type constraint analysis')
    for i in range(len(call_chain) - 1, 0, -1):
        backward = False if i == len(call_chain) - 1 else True
        
        chatbot = ChatBot(api_key, base_url, model, infer_system_prompt, temperature)
        chatbot.add_history(infer_instruction_prompt, 'Sure, please provide the actual function code snippet.')
        chatbot.add_history(example_prompt_1, example_response_1)
        chatbot.add_history(example_prompt_2, example_response_2)
        
        user_prompt = generate_seperate_prompt(call_chain[i], backward)
        
        # chatbot.show_history()
        chat_history = chatbot.get_history()
        actual_prompt = f'{chat_history}\n{user_prompt}'
        
        if actual_prompt in inference_prompt_cache_dict:
            logger.debug(f'Prompt already exists in cache, using cached response...')
            response = inference_prompt_cache_dict[actual_prompt]
        else:
            # logger.debug(f'Calling LLM...')
            response = chatbot.chat(user_prompt, '', True)
            inference_prompt_cache_dict[actual_prompt] = response
            # logger.debug(f'Get the response...')

        call_chain[i]['llm_output'] = response
        call_chain[i - 1]['known_type_info'] = response
        
        called_function_name = call_chain[i]['called_function_name'] if backward else ''
        called_function_parameter = call_chain[i]['called_function_parameter'] if backward else ''
        if call_chain[i].get('split_result', 'false') == 'success':
            called_arguments = call_chain[i]['called_arguments'] 
        else:
            called_arguments = ''
        infered_results.append({
            'function_name': call_chain[i]['function_name'],
            'function_content': call_chain[i]['function_content'],
            'function_parameter': call_chain[i]['function_parameter'],
            'called_function_name': called_function_name,
            'called_function_parameter': called_function_parameter,
            'called_arguments': called_arguments,
            'user_prompt': user_prompt,
            'llm_output': response
        })
    pass


def generate_iterative_prompt(function_info, called_name_chain, backward=True):
    # 利用被调用函数的type结果
    if backward:
        belong_function_name_info = f'The function belongs to class `{function_info["belong_class_name"]}`.\n' if function_info['belong_class_name'] else ''
        belong_function_init_info = f'The constructor of the class is:\n```python\n{function_info["belong_class_init"]}\n```\n' if function_info['belong_class_init'] else ''

        if function_info.get('split_result', 'false') == 'success':
            argument_info = f'Arguments passed to this called function: `{function_info["called_arguments"]}`.\n'
        else:
            argument_info = f''
        
        backward_info = f'''You are provided with type information for the arguments of the called function. Use this as backward-flow type information to guide your inference in the caller.
Function being called: `{function_info['called_function_name']}`.

Arguments defined in this called function: `{function_info['called_function_parameter']}`.
{argument_info}{belong_function_name_info}{belong_function_init_info}

Known type information for this called function's parameters:
{function_info['known_type_info']}'''

        user_prompt = f'''The function `{function_info['function_name']}` in the call chain is as below, it calls the `{function_info['called_function_name']}` function:
```python
{function_info['function_content']}
```
{backward_info}
Please infer the type, fields, methods, and built-in characteristics of each parameter based on its usage within the function `{function_info['function_name']}`, and using any constraints from the callee if available. Provide the result in JSON format. Please only output the JSON result without any additional explanations or comments. If the constraints can not be satisfied, return \"Unable to satisfy!\" and summarize as required in the system prompt.'''

    else:
        backward_info = ''

        user_prompt = f'''The function `{function_info['function_name']}` is the last function in a function call chain (`{called_name_chain}`). There is a `TypeError` in this function:
```python
{function_info['function_content']}
```
{backward_info}
Please infer the type, fields, methods, and built-in characteristics of each parameter based on its usage within the function `{function_info['function_name']}` to trigger the TypeError. Provide the result in JSON format. Please only output the JSON result without any additional explanations or comments.'''

    return user_prompt


def generate_type_iterative_prompt(call_chain, inference_prompt_cache_dict, infered_results):
    infer_rounds = 0
    infer_completed = False
    previous_summarized_failures = []
    
    called_name_chain = ' -> '.join([single_func['function_name'] for single_func in call_chain])

    while infer_rounds < 3 and not infer_completed:
        logger.debug(f'Round {infer_rounds} of type inference...')
        logger.debug(f'Activate error-seeking agent for type constraint analysis')
        temp_infer_process = []
        chatbot = ChatBot(api_key, base_url, model, iterative_infer_system_prompt, temperature)
        chatbot.add_history(example_prompt_1, example_response_1)
        chatbot.add_history(example_prompt_2, example_response_2)
        
        summarized_failure = '\n'.join(previous_summarized_failures)
        if summarized_failure != '':
            chatbot.add_history(f'Here are some previous rounds of type inference that encounter unsatisfiable constraints, as summarized below: {summarized_failure}', 'OK. I will infer again and avoid the same failure.')
            
        for i in range(len(call_chain) - 1, 0, -1):
            backward = False if i == len(call_chain) - 1 else True
            
            user_prompt = generate_iterative_prompt(call_chain[i], called_name_chain, backward)
            
            # chatbot.show_history()
            chat_history = chatbot.get_history()
            actual_prompt = f'{chat_history}\n{user_prompt}'
            
            if actual_prompt in inference_prompt_cache_dict:
                logger.debug(f'Prompt already exists in cache, using cached response...')
                response = inference_prompt_cache_dict[actual_prompt]
                chatbot.add_history(user_prompt, response)
            else:
                # logger.debug(f'Calling LLM...')
                response = chatbot.chat(user_prompt, '', True)
                inference_prompt_cache_dict[actual_prompt] = response
                # logger.debug(f'Get the response.')

            if 'unable to satisfy' in response.lower():
                previous_summarized_failures.append('- ' + response)
                logger.debug(f'Round {infer_rounds} inference failed, unable to satisfy constraints. Summarized failure: {response}')
                infer_rounds += 1
                break

            call_chain[i]['llm_output'] = response
            call_chain[i - 1]['known_type_info'] = response
            
            called_function_name = call_chain[i]['called_function_name'] if backward else ''
            called_function_parameter = call_chain[i]['called_function_parameter'] if backward else ''
            if call_chain[i].get('split_result', 'false') == 'success':
                called_arguments = call_chain[i]['called_arguments'] 
            else:
                called_arguments = ''
                
            temp_infer_process.append({
                'function_name': call_chain[i]['function_name'],
                'function_content': call_chain[i]['function_content'],
                'function_parameter': call_chain[i]['function_parameter'],
                'called_function_name': called_function_name,
                'called_function_parameter': called_function_parameter,
                'called_arguments': called_arguments,
                'user_prompt': user_prompt,
                'llm_output': response
            })
        infered_results.extend(temp_infer_process)
        infer_completed = True
    pass


def run_single_method(origin_test_file, origin_test_func, proj_name, focal_method, focal_dir, fixed_dir, env_name, debugging_mode, prompt_cache_dict, tmp_dir_for_test, type_inference_history, triggering_method, called_name_chain, run_rethink, chain_identifier_hash):
    all_imports, all_fields, all_classes, module_name = construct_module_context(focal_method)
    
    module_path = str(focal_method.belong_module.module_path)
    focal_module_dir = focal_dir + '/' if 'ansible' not in focal_dir else focal_dir + '/lib/'
    module_relative_dir = module_path.replace(focal_module_dir, '').replace('.py', '').replace('/', '.')
    
    class_context = construct_class_context(focal_method)
    
    if 'luigi' in proj_name:
        used_framework = 'pytest'
    elif 'scrapy' in proj_name:
        used_framework = 'pytest'

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

    stage2_prompt = f'\nThe test file for the above mentioned method is:\n ```\n {test_skeleton}\n```\n\nThe test function to be completed is \'{origin_test_func}\'.\nThe focal method is \'{focal_method.name}\'.\n\nPlease complete the test function and provide the complete executable test file. Do not use `with pytest.raises(TypeError)` or `try-except` to catch the error. Instead, let the test fail naturally when a TypeError is raised. Do not omit any code in the provided test file.'

    # print('Querying the LLM...')
    logger.debug('Querying the LLM...')
    
    if not debugging_mode:
        chat_bot = ChatBot(api_key, base_url, model, system_prompt, temperature)
        # if stage1_prompt in prompt_cache_dict.keys():
        #     logger.debug('Stage 1 hit the cache!')
        #     stage1_response = prompt_cache_dict.get(stage1_prompt)
        #     chat_bot.add_history(stage1_prompt, stage1_response)
        # else:
        #     stage1_response = chat_bot.chat_with_additional_history(stage1_prompt, prefix_output='', add_to_history=True, additional_history=type_inference_history)
        #     prompt_cache_dict[stage1_prompt] = stage1_response
        
        # new_prop = f"{stage1_prompt}\n{stage1_response}\n{stage2_prompt}"
        # if new_prop in prompt_cache_dict.keys():
        #     logger.debug('Stage 2 hit the cache!')
        #     stage2_response = prompt_cache_dict.get(new_prop)
        #     chat_bot.add_history(stage2_prompt, stage2_response)
        # else:
        #     stage2_response = chat_bot.chat_with_additional_history(stage2_prompt, prefix_output='', add_to_history=True, additional_history=type_inference_history)
        #     prompt_cache_dict[new_prop] = stage2_response
        actual_stage1_prompt = chat_bot.get_history(additional_history=type_inference_history) + f"Question: {stage1_prompt}\n"
        if actual_stage1_prompt in prompt_cache_dict.keys():
            logger.debug('Stage 1 hit the cache!')
            stage1_response = prompt_cache_dict.get(actual_stage1_prompt)
            chat_bot.add_history(stage1_prompt, stage1_response)
        else:
            stage1_response = chat_bot.chat_with_additional_history(stage1_prompt, prefix_output='', add_to_history=True, additional_history=type_inference_history)
        prompt_cache_dict[actual_stage1_prompt] = stage1_response
        
        actual_stage2_prompt = chat_bot.get_history(additional_history=type_inference_history) + f"Question: {stage2_prompt}\n"
        if actual_stage2_prompt in prompt_cache_dict.keys():
            logger.debug('Stage 2 hit the cache!')
            stage2_response = prompt_cache_dict.get(actual_stage2_prompt)
            chat_bot.add_history(stage2_prompt, stage2_response)
        else:
            stage2_response = chat_bot.chat_with_additional_history(stage2_prompt, prefix_output='', add_to_history=True, additional_history=type_inference_history)
        prompt_cache_dict[actual_stage2_prompt] = stage2_response
    else:
        stage1_prompt = ''
        stage1_response =  ''
        stage2_response = example_response
    
    # print('Get the response!')
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
    # logger.debug(f'Focal test res: {focal_test_res}')
    
    repair_condition = (not focal_type_error and not focal_passed)
    
    if repair_condition:
        logger.debug(f'Satisfies the repair condition, begin repairing...')
        repair_tries = 0
        while repair_tries < 3 and repair_condition:
            logger.debug(f'Repair try {repair_tries + 1}')

            refactored_focal_test_res = refactor_test_res(focal_test_res)
            error_msg = refactored_focal_test_res

            repair_prompt = f'The test file you provided is not working. It encounters unexpected errors. Please fix the test file and make it executable.\n\nThe error message is:\n```\n{error_msg}\n```\n\nPlease provide the complete fixed executable test file.'
            
            if repair_prompt in prompt_cache_dict.keys():
                repair_response = prompt_cache_dict.get(repair_prompt)
                logger.debug('Repair prompt hit the cache!')
                chat_bot.add_history(repair_prompt, repair_response)
            else:
                logger.debug('Repair prompt not in cache, querying the LLM...')
                # logger.debug('Focal output: ' + error_msg)
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

            repair_condition = (not focal_type_error and not focal_passed)
            repair_tries += 1
    
    rethink_condition = (focal_type_error and run_rethink)

    # NOTE: if the error does not occcur in the expected focal method (the last method in the chain), then it needs checking
    if rethink_condition:
        logger.debug(f'Satisfies the reflective validation condition, begin validating...')
        properly_triggered = check_if_properly_triggered(focal_test_res, used_framework, focal_dir, [triggering_method.content])
            
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
            logger.debug(f'Verification try {verification_tries + 1}')
            
            if rethink_condition:
                refactored_focal_test_res = refactor_test_res(focal_test_res)
                    
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
                        'chain_identifier_hash': chain_identifier_hash,
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

            rethink_condition = (focal_type_error and run_rethink)
            properly_triggered = check_if_properly_triggered(focal_test_res, used_framework, focal_dir, [triggering_method.content])
            
            if rethink_condition and properly_triggered:
                logger.debug('Pass the properly triggered check!')
                return {
                    'triggered': triggered,
                    'focal_type_error': focal_type_error,
                    'fixed_type_error': fixed_type_error,
                    'focal_passed': focal_passed,
                    'fixed_passed': fixed_passed,
                    'properly_triggered': properly_triggered if 'properly_triggered' in locals() else False,
                    'chain_identifier_hash': chain_identifier_hash,
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
        'chain_identifier_hash': chain_identifier_hash,
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
    

def find_corresponding_ast_node(call_chain, function_dict):
    ast_chain = []
    for single_function in call_chain:
        if 'split_result' in single_function.keys():
            if single_function['split_result'] == 'failure':
                return None
        
        function_name = single_function['function_name']
        function_content = single_function['function_content']
        
        corresponding_ast_node = None
        for candidate_func in function_dict.values():
            if function_name == candidate_func.name and function_content == candidate_func.content:
                corresponding_ast_node = candidate_func
                break
        
        if corresponding_ast_node is None:
            return None
        
        ast_chain.append(corresponding_ast_node)
    return ast_chain
    


def type_error_detection_entry():
    date_prefix = expr_identifier
    
    run_rethink = True
    debugging_mode = False
    
    base_res_dir = f'{code_base}/data/new_proj_res'
    os.makedirs(base_res_dir, exist_ok=True)
    
    for project_name, config in project_configs.items():
        date = f'{date_prefix}_{project_name}'
        
        src_path = config['src_path']
        base_module_name = config['base_module_name']
        project_path = config['project_path']

        project_focal_info_dir = f'{base_res_dir}/{project_name}'
        function_dict_save_path = Path(f'{project_focal_info_dir}/function_dict.pkl')
        all_called_chains_save_path = Path(f'{project_focal_info_dir}/called_chains.pkl')
        
        test_func_chain_save_path = Path(f'{project_focal_info_dir}/test_func_chains.pkl')
        
        progress_file = f'{project_focal_info_dir}/generation_done.pickle'
        
        iterative_res_base_dir = f'{base_res_dir}/{project_name}/iterative'
        seperate_res_base_dir = f'{base_res_dir}/{project_name}/seperate'
        
        iterative_infer_res_dir = f'{iterative_res_base_dir}/infered_results/{date}'
        seperate_infer_res_dir = f'{seperate_res_base_dir}/infered_results/{date}'
        
        iterative_generation_res_dir = f'{base_res_dir}/{project_name}/generated_results/error-seeking'
        seperate_generation_res_dir = f'{base_res_dir}/{project_name}/generated_results/non-error-seeking'
        
        os.makedirs(iterative_infer_res_dir, exist_ok=True)
        os.makedirs(seperate_infer_res_dir, exist_ok=True)
        os.makedirs(iterative_generation_res_dir, exist_ok=True)
        os.makedirs(seperate_generation_res_dir, exist_ok=True)
        
        with open(function_dict_save_path, 'rb') as f:
            function_dict = pickle.load(f)
        
        with open(all_called_chains_save_path, 'rb') as f:
            all_called_chains = pickle.load(f)
        
        if os.path.exists(progress_file):
            with open(progress_file, 'rb') as f:
                done_ans = pickle.load(f)
        else:
            done_ans = set()
        
        prompt_cache_dir = os.path.join(project_focal_info_dir, 'prompt_cache')
        os.makedirs(prompt_cache_dir, exist_ok=True)
            
        global prompt_cache
        prompt_cache = os.path.join(prompt_cache_dir, f'{date}.pkl')
        
        if os.path.exists(prompt_cache):
            with open(prompt_cache, 'rb') as fr:
                inference_prompt_cache_dict = pickle.load(fr)
        else:
            inference_prompt_cache_dict = defaultdict()

        tmp_dir_for_test = os.path.join(code_base, 'data', 'temp_dirs', 'new_projects', f'tmp_{date}')
        os.makedirs(tmp_dir_for_test, exist_ok=True)
        
        print(len(all_called_chains))

        all_test_func_chains = defaultdict(list)
        
        logger.debug(f'Extracting test chains...')
        if not os.path.exists(test_func_chain_save_path):
            for chain_index, single_call_chain in enumerate(all_called_chains):
                if len(single_call_chain) < 3:
                    continue
                
                ast_call_chain = find_corresponding_ast_node(single_call_chain, function_dict)
                
                if ast_call_chain is None:
                    continue
                
                if 'test' not in ast_call_chain[0].fully_qualified_name:
                    continue
                
                test_func = ast_call_chain[0]
                all_test_func_chains[test_func].append({
                    'split_call_chain': single_call_chain,
                    'ast_node_chain': ast_call_chain,
                })

            with open(test_func_chain_save_path, 'wb') as f:
                pickle.dump(all_test_func_chains, f)
        else:
            with open(test_func_chain_save_path, 'rb') as f:
                all_test_func_chains = pickle.load(f)
        
        total_chain_num = sum([len(i) for i in all_test_func_chains.values()])
        logger.debug(f'Test chains loaded, all test functions: {len(all_test_func_chains.keys())}, total chains: {total_chain_num}')
        
        
        for test_func, test_chains in all_test_func_chains.items():
            logger.debug(f'Processing test function: {test_func.fully_qualified_name}')
            if len(test_chains) < 10:
                continue
            for test_chain in test_chains[10:20]:
                single_call_chain = test_chain['split_call_chain']
                ast_call_chain = test_chain['ast_node_chain']
                
                chain_identifier = '-'.join([i['function_content'] for i in single_call_chain])
                chain_identifier_hash = str(hash(chain_identifier))

                if chain_identifier in done_ans:
                    logger.debug(f"Skip: Chain {chain_identifier_hash} already processed. Skipping.")
                    continue
                                
                logger.debug(f'Processing call chain id: {chain_identifier_hash}, length: {len(single_call_chain)}')
                
                try:
                    # logger.debug(f'Begin iterative type inference...') 
                    iterative_infered_results = []
                    generate_type_iterative_prompt(single_call_chain, inference_prompt_cache_dict, iterative_infered_results)

                    # logger.debug(f'Begin seperate type inference...') 
                    seperate_infered_results = []
                    generate_type_seperate_prompt(single_call_chain, inference_prompt_cache_dict, seperate_infered_results)
                    
                    test_chain['iterative_infered_results'] = iterative_infered_results
                    test_chain['seperate_infered_results'] = seperate_infered_results
                    
                    with open(f'{iterative_infer_res_dir}/chain_{chain_identifier_hash}.jsonl', 'a') as f:
                        for result in iterative_infered_results:
                            f.write(json.dumps(result) + '\n')
                    
                    with open(f'{seperate_infer_res_dir}/chain_{chain_identifier_hash}.jsonl', 'a') as f:
                        for result in seperate_infered_results:
                            f.write(json.dumps(result) + '\n')
                    
                    with open(prompt_cache, 'wb') as fw:
                        pickle.dump(inference_prompt_cache_dict, fw)
                    
                    iterative_type_history = []
                    for i in iterative_infered_results:
                        iterative_type_history.append({"question":i['user_prompt'],"answer":i['llm_output']})
                    
                    seperate_type_history = []
                    for i in seperate_infered_results:
                        seperate_type_history.append({"question":i['user_prompt'],"answer":i['llm_output']})
                    
                    logger.debug(f'Type inference completed, extracting focal method...') 
                    # NOTE: 推理完类型以后，使用该结果进行测试生成

                    focal_method = None
                    triggering_method = None
                    for focal_index, method in enumerate(ast_call_chain):
                        method_file = method.fully_qualified_name
                        method_obj = method
                        
                        if 'env' not in method_file and 'test' not in method_file:
                            focal_method = method_obj
                            break
                    
                    for method in reversed(ast_call_chain):
                        method_file = method.fully_qualified_name
                        method_obj = method
                        
                        if 'env' not in method_file and 'test' not in method_file:
                            triggering_method = method_obj
                            break

                    called_name_chain = ' -> '.join([single_func.name for single_func in ast_call_chain[focal_index:]])
                
                    if focal_method:
                        logger.debug(f'Focal method extracted, begin testing')
                        
                        focal_dir = project_path
                        fixed_dir = project_path
                        proj_real_name = project_name.replace('-master', '')
                        env_name = f'{proj_real_name}_new'
                        origin_test_file = test_func.belong_module.module_path.relative_to(focal_dir).as_posix()
                        origin_test_func = test_func.name
                        
                        logger.debug(f'Focal method: {focal_method.name}, triggering method: {triggering_method.name}')
                        logger.debug(f'Call chain {called_name_chain}')
                        logger.debug(f'Test file: {origin_test_file}, Test method name: {origin_test_func}')
                        logger.debug(f'Focal dir: {focal_dir}, Env name: {env_name}')
                        logger.debug(f'Iterative test generation...')
                        
                        iterative_test_result = run_single_method(origin_test_file, origin_test_func, project_name, focal_method, focal_dir, fixed_dir, env_name, debugging_mode, inference_prompt_cache_dict, tmp_dir_for_test, iterative_type_history, triggering_method, called_name_chain, run_rethink, chain_identifier_hash)
                        
                        test_chain['iterative_test_results'] = iterative_test_result
                    
                        with open(f'{iterative_generation_res_dir}/{date}.jsonl', 'a') as f:
                            f.write(json.dumps(iterative_test_result) + '\n')
                        
                        logger.debug(f'Separate test generation...')
                        seperate_test_result = run_single_method(origin_test_file, origin_test_func, project_name, focal_method, focal_dir, fixed_dir, env_name, debugging_mode, inference_prompt_cache_dict, tmp_dir_for_test, seperate_type_history, triggering_method, called_name_chain, run_rethink, chain_identifier_hash)
                        
                        test_chain['seperate_test_results'] = seperate_test_result

                        with open(f'{seperate_generation_res_dir}/{date}.jsonl', 'a') as f:
                            f.write(json.dumps(seperate_test_result) + '\n')
                            
                        done_ans.add(chain_identifier)
                    else:
                        logger.debug(f'Unable to find focal method, skipping testing.')
                        done_ans.add(chain_identifier)
                        continue
                    
                    
                    with open(test_func_chain_save_path, 'wb') as fw:
                        pickle.dump(all_test_func_chains, fw)
                    
                    with open(progress_file, 'wb') as f:
                        pickle.dump(done_ans, f)
                    
                    logger.debug(f'Processing completed for call chain: {chain_identifier_hash}')
                except Exception as e:
                    logger.error(f'Error processing this call chain {chain_identifier_hash}')
                    logger.error(e)
                    continue
                
    logger.debug('All processing completed.')


if __name__ == '__main__':
    date_prefix = expr_identifier
    
    run_rethink = True
    debugging_mode = False
    
    base_res_dir = f'{code_base}/data/new_proj_res'
    os.makedirs(base_res_dir, exist_ok=True)
    
    for project_name, config in project_configs.items():
        date = f'{date_prefix}_{project_name}'
        
        src_path = config['src_path']
        base_module_name = config['base_module_name']
        project_path = config['project_path']

        project_focal_info_dir = f'{base_res_dir}/{project_name}'
        function_dict_save_path = Path(f'{project_focal_info_dir}/function_dict.pkl')
        all_called_chains_save_path = Path(f'{project_focal_info_dir}/called_chains.pkl')
        
        test_func_chain_save_path = Path(f'{project_focal_info_dir}/test_func_chains.pkl')
        
        progress_file = f'{project_focal_info_dir}/generation_done.pickle'
        
        iterative_res_base_dir = f'{base_res_dir}/{project_name}/iterative'
        seperate_res_base_dir = f'{base_res_dir}/{project_name}/seperate'
        
        iterative_infer_res_dir = f'{iterative_res_base_dir}/infered_results/{date}'
        seperate_infer_res_dir = f'{seperate_res_base_dir}/infered_results/{date}'
        
        iterative_generation_res_dir = f'{iterative_res_base_dir}/generated_results'
        seperate_generation_res_dir = f'{seperate_res_base_dir}/generated_results'
        
        os.makedirs(iterative_infer_res_dir, exist_ok=True)
        os.makedirs(seperate_infer_res_dir, exist_ok=True)
        os.makedirs(iterative_generation_res_dir, exist_ok=True)
        os.makedirs(seperate_generation_res_dir, exist_ok=True)
        
        with open(function_dict_save_path, 'rb') as f:
            function_dict = pickle.load(f)
        
        with open(all_called_chains_save_path, 'rb') as f:
            all_called_chains = pickle.load(f)
        
        if os.path.exists(progress_file):
            with open(progress_file, 'rb') as f:
                done_ans = pickle.load(f)
        else:
            done_ans = set()
        
        prompt_cache_dir = os.path.join(project_focal_info_dir, 'prompt_cache')
        os.makedirs(prompt_cache_dir, exist_ok=True)
            
        prompt_cache = os.path.join(prompt_cache_dir, f'{date}.pkl')
        
        if os.path.exists(prompt_cache):
            with open(prompt_cache, 'rb') as fr:
                inference_prompt_cache_dict = pickle.load(fr)
        else:
            inference_prompt_cache_dict = defaultdict()

        tmp_dir_for_test = os.path.join(code_base, 'data', 'temp_dirs', 'new_projects', f'tmp_{date}')
        os.makedirs(tmp_dir_for_test, exist_ok=True)
        
        print(len(all_called_chains))

        all_test_func_chains = defaultdict(list)
        
        logger.debug(f'Extracting test chains...')
        if not os.path.exists(test_func_chain_save_path):
            for chain_index, single_call_chain in enumerate(all_called_chains):
                if len(single_call_chain) < 3:
                    continue
                
                ast_call_chain = find_corresponding_ast_node(single_call_chain, function_dict)
                
                if ast_call_chain is None:
                    continue
                
                if 'test' not in ast_call_chain[0].fully_qualified_name:
                    continue
                
                test_func = ast_call_chain[0]
                all_test_func_chains[test_func].append({
                    'split_call_chain': single_call_chain,
                    'ast_node_chain': ast_call_chain,
                })

            with open(test_func_chain_save_path, 'wb') as f:
                pickle.dump(all_test_func_chains, f)
        else:
            with open(test_func_chain_save_path, 'rb') as f:
                all_test_func_chains = pickle.load(f)
        
        total_chain_num = sum([len(i) for i in all_test_func_chains.values()])
        logger.debug(f'Test chains loaded, all test functions: {len(all_test_func_chains.keys())}, total chains: {total_chain_num}')
        
        
        for test_func, test_chains in all_test_func_chains.items():
            logger.debug(f'Processing test function: {test_func.fully_qualified_name}')
            if len(test_chains) < 10:
                continue
            for test_chain in test_chains[10:20]:
                single_call_chain = test_chain['split_call_chain']
                ast_call_chain = test_chain['ast_node_chain']
                
                chain_identifier = '-'.join([i['function_content'] for i in single_call_chain])
                chain_identifier_hash = str(hash(chain_identifier))

                if chain_identifier in done_ans:
                    logger.debug(f"Skip: Chain {chain_identifier_hash} already processed. Skipping.")
                    continue
                                
                logger.debug(f'Processing call chain id: {chain_identifier_hash}, length: {len(single_call_chain)}')
                
                try:
                    # logger.debug(f'Begin iterative type inference...') 
                    iterative_infered_results = []
                    generate_type_iterative_prompt(single_call_chain, inference_prompt_cache_dict, iterative_infered_results)

                    # logger.debug(f'Begin seperate type inference...') 
                    seperate_infered_results = []
                    generate_type_seperate_prompt(single_call_chain, inference_prompt_cache_dict, seperate_infered_results)
                    
                    test_chain['iterative_infered_results'] = iterative_infered_results
                    test_chain['seperate_infered_results'] = seperate_infered_results
                    
                    with open(f'{iterative_infer_res_dir}/chain_{chain_identifier_hash}.jsonl', 'a') as f:
                        for result in iterative_infered_results:
                            f.write(json.dumps(result) + '\n')
                    
                    with open(f'{seperate_infer_res_dir}/chain_{chain_identifier_hash}.jsonl', 'a') as f:
                        for result in seperate_infered_results:
                            f.write(json.dumps(result) + '\n')
                    
                    with open(prompt_cache, 'wb') as fw:
                        pickle.dump(inference_prompt_cache_dict, fw)
                    
                    iterative_type_history = []
                    for i in iterative_infered_results:
                        iterative_type_history.append({"question":i['user_prompt'],"answer":i['llm_output']})
                    
                    seperate_type_history = []
                    for i in seperate_infered_results:
                        seperate_type_history.append({"question":i['user_prompt'],"answer":i['llm_output']})
                    
                    logger.debug(f'Type inference completed, extracting focal method...') 
                    # NOTE: 推理完类型以后，使用该结果进行测试生成

                    focal_method = None
                    triggering_method = None
                    for focal_index, method in enumerate(ast_call_chain):
                        method_file = method.fully_qualified_name
                        method_obj = method
                        
                        if 'env' not in method_file and 'test' not in method_file:
                            focal_method = method_obj
                            break
                    
                    for method in reversed(ast_call_chain):
                        method_file = method.fully_qualified_name
                        method_obj = method
                        
                        if 'env' not in method_file and 'test' not in method_file:
                            triggering_method = method_obj
                            break

                    called_name_chain = ' -> '.join([single_func.name for single_func in ast_call_chain[focal_index:]])
                
                    if focal_method:
                        logger.debug(f'Focal method extracted, begin testing')
                        
                        focal_dir = project_path
                        fixed_dir = project_path
                        proj_real_name = project_name.replace('-master', '')
                        env_name = f'{proj_real_name}_new'
                        origin_test_file = test_func.belong_module.module_path.relative_to(focal_dir).as_posix()
                        origin_test_func = test_func.name
                        
                        logger.debug(f'Focal method: {focal_method.name}, triggering method: {triggering_method.name}')
                        logger.debug(f'Call chain {called_name_chain}')
                        logger.debug(f'Test file: {origin_test_file}, Test method name: {origin_test_func}')
                        logger.debug(f'Focal dir: {focal_dir}, Env name: {env_name}')
                        logger.debug(f'Iterative test generation...')
                        
                        iterative_test_result = run_single_method(origin_test_file, origin_test_func, project_name, focal_method, focal_dir, fixed_dir, env_name, debugging_mode, inference_prompt_cache_dict, tmp_dir_for_test, iterative_type_history, triggering_method, called_name_chain, run_rethink, chain_identifier_hash)
                        
                        test_chain['iterative_test_results'] = iterative_test_result
                    
                        with open(f'{iterative_generation_res_dir}/{date}.jsonl', 'a') as f:
                            f.write(json.dumps(iterative_test_result) + '\n')
                        
                        logger.debug(f'Separate test generation...')
                        seperate_test_result = run_single_method(origin_test_file, origin_test_func, project_name, focal_method, focal_dir, fixed_dir, env_name, debugging_mode, inference_prompt_cache_dict, tmp_dir_for_test, seperate_type_history, triggering_method, called_name_chain, run_rethink, chain_identifier_hash)
                        
                        test_chain['seperate_test_results'] = seperate_test_result

                        with open(f'{seperate_generation_res_dir}/{date}.jsonl', 'a') as f:
                            f.write(json.dumps(seperate_test_result) + '\n')
                            
                        done_ans.add(chain_identifier)
                    else:
                        logger.debug(f'Unable to find focal method, skipping testing.')
                        done_ans.add(chain_identifier)
                        continue
                    
                    
                    with open(test_func_chain_save_path, 'wb') as fw:
                        pickle.dump(all_test_func_chains, fw)
                    
                    with open(progress_file, 'wb') as f:
                        pickle.dump(done_ans, f)
                    
                    logger.debug(f'Processing completed for call chain: {chain_identifier_hash}')
                except Exception as e:
                    logger.error(f'Error processing this call chain {chain_identifier_hash}')
                    logger.error(e)
                    continue
                
    logger.debug('All processing completed.')