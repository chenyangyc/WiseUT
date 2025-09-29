from collections import defaultdict
from io import StringIO
import random

from data.Config import example_response, example_test, CONFIG
from core.base_test_program import TestProgram
from core.chatbot import ChatBot
from utils._coverage_utils import get_coverage_data
from utils._java_parser import parse_fields_from_class_code, parse_import_stmts_from_file_code


def select_examples(target_function, all_programs):
    selected_examples = list()
    line_range = set(target_function.line_range)

    chosen_covered_lines = set()
    # find the test with highest cov rate
    for single_case in all_programs:
        covered_all = get_coverage_data(single_case.coverage, target_function.belong_package.name, target_function.belong_file.file_name)
        if not covered_all:
            continue
        case_cover = covered_all.get('coverage_line')
        
        executed_lines = set(case_cover)
        function_executed_lines = executed_lines.intersection(line_range)
        function_executed_rate = len(function_executed_lines) / len(line_range)
        
        single_case.set_single_func_cov_lines(function_executed_lines)
        single_case.set_single_func_cov_rate(function_executed_rate)
    # 按cov从大到小排序
    sorted_by_cov = sorted(all_programs, key=lambda x: x.single_func_cov_rate)
    sorted_by_cov.reverse()
    
    for single_case in sorted_by_cov:
        if len(selected_examples) > 5:
            break
        if len(single_case.single_func_cov_lines - chosen_covered_lines) > 0:
            selected_examples.append(single_case)
            chosen_covered_lines = chosen_covered_lines.union(single_case.single_func_cov_lines)
    return selected_examples

def construct_all_context(target_method, module_content):
    target_content = target_method.content
    prev_context = module_content.split(target_content)[0] + '\n\n' + target_content
    return prev_context

def construct_context(target_method, name_2_class, chosen_chain=None):
    # TODO: called_functions / branch_related_called_methods
    # chosen_called_methods = target_method.called_functions
    chosen_called_methods = target_method.branch_related_called_methods
    
    if chosen_chain is None:
        chosen_calee_methods = set()
    else:
        chosen_calee_methods = set(chosen_chain)
    
    chosen_context_functions = chosen_called_methods.union(chosen_calee_methods)
    chosen_context_functions = chosen_context_functions.union({target_method})
    # all_classes = set([i.belong_class for i in chosen_context_functions])
    
    final_classes = defaultdict()
    
    # 加入目标方法
    if target_method.belong_class.name not in final_classes:
        final_classes[target_method.belong_class.name] = []
    final_classes[target_method.belong_class.name].append(target_method)
    
    # 加入分支相关的方法
    for method in chosen_called_methods:
        if method.belong_class.name not in final_classes:
            final_classes[method.belong_class.name] = []
        final_classes[method.belong_class.name].append(method)
        called_class = target_method.get_branch_related_called_class(method)
        
        while called_class != method.belong_class and called_class is not None:
            if called_class.name not in final_classes:
                final_classes[called_class.name] = []
            final_classes[called_class.name].append(method)
            called_class = called_class.father_class
    
    # 加入调用链信息
    if chosen_chain is not None:
        for index, method in enumerate(chosen_chain):
            if method.belong_class.name not in final_classes:
                final_classes[method.belong_class.name] = []
            final_classes[method.belong_class.name].append(method)
            
            if index + 1 < len(chosen_chain):
                called_method = chosen_chain[index + 1]
                called_class = method.get_called_class(called_method)
                while called_class != called_method.belong_class and called_class is not None:
                    if called_class.name not in final_classes:
                        final_classes[called_class.name] = []
                    final_classes[called_class.name].append(called_method)
                    called_class = called_class.father_class
    
    final_classes = {k: list(set(v)) for k, v in final_classes.items()}
    
    # 输出结果
    all_content = []

    for belong_class, functions in final_classes.items():
        class_content = ''
        class_content = StringIO(class_content)

        class_obj = name_2_class.get(belong_class)
        if class_obj is not None:
            
            # 不应该只取第一行
            class_declare = class_obj.content.split('{')[0] + '{\n'
            class_init = ''
            for init in class_obj.init:
                class_init += init.content + '\n'
            if class_init == '':
                class_init = None
            # class_init = class_obj.init[0] if class_obj.init else None
            class_fields = []
            class_fields.extend([i["declaration_text"] for i in parse_fields_from_class_code(class_obj.content)])
            class_fields_content = '\n'.join(class_fields)


            class_content.write(class_declare.strip() + '\n')
            class_content.write(class_fields_content.strip() + '\n')
            if class_init is not None:
                for i in class_init.split('\n'):
                    if i.strip() == '':
                        continue
                    class_content.write('    ' + i)
                    class_content.write('\n')
                    
            class_content.write('\n')
            
            
        for func in functions:
            func_content = func.content
            for i in func_content.split('\n'):
                if i.strip() == '':
                    continue
                class_content.write('    ' + i)
                class_content.write('\n')
            class_content.write('\n')
            pass
        all_content.append(class_content.getvalue())
        all_content.append('}\n')
        class_content.close()
        
    if target_method.return_class is not None:
        class_obj = target_method.return_class
        class_content = class_obj.content
        class_content = StringIO(class_content)
        
        all_content.append(class_content.getvalue())
        all_content.append('}\n')
        class_content.close()

    final_context = '\n'.join(all_content)
    return final_context

