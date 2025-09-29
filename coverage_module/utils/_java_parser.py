import sys

from loguru import logger
sys.path.extend([".", ".."])
import json
import pickle
from tree_sitter import Parser, Language
import tree_sitter_java as tsjava

JAVA_LANGUAGE = Language(tsjava.language(), name='java')


def parse_fields_from_class_code(class_str: str):
    """
    Analyze defined fields for given class.
    :param class_str: class code in a string.
    :return: list of field dicts, for eaxmple:
            {
                "field_name": field_name,
                "field_type": field_type,
                "field_modifiers": field_modifiers,
                "declaration_text": declaration_text,
            }
    """
    java_modifiers = [
        "public",
        "protected",
        "private",
        "static",
        "final",
        "abstract",
        "synchronized",
        "volatile",
        "transient",
        "native",
        "default",
    ]
    
    parser = Parser()
    parser.language = JAVA_LANGUAGE
    tree = parser.parse(bytes(class_str, "utf-8"))
    rets = []

    field_decl_query = JAVA_LANGUAGE.query("""(field_declaration) @field_decl""")
    field_attr_query = JAVA_LANGUAGE.query(
        """
        (field_declaration
            type: (_) @type_name
            declarator: (variable_declarator name: (identifier)@var_name)
        ) 
        """
    )

    fields = field_decl_query.captures(tree.root_node).get("field_decl", [])
    for field_decl in fields:
        declaration_text = field_decl.text.decode()
        
        field_modifiers = []
        tokens = declaration_text.split(" ")
        for token in tokens:
            if token in java_modifiers:
                field_modifiers.append(token)
        
        # Get attributes of the field declaration
        attrs = field_attr_query.captures(field_decl)

        # Sort attributes by their start byte position
        type_name_list = sorted(attrs.get("type_name", []), key=lambda x: x.start_byte)
        type_name_list = [
            type_name for type_name in type_name_list if type_name.parent == field_decl
        ]
        var_name_list = sorted(attrs.get("var_name", []), key=lambda x: x.start_byte)
        var_name_list = [
            var_name
            for var_name in var_name_list
            if var_name.parent.parent == field_decl
        ]

        if len(type_name_list) != 1:
            logger.error("Field Declaration has no type name or multiple type names.")

        type_name_list = [type_name_list[0]] * len(
            var_name_list
        )  # Extend type names to match variable names

        for field_type, field_name in zip(type_name_list, var_name_list):
            rets.append(
                {
                    "field_name": field_name,
                    "field_type": field_type,
                    "field_modifiers": field_modifiers,
                    "declaration_text": declaration_text,
                }
            )
    return rets


def parse_import_stmts_from_file_code(file_code: str):
    """
    从给定的代码文件内容中提取import。为了避免噪音，需要满足两个条件：
    1. import语句必须是分号结尾
    2. import语句至多含有三个以空格区分的token

    Args:
        file_code (str): 输入的代码文件内容（最好是代码文件，其他文件中可能会被过滤掉）

    Returns:
        list: 从输入内容中提取出的import strings
    """
    parser = Parser()
    parser.language = JAVA_LANGUAGE
    tree = parser.parse(bytes(file_code, "utf-8"))

    import_decl_query = JAVA_LANGUAGE.query("(import_declaration) @import_decl")

    rets = []
    imports = import_decl_query.captures(tree.root_node).get("import_decl", [])
    for import_stmt in imports:
        import_stmt = str(import_stmt.text, encoding="utf-8")
        tks = import_stmt.split()
        if import_stmt.endswith(";") and (len(tks) == 2 or len(tks) == 3):
            rets.append(import_stmt)
    return rets


def parse_methods_from_class_node(class_str: str, need_prefix=False):
    """
    Analyze methods defined in the class.
    :param class_str:
    :return: list of collected methods. The elements are like:
    {
        "method_name": method_name,
        "method_modifiers": method_modifiers,
        "method_return_type": method_return_type,
        "method_body": method_body,
        "method_text": method_text,
        "method_start_line": method start line,
        "method_end_line": method end line
    }
    """
    parser = Parser()
    parser.language = JAVA_LANGUAGE
    tree = parser.parse(bytes(class_str, "utf-8"))
    rets = []
    
    # 查询所有方法声明节点
    method_query = JAVA_LANGUAGE.query(
        """
        (method_declaration) @method_decl
        """
    )

    # 提取方法属性：修饰符、返回类型、名称、参数、体
    method_attr_query = JAVA_LANGUAGE.query(
        """
        (method_declaration
            type: (_) @ret_type
            name: (_) @name
            body: (_)? @body
        )
        """
    )

    methods = method_query.captures(tree.root_node).get("method_decl", [])
    # 不解析内部函数
    methods = [
        method_node
        for method_node in methods
        if method_node.parent.parent.parent == tree.root_node
    ]

    for method_node in methods:
        method_text = str(method_node.text, 'utf-8')
        method_start_line = method_node.start_point[0]
        method_end_line = method_node.end_point[0]
        
        attrs = method_attr_query.captures(method_node)
        return_type_list = sorted(attrs.get("ret_type", []), key=lambda x: x.start_byte)
        name_list = sorted(attrs.get("name", []), key=lambda x: x.start_byte)
        body_list = sorted(attrs.get("body", []), key=lambda x: x.start_byte)
        
        # 检查属性数量是否一致
        if len(name_list) != len(return_type_list):
            logger.warning(
                f"Attribute count of Method Declaration {str(method_node.text, encoding='utf-8')} mismatch, "
            )
            continue

        # 取第一个结果即可（每个方法只有一个）
        method_modifiers = None
        for child in method_node.children:
            if child.type == "modifiers":
                method_modifiers = child.text.decode()
                break
        if method_modifiers is None:
            method_modifiers = "private"
        method_return_type = return_type_list[0]
        method_name = name_list[0]
        method_body = body_list[0] if body_list else None
        
        rets.append(
            {
                "method_name": method_name,
                "method_modifiers": method_modifiers,
                "method_return_type": method_return_type,
                "method_body": method_body,
                "method_text": method_text,
                "method_start_line": method_start_line,
                "method_end_line": method_end_line
            }
        )
    return rets
    