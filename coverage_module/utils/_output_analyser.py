import os
import io
import pickle
import re
import sys

import chardet
import javalang
import javalang.tree

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from utils._java_parser import (
    parse_import_stmts_from_file_code,
    parse_methods_from_class_node,
    parse_fields_from_class_code,
)

junit_imports = [
    "import org.junit.Test;",
    "import org.junit.Assert;",
    "import org.junit.Before;",
    "import org.junit.After;",
    "import static org.junit.Assert.*;",
    "import org.junit.Ignore;",
    "import org.junit.BeforeClass;",
    "import org.junit.AfterClass;",
    "import org.junit.runner.RunWith;",
    "import org.junit.runners.JUnit4;",
    "import org.junit.Rule;",
    "import org.junit.rules.ExpectedException;",
]

focal_imports = [
    # # "import static org.mockito.Mockito.*;",
    # # "import org.mockito.Mockito;",
    # "import java.text.SimpleDateFormat;",
    # "import java.io.*;",
    # "import java.lang.*;",
    # "import java.util.*;",
    # "import java.time.*;",
    # "import java.math.*;",
    # # "import java.sql.SQLException;",
    # "import java.net.*;",
    # "import java.security.*;",
    # "import java.nio.file.Files;",
    # "import java.nio.file.Path;",
    # "import java.sql.*;",
]


def extract_method_name(method_code):
    # Parse the Java code
    method_code = "public class TmpClass {\n" + method_code + "}\n"
    tree = javalang.parse.parse(method_code)

    method_names = []
    for _, node in tree.filter(javalang.tree.MethodDeclaration):
        method_names.append(node.name)
    return method_names[0]


def analyze_outputs(output_str: str, method_signature=None):
    block_dot_lines = []
    lines = output_str.split("\n")
    strategy = "generation"
    if strategy == "generation":
        for id, line in enumerate(lines):
            if line.startswith("```"):
                block_dot_lines.append(id)
    elif strategy == "extend":
        for id, line in enumerate(lines):
            if line.endswith("```") or line.startswith("```"):
                block_dot_lines.append(id)
                pass
            else:
                pass
        pass
    else:
        raise NotImplementedError(
            f"Strategy {strategy} is not supported for analyze_outputs method"
        )
    total_lines = len(lines)
    methods = []
    imports = []
    fields = []
    classes = []
    start = 0
    for id in block_dot_lines:
        if id == 0:
            start = 1
            continue
        cur_block = lines[start: id]
        cur_content = "\n".join(cur_block)
        if lines[id].startswith("```"):
            pass
        else:
            column_id = lines[id].find("```")
            if column_id == -1:
                raise IndexError(f"Failing in finding ``` starters in {lines[id]}")
            else:
                cur_content += lines[id][:column_id]

        if method_signature is not None:
            raw_methods = parse_methods_from_class_node(cur_content)
            for candidate in raw_methods:
                modifier = candidate["method_modifiers"]
                if "@Test" in modifier:
                    methods.append(
                        pickle.loads(pickle.dumps(candidate["method_text"]))
                    )
                else:
                    methods.append(pickle.loads(pickle.dumps(candidate["method_text"])))
            pass
        else:
            methods.extend(
                [i["method_text"] for i in parse_methods_from_class_node(cur_content)]
            )
        imports.extend(parse_import_stmts_from_file_code(cur_content))
        # fields.extend(parse_fields_from_class_code(cur_content, strategy))
        fields.extend(
            [i["declaration_text"] for i in parse_fields_from_class_code(cur_content)]
        )
        # classes.extend(parse_classes_from_file_node(cur_content, strategy))
        start = id + 1
        pass

    if start < total_lines:
        if start == 0:
            pass
        else:
            start += 1
        cur_block = lines[start:]
        cur_content = "\n".join(cur_block)
        cur_methods = parse_methods_from_class_node(cur_content)
        if len(cur_methods) != 0:
            # methods.extend(cur_methods)
            # methods.extend([i["method_text"] for i in cur_methods])
            if method_signature is not None:
                raw_methods = parse_methods_from_class_node(cur_content)
                for candidate in raw_methods:
                    modifier = candidate["method_modifiers"]
                    if "@Test" in modifier:
                        methods.append(
                            pickle.loads(pickle.dumps(candidate["method_text"]))
                        )
                    else:
                        methods.append(
                            pickle.loads(pickle.dumps(candidate["method_text"]))
                        )
                pass
            else:
                methods.extend(
                    [
                        i["method_text"]
                        for i in parse_methods_from_class_node(cur_content)
                    ]
                )
            imports.extend(parse_import_stmts_from_file_code(cur_content))
            fields.extend(
                [
                    i["declaration_text"]
                    for i in parse_fields_from_class_code(cur_content)
                ]
            )
            # classes.extend(parse_classes_from_file_node(cur_content))

    imports = list(set(imports))
    methods = set(methods)
    fields = list(set(fields))

    return methods, imports, fields, classes


