import os
import json

from data.Config import CONFIG

def find_java_files(directory):
    java_files = []

    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".java"):
                java_files.append(os.path.join(root, file))
    return java_files

def load_java_tests(project_root, test_base):
    # existing_cases = {
    #     "project_root":,
    #     "test_root_dir":,
    #     "test_class_sig":,
    #     "test_class":,
    # }
    existing_cases = []
    test_root_dir = test_base
    full_test_root = os.path.join(project_root, test_base)
    files = find_java_files(full_test_root)
    for file in files:
        with open(file, 'r', encoding='utf-8') as reader:
            test_class = reader.read()
        test_class_sig = file.replace(full_test_root + '/', '')
        test_class_sig = test_class_sig.replace(os.path.sep, '.').rstrip('.java')
        # print(test_class_sig)
        existing_cases.append({
            "project_root": project_root,
            "test_root_dir": test_base,
            "test_class_sig": test_class_sig,
            "test_class": test_class
        })
    return existing_cases


def load_focal_method(project_name, package):
    fm_sigs = []
    source_file = CONFIG['path_mappings'][project_name]['focal_method']
    if not os.path.exists(source_file):
        print('Focal method file not found.')
        return fm_sigs
    with open(source_file, 'r', encoding='utf-8') as reader:
        for line in reader.readlines():
            if line.strip() == '':
                continue
            inst = json.loads(line.strip())
            source_code_pkg = inst['sourceMethodSignature'].split('#')[0]
            if source_code_pkg == package:
                fm_sigs.append((inst['sourceMethodSignature'], inst['head_test']))
                pass
            # print(1)
    return fm_sigs

def load_focal_class(project_name, package):
    fm_sigs = []
    source_file = CONFIG['path_mappings'][project_name]['focal_class']
    if not os.path.exists(source_file):
        print('Focal method file not found.')
        return fm_sigs
    with open(source_file, 'r', encoding='utf-8') as reader:
        for line in reader.readlines():
            if line.strip() == '':
                continue
            inst = json.loads(line.strip())
            source_code_pkg = inst['sourceClassSignature'].split('#')[0]
            if source_code_pkg == package:
                fm_sigs.append((inst['sourceClassSignature'], inst['head_test']))
                pass
            # print(1)
    return fm_sigs

def load_packages(project_name):
    packages = []
    source_file = CONFIG['path_mappings'][project_name]['focal_method']
    if not os.path.exists(source_file):
        print('Packages file not found.')
        return packages
    with open(source_file, 'r', encoding='utf-8') as reader:
        for line in reader.readlines():
            if line.strip() == '':
                continue
            inst = json.loads(line.strip())
            source_code_pkg = inst['sourceMethodSignature'].split('#')[0]
            packages.append(source_code_pkg)
    
    packages = list(set(packages))
    return packages