def construct_call_chain_info(chosen_chain):
    chain_func_names = [single_func.name for single_func in chosen_chain if single_func.name != '__init__']
    return '->'.join(chain_func_names)

def construct_summarize_function_prompt(target_method, module_name, context):
    func_name = target_method.name
    prompt = (
        f"There is a java function '{func_name}' in module {module_name}. "
        f"A simplified version of this module is \n```\n{context}\n```\n"
        # f"The information of the function is \n```\n{context}\n```\n"
        f"What is the functionality of the function? Do not write any unit tests in your response. "
    )
    return prompt

# 在原有的基础上，给prompt加入了import信息，避免导包错误
def construct_summarize_function_prompt_add_import(target_method, module_name, context):
    func_name = target_method.name
    imports = parse_import_stmts_from_file_code(target_method.belong_file.content)
    imports_content = '\n'.join(imports)
    prompt = (
        f"There is a java function '{func_name}' in module {module_name}. "
        f"The import statements of the module are \n```\n{imports_content}\n```\n"
        f"A simplified version of this module is \n```\n{context}\n```\n"
        # f"The information of the function is \n```\n{context}\n```\n"
        f"What is the functionality of the function? Do not write any unit tests in your response. "
    )
    return prompt

def construct_prompt_from_direct_program(target_method, test_programs):
    func_name = target_method.name
    
    line_range = list(target_method.line_range)
    covered_lines = list(target_method.covered_lines)
    start_num = min(line_range)
    line_range = [i - start_num + 1 for i in line_range]
    line_range.sort()
    covered_lines = [i - start_num + 1 for i in covered_lines]
    covered_lines_info = ', '.join([str(i) for i in covered_lines])

    # test_program_info = '\n'.join([f'```\n{test_program.content.strip()}\n```' for test_program in test_programs])
    test_program_info = ''
    for test_program in test_programs:
        t_content = test_program.content.strip()
        case = '```' + t_content.split('@Test(timeout = 4000)')[-1][:-1] + '```' + '\n'
        test_program_info += case
    # test_program_info = '\n'.join([f'```\n{test_program.content.strip().split('@Test(timeout = 4000)')[-1][:-1]}\n```' for test_program in test_programs])
    
    if len(test_programs) > 1:
        prompt = (
            f"The test cases below is designed to test the function '{func_name}'. They can cover different part of the function.\n"
            f"The contents of the test cases are \n{test_program_info}\n"
            f"The function '{func_name}' is defined in the line {line_range[0]} to {line_range[-1]}. "
            f"The test cases cover the lines {covered_lines_info}.\n"
            f"Please generate new test cases that cover different scenarios or edge cases.\n"
            f"Ensure that you have an adequate number of tests, but limit yourself to no more than four test cases, and group similar tests within the same test method whenever possible. "
            f"The code should be self-contained and complete. Do not add new classes and interfaces. Do not modify the import statements. "
            # f"Your code format should be consistent with the provided test programs. " 
        )
    else:
        prompt = (
            f"The test case below is designed to test the function '{func_name}' and can only cover part of it. \n"
            f"The content of the test case is \n{test_program_info}\n"
            f"The function '{func_name}' is defined in the line {line_range[0]} to {line_range[-1]}. "
            f"The test cases cover the lines {covered_lines_info}. \n"
            f"Please generate new test cases that cover different scenarios or edge cases. \n"
            f"Ensure that you have an adequate number of tests, but limit yourself to no more than four test cases, and group similar tests within the same test method whenever possible. "
            f"The code should be self-contained and complete. Do not add new classes and interfaces. Do not modify the import statements. "
            # f"Your code format should be consistent with the provided test programs. " 
        )

    return prompt