def aggeragate_imports_mvn(project_src_root_dir, class_sig, imports, methods):
    
    focal_class_file = os.path.join(project_src_root_dir, class_sig.replace(".", "/") + ".java")
    focal_class_import = []
    try:
        with open(focal_class_file, 'rb') as file:
            raw_data = file.read()
        result = chardet.detect(raw_data)
        encoding = result['encoding']
        focal_content = raw_data.decode(encoding)
        focal_class_import.extend(parse_import_stmts_from_file_code(focal_content))
    except UnicodeDecodeError as e:
        print(f"UnicodeDecodeError: {e}")
    except Exception as e:
        print(f'Error occurred in function util.output_analyser.aggeragate_imports_mvn: {class_sig}')
        print(f"An error occurred: {e}")
    
    imports.append(f"import {class_sig};")
    
    # 根据LLM生成的 imports ，酌情加入imports
    # remove enum to avoid java version isse
    focal_class_import = [i for i in focal_class_import if "enum" not in i.split(".")]
    pre_defined_imports = [i for i in focal_imports if "enum" not in i.split(".")]
    llm_imp_set = set(imports)
    
    focal_class_import = filter_imports(focal_class_import, llm_imp_set)
    pre_defined_imports = filter_imports(
        pre_defined_imports, set(focal_class_import) | llm_imp_set
    )
    
    current_method_names = {}
    new_methods = []
    for method in methods:
        try:
            method_name = extract_method_name(method)
            if method_name in current_method_names.keys():
                current_method_names[method_name] = (
                    current_method_names[method_name] + 1
                )
                method = method.replace(
                    method_name, method_name + str(current_method_names[method_name])
                )
            else:
                current_method_names[method_name] = 0
            new_methods.append(method)
        except:
            continue
    
    return imports, focal_class_import, pre_defined_imports, new_methods


def remove_whitespace(s):
    # 使用 str 的 replace 方法去除常见的空白字符
    for whitespace in [' ', '\t', '\n', '\r']:
        s = s.replace(whitespace, '')
    return s

def update_fields(fields):
    new_fields = []
    cleaned_fields = []
    for field in fields:
        try:
            cleaned_field = remove_whitespace(field)
            if cleaned_field in cleaned_fields:
                continue
            cleaned_fields.append(cleaned_field)
            new_fields.append(field)
        except:
            continue
    
    return new_fields

def update_imports(imports):
    new_imports = []
    cleaned_imports = []
    for imp in imports:
        try:
            cleaned_import = remove_whitespace(imp)
            if cleaned_import in cleaned_imports:
                continue
            cleaned_imports.append(cleaned_import)
            new_imports.append(imp)
        except:
            continue
    
    return new_imports


def update_setup_methods(setup_methods):
    current_method_names = {}
    new_methods = []
    cleaned_methods = []
    for method in setup_methods:
        try:
            cleaned_method = remove_whitespace(method)
            if cleaned_method in cleaned_methods:
                continue
            cleaned_methods.append(cleaned_method)
            method_name = extract_method_name(method)
            if method_name in current_method_names.keys():
                current_method_names[method_name] = (
                    current_method_names[method_name] + 1
                )
                method = method.replace(
                    method_name, method_name + str(current_method_names[method_name])
                )
            else:
                current_method_names[method_name] = 0
            new_methods.append(method)
        except:
            continue
    
    return new_methods

