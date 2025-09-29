import random
import string
from utils._output_analyser import aggeragate_imports_mvn, analyze_outputs, assemble_single_ut_test_class_mvn, update_fields, update_imports, update_setup_methods


def extract_elements_from_llm_generation(
        generation: str, method_signature: str
):
    """
    从LLM的输出结果中分析代码元素，组成测试类
    Args:
        generation: LLM的输出内容
        method_signature: 待测函数签名

    Returns:
        dict:{
                "msg": 提取结果，"success", "no llm output" 或 "no methods in output"
                "methods":[method],
                "imports":[import],
                "fields":[field],
                "classes":[class],
                "uts": [ut],
            }
    """
    # 当LLM有正确输出的时候才进行下一步
    msg = "no llm output"
    imports, fields, classes, methods, uts = [], [], [], [], []
    if generation != "":
        methods, imports, fields, classes = analyze_outputs(
            generation,
            method_signature=method_signature,
        )
        set_up_methods = [method for method in methods if not method.strip().startswith("@Test")]
        uts = [method for method in methods if method.strip().startswith("@Test")]
        
        remove_uts = []
        for set_up_method in set_up_methods:
            line = set_up_method.split('\n')[0];
            if 'test' in line.lower():
                new_ut = "@Test\n" + set_up_method
                uts.append(new_ut)
                remove_uts.append(set_up_method)
        
        set_up_methods = [method for method in set_up_methods if method not in remove_uts]
        # uts = [method for method in set_up_methods]
        
        msg = "success"

    # 如果没有提取到任何method
    if len(uts) == 0:
        set_up_methods, imports, fields, classes = [], [], [], []
        msg = "no methods in output"
        uts = []

    return {
        "msg": msg,
        "methods": set_up_methods,
        "uts": uts,
        "imports": imports,
        "fields": fields,
        "classes": classes
    }
    
def assembly_test_class_component(single_target, stage2_response, selected_examples, src_root_dir):
    method_signature = single_target.signature
    class_name = single_target.belong_class.name
    extractions = extract_elements_from_llm_generation(stage2_response, method_signature)

    imports, focal_class_import, src_imports, setup_methods = aggeragate_imports_mvn(src_root_dir, class_name, extractions["imports"], extractions["methods"])
    total_imports = imports + focal_class_import + src_imports
    fields = extractions["fields"]
    classes = extractions["classes"]
    uts = extractions['uts']
    
    # 如果有选中的例子，就把例子的import，fields，setup methods加进来
    if selected_examples:
        example_imports = []
        example_fields = []
        example_setups = []
        example = selected_examples[0]
        example_extract = extract_elements_from_llm_generation(example.content, method_signature)
        example_imports.extend(example_extract['imports'])
        example_fields.extend(example_extract['fields'])
        example_setups.extend([method for method in example_extract['methods'] if '@Before' in method or '@After' in method])
        total_imports = list(set(total_imports + example_imports))
        fields = list(set(fields + example_fields))
        setup_methods = list(set(setup_methods + example_setups))
    
    setup_methods = update_setup_methods(setup_methods)
    fields = update_fields(fields)
    total_imports = update_imports(total_imports)
    total_imports.sort()
    
    return total_imports, fields, setup_methods, classes, uts
    
def construct_test_class(single_target, total_imports, fields, setup_methods, classes, single_ut):
    class_name = single_target.belong_class.name
    diff_id = generate_random_string(16)
    test_class_name = single_target.name_no_package + diff_id + 'Test'
    test_class_name = test_class_name[0].upper() + test_class_name[1:]
    test_class_content, test_class_sig = assemble_single_ut_test_class_mvn(class_name, total_imports, setup_methods, fields, [single_ut], classes, test_class_name)
    
    return test_class_content, test_class_sig

def generate_random_string(length):
    '''生成随机字符串，表示diff_id'''
    characters = string.ascii_letters + string.digits  # 包含大写字母、小写字母和数字
    random_string = ''.join(random.choice(characters) for _ in range(length))
    return random_string