def construct_prompt_from_calee_program(target_method, test_programs, chosen_chain):
    func_name = target_method.name
    # test_program_info = '\n'.join([f'```\n{test_program.content.strip()}\n```' for test_program in test_programs])
    
    line_range = list(target_method.line_range)
    covered_lines = list(target_method.covered_lines)
    start_num = min(line_range)
    line_range = [i - start_num + 1 for i in line_range]
    line_range.sort()
    covered_lines = [i - start_num + 1 for i in covered_lines]
    covered_lines_info = ', '.join([str(i) for i in covered_lines])
    
    test_program_info = ''
    for test_program in test_programs:
        t_content = test_program.content.strip()
        case = '```' + t_content.split('@Test(timeout = 4000)')[-1][:-1] + '```' + '\n'
        test_program_info += case
    # TODO: 建立更好的 call chain 的信息
    call_chain_info = construct_call_chain_info(chosen_chain)
    
    if len(test_programs) > 1:
        prompt = (
            f"The test programs below may cover different part of the function '{func_name}' through the call chain {call_chain_info}. "
            f"The contents of the test programs are \n{test_program_info}\n"
            f"The function '{func_name}' is defined in the line {line_range[0]} to {line_range[-1]}. "
            f"The test programs cover the lines {covered_lines_info}. "
            f"Please generate new test programs that cover different scenarios or edge cases. "
            f"Ensure that you have an adequate number of tests, but limit yourself to no more than four test cases, and group similar tests within the same test method whenever possible. "
            f"The code should be self-contained and complete. Do not add new classes and interfaces. Do not modify the import statements. "
            # f"Your code format should be consistent with the provided test programs. " 
        )
    else:
        prompt = (
            f"The test program below may test the function '{func_name}' through the call chain {call_chain_info}. "
            f"The content of the test program is \n{test_program_info}\n"
            f"The function '{func_name}' is defined in the line {line_range[0]} to {line_range[-1]}. "
            f"The test programs cover the lines {covered_lines_info}. "
            f"Please generate new test programs that cover different scenarios or edge cases. "
            f"Ensure that you have an adequate number of tests, but limit yourself to no more than four test cases, and group similar tests within the same test method whenever possible. "
            f"The code should be self-contained and complete. Do not add new classes and interfaces. Do not modify the import statements. "
            # f"Your code format should be consistent with the provided test programs. " 
        )
    return prompt

