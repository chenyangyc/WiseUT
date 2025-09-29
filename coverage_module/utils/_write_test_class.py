import os
from loguru import logger


def _create_directory_structure(root_dir, package_name):
    package_path = package_name.replace('.', os.sep)
    full_path = os.path.join(root_dir, package_path)
    os.makedirs(full_path, exist_ok=True)
    return full_path


def _write_content_to_file(file_path, content):
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(content)


def write_test_class(project_root, test_root_dir, test_class_sig, test_class_content, log=False):
    # 获取实现文件内容
    implementation_content = test_class_content

    # 从实现文件内容中提取包名和类名
    class_name = test_class_sig.split('.')[-1]
    package_name = test_class_sig[:-len(class_name) - 1]

    if not package_name or not class_name:
        raise ValueError("The implementation file does not contain a valid package name or class name.")

    # 创建包对应的目录结构
    package_path = _create_directory_structure(os.path.join(project_root, test_root_dir), package_name)

    # 定义测试类的文件路径
    test_class_path = os.path.join(package_path, f"{class_name}.java")

    # 将实现内容写入测试类文件中
    _write_content_to_file(test_class_path, implementation_content)

    if log: logger.info(f"Successfully wrote the test class to {test_class_path}")

def clear_test_class(project_root, test_root_dir, test_class_sig, log=False):
    # 从实现文件内容中提取包名和类名
    class_name = test_class_sig.split('.')[-1]
    package_name = test_class_sig[:-len(class_name) - 1]

    if not package_name or not class_name:
        raise ValueError("The implementation file does not contain a valid package name or class name.")

    # 创建包对应的目录结构
    package_path = _create_directory_structure(os.path.join(project_root, test_root_dir), package_name)

    # 定义测试类的文件路径
    test_class_path = os.path.join(package_path, f"{class_name}.java")

    # 删除测试类文件
    os.remove(test_class_path)

    if log: logger.info(f"Successfully removed the test class at {test_class_path}")

def save_test_class(test_class_sig, test_class_content, save_dir, log=False):
    # 获取实现文件内容
    implementation_content = test_class_content

    # 从实现文件内容中提取包名和类名
    class_name = test_class_sig.split('.')[-1]
    package_name = test_class_sig[:-len(class_name) - 1]

    if not package_name or not class_name:
        raise ValueError("The implementation file does not contain a valid package name or class name.")

    # 创建包对应的目录结构
    package_path = _create_directory_structure(save_dir, package_name)

    # 定义测试类的文件路径
    test_class_path = os.path.join(package_path, f"{class_name}.java")

    # 将实现内容写入测试类文件中
    _write_content_to_file(test_class_path, implementation_content)

    if log: logger.info(f"Successfully saved the test class to {test_class_path}")