def assemble_single_ut_test_class_mvn(        
        class_sig,
        imports,
        setup_methods,
        fields,
        uts,
        classes,
        test_class_name):
    
    package_name = ".".join(class_sig.split(".")[:-1])
    class_declaration = f"public class {test_class_name} {{"
    
    res_content = ""
    res_stream = io.StringIO(res_content)
    res_stream.write(f"package {package_name};\n")
    
    for imp in imports:
        res_stream.write(imp + "\n")
        
    res_stream.write("\n")
    res_stream.write(class_declaration + "\n")
    res_stream.write("\n")
    
    for field in fields:
        res_stream.write(field + "\n")
        
    for method in setup_methods:
        res_stream.write("\n" + method + "\n")
        res_stream.write("\n")
    
    for ut in uts:
        res_stream.write("\n" + ut + "\n")
        res_stream.write("\n")
    res_stream.write("}")
    for single_class in classes:
        res_stream.write(f"\n{single_class}\n")
        
    assembled_test_class = res_stream.getvalue()
    return assembled_test_class, ".".join([package_name, test_class_name])
    


def filter_imports(src_imports: list, tgt_imports: set):
    """
    filter imports from source list from target list.
    :param src_imports: source import list, which is about to be merged.
    :param tgt_imports: target import list, which is the imports that generated by LLM
    :return: merged import set
    """
    # find all classes that are imported by target import statements
    classes_imported_by_tgt = []
    packages_imported_by_tgt = []
    final_imports = []
    jupiters_included_in_tgt = False
    for import_str in tgt_imports:
        tokens = import_str.split()
        if len(tokens) == 2 and tokens[0] == "import":
            cls_str = tokens[1].split(".")[-1][:-1]
            if "org.junit.jupiter" in tokens[1]:
                jupiters_included_in_tgt = True
            if cls_str == "*":
                packages_imported_by_tgt.append(".".join(tokens[1].split(".")[:-1]))
                pass
            else:
                classes_imported_by_tgt.append(cls_str)
            # final_imports.append(import_str)
            pass
        elif len(tokens) == 3 and tokens[0] == "import" and tokens[1] == "static":
            cls_str = tokens[2].split(".")[-1][:-1]
            if "org.junit.jupiter" in tokens[2]:
                jupiters_included_in_tgt = True
            if cls_str == "*":
                packages_imported_by_tgt.append(".".join(tokens[2].split(".")[:-1]))
                pass
            else:
                classes_imported_by_tgt.append(cls_str)
            # final_imports.append(import_str)
            pass
        else:
            raise NotImplementedError(
                f"more than 3 tokens in {import_str}, please check"
            )
            
    for import_str in src_imports:
        tokens = import_str.split()
        if len(tokens) == 2 and tokens[0] == "import":
            cls_str = tokens[1].split(".")[-1][:-1]
            imported_cls = tokens[1]
            pass
        elif len(tokens) == 3 and tokens[0] == "import" and tokens[1] == "static":
            cls_str = tokens[2].split(".")[-1][:-1]
            imported_cls = tokens[2]
            pass
        else:
            raise NotImplementedError(
                f"more than 3 tokens in {import_str}, please check"
            )

        if cls_str in classes_imported_by_tgt:
            # 同名的去掉
            continue
        # 去掉Assert 和 junit.jupiter.Assertion的问题
        # org.junit.jupiter.api.Assertions.*

        package_name = ".".join(imported_cls.split(".")[:-1])
        if (package_name in packages_imported_by_tgt) or (
                package_name.startswith("org.junit") and jupiters_included_in_tgt
        ):
            # 如果已经引入*，则不需要继续补充
            continue

        final_imports.append(import_str)

    return final_imports