def construct_prompt_from_covered_program(target_method, test_programs, chosen_chain):
    func_name = target_method.name
    # test_program_info = '\n'.join([f'```\n{test_program.content.strip()}\n```' for test_program in test_programs])
    
    line_range = list(target_method.line_range)
    covered_lines = list(target_method.covered_lines)
    start_num = min(line_range)
    line_range = [i - start_num + 1 for i in line_range]
    line_range.sort()
    covered_lines = [i - start_num + 1 for i in covered_lines]
    covered_lines_info = ', '.join([str(i) for i in covered_lines])
    
    test_program_info = ''
    for test_program in test_programs:
        t_content = test_program.content.strip()
        case = '```' + t_content.split('@Test(timeout = 4000)')[-1][:-1] + '```' + '\n'
        test_program_info += case
    # TODO: 建立更好的 call chain 的信息
    if chosen_chain is None:
        call_chain_info = target_method.name
    else:
        call_chain_info = construct_call_chain_info(chosen_chain)
    
    if len(test_programs) > 1:
        prompt = (
            f"The test programs below may cover different part of the function '{func_name}' through the call chain {call_chain_info}. "
            f"The contents of the test programs are \n{test_program_info}\n"
            f"The function '{func_name}' is defined in the line {line_range[0]} to {line_range[-1]}. "
            f"The test programs cover the lines {covered_lines_info}. "
            f"Please generate new test programs that cover different scenarios or edge cases. "
            f"Ensure that you have an adequate number of tests, but limit yourself to no more than four test cases, and group similar tests within the same test method whenever possible. "
            f"The code should be self-contained and complete. Do not add new classes and interfaces. Do not modify the import statements. "
            # f"Your code format should be consistent with the provided test programs. " 
        )
    else:
        prompt = (
            f"The test program below may test the function '{func_name}' through the call chain {call_chain_info}. "
            f"The content of the test program is \n{test_program_info}\n"
            f"The function '{func_name}' is defined in the line {line_range[0]} to {line_range[-1]}. "
            f"The test programs cover the lines {covered_lines_info}. "
            f"Please generate new test programs that cover different scenarios or edge cases. "
            f"Ensure that you have an adequate number of tests, but limit yourself to no more than four test cases, and group similar tests within the same test method whenever possible. "
            f"The code should be self-contained and complete. Do not add new classes and interfaces. Do not modify the import statements. "
            # f"Your code format should be consistent with the provided test programs. " 
        )
    return prompt

def construct_prompt_from_scratch(target_method, chosen_chains = None):
    func_name = target_method.name
    
    line_range = list(target_method.line_range)
    covered_lines = list(target_method.covered_lines)
    start_num = min(line_range)
    line_range = [i - start_num + 1 for i in line_range]
    line_range.sort()
    covered_lines = [i - start_num + 1 for i in covered_lines]
    covered_lines_info = ', '.join([str(i) for i in covered_lines]) if covered_lines else ''
    if covered_lines_info != '':
        covered_lines_info = f'The test cases cover the lines {covered_lines_info}'
    
    test_program_info = ''
    if target_method.test_head is not None:
        test_program_info = 'Here is an example test case.\n' + '```' + target_method.test_head + '```'
    
    if chosen_chains is not None:
        call_chain_info = construct_call_chain_info(chosen_chains)
        prompt = (
            f"The target function '{func_name}' can be invoked through the call chain {call_chain_info}.\n"
            f"The function '{func_name}' is defined in the line {line_range[0]} to {line_range[-1]}. {covered_lines_info}\n"
            f"{test_program_info}\nPlease write some test cases for {func_name} that can cover different scenarios and edge cases.\n"
            f"Ensure that you have an adequate number of tests, but limit yourself to no more than four test cases, and group similar tests within the same test method whenever possible. "
            f"The code should be self-contained and complete. "
            f"The test cases should cover the call chain {call_chain_info}. "
        )
    else:
        prompt = (
            f"Please write some test cases for '{func_name}' that can cover different scenarios and edge cases. "
            f"The function '{func_name}' is defined in the line {line_range[0]} to {line_range[-1]}. {covered_lines_info}\n "
            f"{test_program_info}\nPlease write some test cases for {func_name} that can cover different scenarios and edge cases.\n"
            f"Ensure that you have an adequate number of tests, but limit yourself to no more than four test cases, and group similar tests within the same test method whenever possible. "
            f"The code should be self-contained and complete. "
        )
    return prompt

