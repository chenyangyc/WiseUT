import sys
import os

sys.path.extend([".", ".."])
import subprocess
from loguru import logger
import xml.etree.ElementTree as ET

from utils._add_dependency_in_mvn import find_pom_xml, add_maven_dependencies_for_jdk


def run_mvn_test(args):
    directory, test_class, test_method = args
    pom_path = find_pom_xml(directory)
    if not pom_path:
        logger.error(f"pom.xml not found in {directory}")
        exit(1)
    success, pom_content = add_maven_dependencies_for_jdk("jdk11", pom_path)
    if not success:
        logger.error('add pom dependency failed!!!')
        
    
    # 构建命令
    if test_class and test_method:
        mvn_command = f"mvn clean org.jacoco:jacoco-maven-plugin:prepare-agent test -Dtest={test_class}#{test_method}"
    elif test_class:
        mvn_command = f"mvn clean org.jacoco:jacoco-maven-plugin:prepare-agent test -Dtest={test_class}"
    else:
        mvn_command = f"mvn clean org.jacoco:jacoco-maven-plugin:prepare-agent test"

    jacoco_report_command = 'mvn org.jacoco:jacoco-maven-plugin:report'
    # 改变到指定目录
    os.chdir(directory)

    # 运行命令
    # javac_result = subprocess.run('javac -version', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    mvn_result = subprocess.run(mvn_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    _ = subprocess.run(jacoco_report_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # 收集输出和错误信息
    mvn_stdout = mvn_result.stdout
    mvn_stderr = mvn_result.stderr

    # 把原始的pom.xml写回
    with open(pom_path, 'w') as f:
        f.write(pom_content)

    # 检查结果
    jacoco_report_output = os.path.join(directory, 'target/site/jacoco/jacoco.xml')
    if "BUILD SUCCESS" in mvn_stdout:
        if not os.path.exists(jacoco_report_output):
            logger.error('Please ensure that maven and jacoco are properly configured!')
            test_result = "Failed Compilation"
        else:
            test_result = "Passed"
    elif "BUILD FAILURE" in mvn_stdout or "Tests run:" in mvn_stdout and "Failures:" in mvn_stdout:
        if not os.path.exists(jacoco_report_output):
            test_result = "Failed Compilation"
            pass
        else:
            test_result = 'Failed Execution'
    else:
        logger.error('Unknown results of mvn test. Please check')


    return {
        "directory": directory,
        "test_class": test_class,
        "test_method": test_method,
        "result": test_result,
        "stdout": mvn_stdout,
        "stderr": mvn_stderr
    }

def run_mvn_compile(project_root):
    directory = project_root
    pom_path = find_pom_xml(directory)
    if not pom_path:
        logger.error(f"pom.xml not found in {directory}")
        exit(1)
    success, pom_content = add_maven_dependencies_for_jdk("jdk11", pom_path)
    if not success:
        logger.error('add pom dependency failed!!!')
    
    mvn_command = f"mvn clean compile"
    os.chdir(project_root)
    mvn_result = subprocess.run(mvn_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    
    mvn_stdout = mvn_result.stdout
    mvn_stderr = mvn_result.stderr
    
    # 把原始的pom.xml写回
    with open(pom_path, 'w') as f:
        f.write(pom_content)
    
    return mvn_stdout, mvn_stderr

def run_mvn_test_no_clean(args):
    directory, test_class, test_method = args
    
    # 清空jacoco.exec和jacoco.xml文件
    jacoco_exec_path = os.path.join(directory, 'target/jacoco.exec')
    if os.path.exists(jacoco_exec_path):
        os.remove(jacoco_exec_path)
    jacoco_report_output = os.path.join(directory, 'target/site/jacoco/jacoco.xml')
    if os.path.exists(jacoco_report_output):
        os.remove(jacoco_report_output)
    
    # 构建命令 注意 这里不clean
    if test_class and test_method:
        mvn_command = f"mvn org.jacoco:jacoco-maven-plugin:prepare-agent test -Dtest={test_class}#{test_method}"
    elif test_class:
        mvn_command = f"mvn org.jacoco:jacoco-maven-plugin:prepare-agent test -Dtest={test_class}"
    else:
        mvn_command = f"mvn org.jacoco:jacoco-maven-plugin:prepare-agent test"

    jacoco_report_command = 'mvn org.jacoco:jacoco-maven-plugin:report'
    # 改变到指定目录
    os.chdir(directory)

    # 运行命令
    # javac_result = subprocess.run('javac -version', shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    mvn_result = subprocess.run(mvn_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    _ = subprocess.run(jacoco_report_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # 收集输出和错误信息
    mvn_stdout = mvn_result.stdout
    mvn_stderr = mvn_result.stderr
    
    # 检查结果
    jacoco_report_output = os.path.join(directory, 'target/site/jacoco/jacoco.xml')
    if "BUILD SUCCESS" in mvn_stdout:
        assert os.path.exists(jacoco_report_output)
        test_result = "Passed"
    elif "BUILD FAILURE" in mvn_stdout or "Tests run:" in mvn_stdout and "Failures:" in mvn_stdout:
        if not os.path.exists(jacoco_report_output):
            test_result = "Failed Compilation"
            pass
        else:
            test_result = 'Failed Execution'
    else:
        logger.error('Unknown results of mvn test. Please check')


    return {
        "directory": directory,
        "test_class": test_class,
        "test_method": test_method,
        "result": test_result,
        "stdout": mvn_stdout,
        "stderr": mvn_stderr
    }
