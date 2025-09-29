from collections import defaultdict
import re
import xml.etree.ElementTree as ET

def to_jave_bytecode_types(c_str: str):
    """
    Converts a given Java bytecode type string to its corresponding Java type.

    Args:
        c_str (str): The Java bytecode type string to be converted.

    Returns:
        str: The corresponding Java type.

    Raises:
        NotImplementedError: If the given bytecode type is not implemented yet.
    """
    # ["B", "C", "D", "F", "I", "J", "Z", "S"]
    if c_str == "B":
        return "java.lang.byte"
    elif c_str == "C":
        return "java.lang.character"
    elif c_str == "D":
        return "java.lang.double"
    elif c_str == "F":
        return "java.lang.float"
    elif c_str == "I":
        return "java.lang.integer"
    elif c_str == "J":
        return "java.lang.long"
    elif c_str == "Z":
        return "java.lang.boolean"
    elif c_str == "S":
        return "java.lang.short"
    elif c_str.startswith("L"):
        return c_str[1:].replace("/", ".")
    elif c_str.startswith("["):
        return to_jave_bytecode_types(c_str[1:]) + "[]"
    else:
        raise NotImplementedError("class type %s not implemented yet" % c_str)


def parse_coverage_xml(coverage_report):
    """
    Load and parse the JaCoCo XML coverage report

    Args:
        coverage_report (str): jacoco生成的覆盖率报告路径

    Raises:
        NotImplementedError: 不支持的变量类型，请联系开发人员

    Returns:
        dict: 经过分析之后的jacoco覆盖率指标
    """
    tree = ET.parse(coverage_report)
    root = tree.getroot()

    coverage_data = defaultdict()
    # Iterate over the packages in the XML and collect data
    for package in root.findall(".//package"):
        package_name = package.attrib["name"]
        package_name = package_name.replace('/', '.')
        coverage_data[package_name] = defaultdict()

        '''
        <line nr="52" mi="5" ci="0" mb="0" cb="0"/>
        nr 属性：表示代码中的行号。
        mi 属性：missed instruction
        ci 属性：covered instruction
        mb 属性：missed branch
        cb 属性：covered branch
        '''
        for sourcefile in package.findall(".//sourcefile"):
            sourcefile_name = sourcefile.attrib["name"]
            if sourcefile.findall(".//line"):
                coverage_data[package_name][sourcefile_name] = {
                    "line" : defaultdict(),
                    "branch" : defaultdict()
                }
                
                coverage_data[package_name][sourcefile_name]
                coverage_line = []
                total_line = []
                
                covered_branch = []
                total_branch = []
                for line in sourcefile.findall(".//line"):
                    nr = int(line.attrib["nr"])
                    mi = int(line.attrib["mi"])
                    ci = int(line.attrib["ci"])
                    mb = int(line.attrib["mb"])
                    cb = int(line.attrib["cb"])
                    if ci > 0:
                        coverage_line.append(nr)
                    total_line.append(nr)
                    
                    if mb > 0 or cb > 0:
                        coverage_data[package_name][sourcefile_name]["branch"][nr] = {
                            "total": mb + cb,
                            "covered": cb
                        }

                coverage_data[package_name][sourcefile_name]["line"]['coverage_line'] = coverage_line
                coverage_data[package_name][sourcefile_name]["line"]['total_line'] = total_line
                
        for clazz in package.findall(".//class"):
            clazz_name = clazz.attrib["name"]
            if clazz.findall(".//method"):
                coverage_data[package_name][clazz_name] = defaultdict()

                for method in clazz.findall(".//method"):
                    method_name = method.attrib["name"]
                    pattern = r"\(.*?\)"
                    parameters = re.findall(pattern, method.attrib["desc"])[0][1:-1]
                    raw_param_list = parameters.split(";")
                    parameter_list = []

                    for param_str in raw_param_list:
                        if param_str == "":
                            continue
                        else:
                            param_stack = []

                            for i in range(len(param_str)):
                                c_str = param_str[i]
                                if c_str == "[":
                                    param_stack.append(c_str)
                                    continue
                                elif c_str == "L":
                                    param_stack.append(param_str[i:])
                                    res = "".join(param_stack)
                                    parameter_list.append(
                                        to_jave_bytecode_types(res).lower()
                                    )
                                    param_stack.clear()
                                    break
                                elif c_str in ["B", "C", "D", "F", "I", "J", "Z", "S"]:
                                    param_stack.append(c_str)
                                    pass
                                else:
                                    raise NotImplementedError(
                                        "Class Type %s not implemented yet." % c_str
                                    )
                                res = "".join(param_stack)
                                parameter_list.append(
                                    to_jave_bytecode_types(res).lower()
                                )
                                param_stack.clear()

                    tmp_list = []
                    for i in parameter_list:
                        if "/" in i:
                            tmp_list.append(i.split("/")[-1])
                        else:
                            tmp_list.append(i)
                    parameter_tuple = tuple(tmp_list)

                    if method_name not in coverage_data[package_name][clazz_name]:
                        coverage_data[package_name][clazz_name][
                            method_name
                        ] = defaultdict()
                    coverage_data[package_name][clazz_name][method_name][
                        parameter_tuple
                    ] = defaultdict()
                    if method.find('.//counter[@type="LINE"]') is not None:
                        coverage_data[package_name][clazz_name][method_name][
                            parameter_tuple
                        ]["line_coverage"] = method.find(
                            './/counter[@type="LINE"]'
                        ).attrib
                    else:
                        coverage_data[package_name][clazz_name][method_name][
                            parameter_tuple
                        ]["line_coverage"] = None
                    if method.find('.//counter[@type="BRANCH"]') is not None:
                        coverage_data[package_name][clazz_name][method_name][
                            parameter_tuple
                        ]["branch_coverage"] = method.find(
                            './/counter[@type="BRANCH"]'
                        ).attrib
                    else:
                        coverage_data[package_name][clazz_name][method_name][
                            parameter_tuple
                        ]["branch_coverage"] = None
    return coverage_data