def construct_prompt(single_target, all_conditions, direct_selected_examples, class_map):
    is_direct_available, is_indirect_available, new = all_conditions
    chosen_strategy = None
    selected_examples = []
    prompt = ''
    context = ''
    
    if is_direct_available:
        candidate_programs = [i for i in single_target.direct_programs if i not in direct_selected_examples]
        selected_examples = select_examples(single_target, candidate_programs)
        direct_selected_examples.extend(selected_examples)
        
        context = construct_context(single_target, class_map, chosen_chain=None)
        
        if not selected_examples:
            selected_examples = select_examples(single_target, single_target.covered_tests)
        if selected_examples:
            prompt = construct_prompt_from_direct_program(single_target, selected_examples)
        else:
            prompt = construct_prompt_from_scratch(single_target, chosen_chain=None)
        
        chosen_strategy = 'direct'
    elif is_indirect_available:
        available_callee_chains = [i for i in single_target.using_callee_chains if i[0].direct_programs]
        chosen_chain = random.choice(available_callee_chains)
        single_target.used_callee_chains.append(chosen_chain)
        start_function = chosen_chain[0]
        
        # 注意这里用的是start_function的direct program
        selected_examples = select_examples(single_target, start_function.direct_programs)
        
        context = construct_context(single_target, class_map, chosen_chain)
        
        if not selected_examples:
            selected_examples = select_examples(single_target, start_function.covered_tests)
        if selected_examples:
            prompt = construct_prompt_from_calee_program(single_target, selected_examples, chosen_chain)
        else:
            prompt = construct_prompt_from_scratch(single_target, chosen_chain)
        
        chosen_strategy = 'indirect'
    elif new:
        chosen_chain = None
        if single_target.using_callee_chains:
            chosen_chain = random.choice(single_target.using_callee_chains)
        
        selected_examples = select_examples(single_target, single_target.covered_tests)
        
        context = construct_context(single_target, class_map, chosen_chain)
        
        if selected_examples:
            prompt = construct_prompt_from_covered_program(single_target, selected_examples, chosen_chain)
        else:
            if single_target.test_head is not None:
                selected_examples = [TestProgram(content=single_target.test_head, target_function=single_target)]
            prompt = construct_prompt_from_scratch(single_target, chosen_chain)
        
        chosen_strategy = 'new'
    
    return prompt, context, chosen_strategy, selected_examples

def invoke_llm(single_target, context, prompt, prompt_cache_dict, debugging_mode=False):
    """
    Invokes the LLM (Language Model) with the given parameters.
    Parameters:
    - api_base (str): The base URL of the API.
    - single_target (Target): The single target object.
    - context (str): The context for the prompt.
    - prompt (str): The prompt to be passed to the LLM.
    - prompt_cache_dict (dict): A dictionary to cache prompt-response pairs.
    - debugging_mode (bool, optional): Whether to run in debugging mode. Defaults to False.
    Returns:
    - stage1_prompt (str): The stage 1 prompt used for the LLM.
    - stage1_response (str): The stage 1 response received from the LLM.
    - prompt (str): The original prompt passed to the LLM.
    - stage2_response (str): The stage 2 response received from the LLM.
    - generated (bool): Indicates whether the responses were generated successfully.
    """
    # Code implementation goes here
    pass
    package_name = single_target.get_package_name()
    generated = True
    stage1_prompt = ''
    stage1_response = ''
    stage2_response = ''
    try:
        if not debugging_mode:
            chat_bot = ChatBot(api_base=CONFIG['api_base'], model=CONFIG['model'], api_key=CONFIG['api_key'])
            stage1_prompt = construct_summarize_function_prompt_add_import(single_target, package_name, context)
            if stage1_prompt in prompt_cache_dict.keys():
                stage1_response = prompt_cache_dict.get(stage1_prompt)
            else:
                stage1_response = invoke_llm_cache(chat_bot, stage1_prompt, stage1_response=None, stage2_prompt=None)
                prompt_cache_dict[stage1_prompt] = stage1_response
            
            new_prop = f"{stage1_prompt}\n{stage1_response}\n{prompt}"
            if new_prop in prompt_cache_dict.keys():
                stage2_response = prompt_cache_dict.get(new_prop)
            else:
                stage2_response = invoke_llm_cache(chat_bot, stage1_prompt, stage1_response, prompt)
                prompt_cache_dict[new_prop] = stage2_response
        else:
            stage1_prompt = ''
            stage1_response =  ''
            stage2_response = example_response
    except:
        generated = False
    
    return stage1_prompt, stage1_response, prompt, stage2_response, generated


def invoke_llm_cache(chat_bot, stage1_prompt, stage1_response=None, stage2_prompt=None):
    response = chat_bot.chat_cache(stage1_prompt, stage1_response, stage2_prompt)
    return response

