# maven_dependency_manager.py
from lxml import etree
import os
from loguru import logger
from typing import Dict, List, Optional, Any, Set, Tuple


DEPENDENCY_CONFIG = {
    "jdk7": {
        # 统一的 dependency_management，包含普通依赖和BOM
        "dependency_management": [
            {"g": "junit", "a": "junit", "v": "4.12"},
            {"g": "org.mockito", "a": "mockito-core", "v": "1.10.19"},
            {"g": "org.objenesis", "a": "objenesis", "v": "2.1"},
            {"g": "org.hamcrest", "a": "hamcrest-core", "v": "1.3"},
            {"g": "org.powermock", "a": "powermock-api-mockito2", "v": "1.6.6"},
            {"g": "org.powermock", "a": "powermock-core", "v": "1.6.6"},
            {"g": "org.powermock", "a": "powermock-module-junit4", "v": "1.6.6"},
        ],
        # 在 dependencies 中声明使用的依赖 (无版本)
        "used_dependencies": [
            {"g": "junit", "a": "junit", "s": "test"},
            {"g": "org.mockito", "a": "mockito-core", "s": "test"},
            {"g": "org.objenesis", "a": "objenesis", "s": "test"},
            {"g": "org.hamcrest", "a": "hamcrest-core", "s": "test"},
            {"g": "org.powermock", "a": "powermock-api-mockito2", "s": "test"},
            {"g": "org.powermock", "a": "powermock-core", "s": "test"},
            {"g": "org.powermock", "a": "powermock-module-junit4", "s": "test"},
        ],
        # 插件管理配置：声明需要使用的插件及其执行配置
        "used_plugins": [
            {
                "g": "org.jacoco",
                "a": "jacoco-maven-plugin",
                "executions": [
                    {"id": "pre-test", "goals": ["prepare-agent"]},
                    {"id": "report", "phase": "verify", "goals": ["report"]},
                ],
            },
        ],
        # 独立的插件版本管理配置
        "plugin_management": [
            {"g": "org.jacoco", "a": "jacoco-maven-plugin", "v": "0.7.9"},
        ],
    },
    "jdk8": {
        "dependency_management": [
            # BOM 现在用 type="pom" 和 scope="import" 标记
            {
                "g": "org.junit",
                "a": "junit-bom",
                "v": "5.12.2",
                "type": "pom",
                "scope": "import",
            },
            {
                "g": "org.mockito",
                "a": "mockito-bom",
                "v": "5.5.0",
                "type": "pom",
                "scope": "import",
            },
            # 未被BOM覆盖的依赖
            {"g": "org.apiguardian", "a": "apiguardian-api", "v": "1.1.0"},
            {"g": "net.bytebuddy", "a": "byte-buddy", "v": "1.14.11"},
            {"g": "net.bytebuddy", "a": "byte-buddy-agent", "v": "1.14.11"},
            {"g": "org.objenesis", "a": "objenesis", "v": "3.3"},
            {"g": "org.hamcrest", "a": "hamcrest", "v": "2.1"},
            {"g": "org.powermock", "a": "powermock-api-mockito2", "v": "1.7.4"},
            {"g": "org.powermock", "a": "powermock-core", "v": "1.7.4"},
            {"g": "org.powermock", "a": "powermock-module-junit4", "v": "1.7.4"},
        ],
        "used_dependencies": [
            {"g": "org.junit.jupiter", "a": "junit-jupiter-api", "s": "test"},
            {"g": "org.junit.jupiter", "a": "junit-jupiter-params", "s": "test"},
            {"g": "org.junit.jupiter", "a": "junit-jupiter-engine", "s": "test"},
            {"g": "org.mockito", "a": "mockito-core", "s": "test"},
            {"g": "org.mockito", "a": "mockito-junit-jupiter", "s": "test"},
            {"g": "org.apiguardian", "a": "apiguardian-api", "s": "test"},
            {"g": "net.bytebuddy", "a": "byte-buddy", "s": "test"},
            {"g": "net.bytebuddy", "a": "byte-buddy-agent", "s": "test"},
            {"g": "org.objenesis", "a": "objenesis", "s": "test"},
            {"g": "org.hamcrest", "a": "hamcrest", "s": "test"},
            {"g": "org.powermock", "a": "powermock-api-mockito2", "s": "test"},
            {"g": "org.powermock", "a": "powermock-core", "s": "test"},
            {"g": "org.powermock", "a": "powermock-module-junit4", "s": "test"},
        ],
        "used_plugins": [
            {
                "g": "org.jacoco",
                "a": "jacoco-maven-plugin",
                "executions": [
                    {"id": "pre-test", "goals": ["prepare-agent"]},
                    {"id": "report", "phase": "verify", "goals": ["report"]},
                ],
            },
        ],
        "plugin_management": [
            {"g": "org.jacoco", "a": "jacoco-maven-plugin", "v": "0.8.12"},
        ],
    },
    "jdk9": "jdk8",
    "jdk11": "jdk8",
    "jdk17": "jdk8",
    "jdk21": {
        "dependency_management": [
            {
                "g": "org.junit",
                "a": "junit-bom",
                "v": "5.12.2",
                "type": "pom",
                "scope": "import",
            },
            {
                "g": "org.mockito",
                "a": "mockito-bom",
                "v": "5.7.0",
                "type": "pom",
                "scope": "import",
            },
            {"g": "org.apiguardian", "a": "apiguardian-api", "v": "1.1.2"},
            {"g": "net.bytebuddy", "a": "byte-buddy", "v": "1.14.11"},
            {"g": "net.bytebuddy", "a": "byte-buddy-agent", "v": "1.14.11"},
            {"g": "org.objenesis", "a": "objenesis", "v": "3.3"},
            {"g": "org.hamcrest", "a": "hamcrest", "v": "2.2"},
            {"g": "org.powermock", "a": "powermock-api-mockito2", "v": "1.7.4"},
            {"g": "org.powermock", "a": "powermock-core", "v": "1.7.4"},
            {"g": "org.powermock", "a": "powermock-module-junit4", "v": "1.7.4"},
        ],
        "used_dependencies": [
            {"g": "org.junit.jupiter", "a": "junit-jupiter-api", "s": "test"},
            {"g": "org.junit.jupiter", "a": "junit-jupiter-params", "s": "test"},
            {"g": "org.junit.jupiter", "a": "junit-jupiter-engine", "s": "test"},
            {"g": "org.mockito", "a": "mockito-core", "s": "test"},
            {"g": "org.mockito", "a": "mockito-junit-jupiter", "s": "test"},
            {"g": "org.apiguardian", "a": "apiguardian-api", "s": "test"},
            {"g": "net.bytebuddy", "a": "byte-buddy", "s": "test"},
            {"g": "net.bytebuddy", "a": "byte-buddy-agent", "s": "test"},
            {"g": "org.objenesis", "a": "objenesis", "s": "test"},
            {"g": "org.hamcrest", "a": "hamcrest", "s": "test"},
            {"g": "org.powermock", "a": "powermock-api-mockito2", "s": "test"},
            {"g": "org.powermock", "a": "powermock-core", "s": "test"},
            {"g": "org.powermock", "a": "powermock-module-junit4", "s": "test"},
        ],
        "used_plugins": [
            {
                "g": "org.jacoco",
                "a": "jacoco-maven-plugin",
                "executions": [
                    {"id": "pre-test", "goals": ["prepare-agent"]},
                    {"id": "report", "phase": "verify", "goals": ["report"]},
                ],
            },
        ],
        "plugin_management": [
            {"g": "org.jacoco", "a": "jacoco-maven-plugin", "v": "0.8.12"},
        ],
    },
}


# ================================
# 2. 工具函数
# ================================
def _get_pom_namespace(root_element):
    namespace_uri = root_element.nsmap.get(None)
    if not namespace_uri:
        logger.warning(
            "Default namespace not found. Assuming http://maven.apache.org/POM/4.0.0"
        )
        namespace_uri = "http://maven.apache.org/POM/4.0.0"
    return namespace_uri


def _create_namespaces_dict(uri):
    return {"maven": uri}


def _format_xml_and_write(tree, pom_path):
    """格式化 XML 并写入文件，兼容不同版本的 lxml"""
    try:
        # 尝试使用 etree.indent（新版本 lxml）
        if hasattr(etree, "indent"):
            etree.indent(tree, space="  ")
        tree.write(pom_path, encoding="utf-8", xml_declaration=True, pretty_print=True)
    except Exception as e:
        # 如果失败，使用基本的 pretty_print
    # ...去除详细 log...
        tree.write(pom_path, encoding="utf-8", xml_declaration=True, pretty_print=True)


def _resolve_config(jdk_key: str) -> Optional[Dict]:
    if jdk_key not in DEPENDENCY_CONFIG:
        logger.error(f"Unsupported JDK version: {jdk_key}")
        return None
    config = DEPENDENCY_CONFIG[jdk_key]
    if isinstance(config, str):
        base = DEPENDENCY_CONFIG.get(config)
        if base is None:
            logger.error(f"Base config '{config}' for '{jdk_key}' not found.")
            return None
        return base
    return config


# ================================
# 3. 预扫描函数：核心改进，避免重复
# ================================
def _scan_existing_elements(pom_path: str) -> Dict[str, Set[str]]:
    """
    预扫描 POM 文件，返回已存在的 groupId 集合。

    返回格式：
    {
        'dependency': {'org.junit.jupiter', 'org.mockito', ...},  # 包含 dependencies 和 dependencyManagement
        'plugin': {'org.jacoco', ...}                           # 包含 plugins 和 pluginManagement
    }

    特殊处理：JUnit 4/5 互斥检查和 JUnit 5 组完整性检查
    """
    result = {"dependency": set(), "plugin": set()}

    if not os.path.exists(pom_path):
        return result

    try:
        parser = etree.XMLParser(strip_cdata=False, recover=True)
        tree = etree.parse(pom_path, parser)
        root = tree.getroot()
        ns_uri = _get_pom_namespace(root)
        namespaces = _create_namespaces_dict(ns_uri)

        # 扫描所有 dependencies（包括 dependencies 和 dependencyManagement）
        all_deps = root.xpath(
            "//maven:dependencies/maven:dependency", namespaces=namespaces
        )
        all_deps += root.xpath(
            "//maven:dependencyManagement//maven:dependencies/maven:dependency",
            namespaces=namespaces,
        )
        for dep in all_deps:
            g = dep.find("maven:groupId", namespaces)
            if g is not None:
                result["dependency"].add(g.text)

        # 扫描所有 plugins（包括 plugins 和 pluginManagement）
        all_plugins = root.xpath(
            "//maven:build/maven:plugins/maven:plugin", namespaces=namespaces
        )
        all_plugins += root.xpath(
            "//maven:profile/maven:build/maven:plugins/maven:plugin",
            namespaces=namespaces,
        )
        all_plugins += root.xpath(
            "//maven:build/maven:pluginManagement//maven:plugins/maven:plugin",
            namespaces=namespaces,
        )
        all_plugins += root.xpath(
            "//maven:profile/maven:build/maven:pluginManagement//maven:plugins/maven:plugin",
            namespaces=namespaces,
        )
        for plugin in all_plugins:
            g = plugin.find("maven:groupId", namespaces)
            if g is not None:
                result["plugin"].add(g.text)

        # 特殊处理：JUnit 4/5 互斥检查
        junit4_groups = {"junit"}
        junit5_groups = {"org.junit.jupiter", "org.junit"}

        has_junit4 = any(group in result["dependency"] for group in junit4_groups)
        has_junit5 = any(group in result["dependency"] for group in junit5_groups)

        # 如果有 JUnit 4，则标记 JUnit 5 相关组为已存在
        if has_junit4:
            result["dependency"].update(junit5_groups)
            # ...去除详细 log...

        # 如果有 JUnit 5，则标记 JUnit 4 相关组为已存在，并确保 JUnit 5 组完整
        if has_junit5:
            result["dependency"].update(junit4_groups)
            result["dependency"].update(junit5_groups)  # 确保两个 JUnit 5 组都被标记
            # ...去除详细 log...

        return result
    except Exception as e:
        logger.warning(f"Failed to scan existing elements in {pom_path}: {e}")
        return result


def _should_skip_dependency(
    dep_type: str, group_id: str, existing_groups: Dict[str, Set[str]]
) -> bool:
    """
    检查是否应该跳过某个依赖/插件的添加。

    简单逻辑：如果该类型下已经存在该 groupId，则跳过
    """
    if group_id in existing_groups.get(dep_type, set()):
        # ...去除详细 log...
        return True
    return False


# ================================
# 4. 核心函数：职责分离
# ================================
def manage_dependency_version(
    pom_path: str,
    group_id: str,
    artifact_id: str,
    version: str,
    scope: str = None,
    type: str = None,
) -> bool:
    """在 <dependencyManagement> 中管理依赖版本或导入BOM。"""
    if not os.path.exists(pom_path):
        logger.error(f"pom.xml not found: {pom_path}")
        return False

    try:
        parser = etree.XMLParser(
            strip_cdata=False, recover=True, remove_blank_text=True
        )
        tree = etree.parse(pom_path, parser)
        root = tree.getroot()
        ns_uri = _get_pom_namespace(root)
        namespaces = _create_namespaces_dict(ns_uri)
        ns = f"{{{ns_uri}}}"

        dep_mgmt = root.find("maven:dependencyManagement", namespaces)
        if dep_mgmt is None:
            dep_mgmt = etree.SubElement(root, f"{ns}dependencyManagement")

        deps_mgmt = dep_mgmt.find("maven:dependencies", namespaces)
        if deps_mgmt is None:
            deps_mgmt = etree.SubElement(dep_mgmt, f"{ns}dependencies")

        # 构造 XML 并格式化
        dependency_elem = etree.Element(f"{ns}dependency")
        etree.SubElement(dependency_elem, f"{ns}groupId").text = group_id
        etree.SubElement(dependency_elem, f"{ns}artifactId").text = artifact_id
        etree.SubElement(dependency_elem, f"{ns}version").text = version

        if scope:
            etree.SubElement(dependency_elem, f"{ns}scope").text = scope
        if type:
            etree.SubElement(dependency_elem, f"{ns}type").text = type

        deps_mgmt.append(dependency_elem)

        # 使用自定义格式化方法
        _format_xml_and_write(tree, pom_path)
        # ...去除详细 log...
        return True
    except Exception as e:
        logger.error(
            f"Failed to manage version for {group_id}:{artifact_id}: {e}", exc_info=True
        )
        return False


def add_dependency(
    pom_path: str, group_id: str, artifact_id: str, scope: str = "compile"
) -> bool:
    """在 <dependencies> 中添加依赖（无版本）。"""
    if not os.path.exists(pom_path):
        logger.error(f"pom.xml not found: {pom_path}")
        return False

    try:
        parser = etree.XMLParser(
            strip_cdata=False, recover=True, remove_blank_text=True
        )
        tree = etree.parse(pom_path, parser)
        root = tree.getroot()
        ns_uri = _get_pom_namespace(root)
        namespaces = _create_namespaces_dict(ns_uri)
        ns = f"{{{ns_uri}}}"

        dependencies = None
        for child in root:
            if (
                etree.QName(child).localname == "dependencies"
                and child.getparent() == root
            ):
                dependencies = child
                break
        if dependencies is None:
            dependencies = etree.SubElement(root, f"{ns}dependencies")

        # 构造依赖元素并格式化
        dependency_elem = etree.Element(f"{ns}dependency")
        etree.SubElement(dependency_elem, f"{ns}groupId").text = group_id
        etree.SubElement(dependency_elem, f"{ns}artifactId").text = artifact_id
        etree.SubElement(dependency_elem, f"{ns}scope").text = scope

        dependencies.append(dependency_elem)

        # 使用自定义格式化方法
        _format_xml_and_write(tree, pom_path)
    # ...去除详细 log...
        return True
    except Exception as e:
        logger.error(
            f"Failed to add dependency {group_id}:{artifact_id}: {e}", exc_info=True
        )
        return False


def manage_plugin_version(
    pom_path: str, group_id: str, artifact_id: str, version: str
) -> bool:
    """在 <pluginManagement> 中管理插件版本。"""
    if not os.path.exists(pom_path):
        logger.error(f"pom.xml not found: {pom_path}")
        return False

    try:
        parser = etree.XMLParser(
            strip_cdata=False, recover=True, remove_blank_text=True
        )
        tree = etree.parse(pom_path, parser)
        root = tree.getroot()
        ns_uri = _get_pom_namespace(root)
        namespaces = _create_namespaces_dict(ns_uri)
        ns = f"{{{ns_uri}}}"

        all_builds = [root.find("maven:build", namespaces)]
        all_builds += root.xpath("//maven:profile/maven:build", namespaces=namespaces)
        all_builds = [b for b in all_builds if b is not None]

        for build_elem in all_builds:
            plugin_mgmt = build_elem.find("maven:pluginManagement", namespaces)
            if plugin_mgmt is None:
                plugin_mgmt = etree.SubElement(build_elem, f"{ns}pluginManagement")

            plugins_mgmt = plugin_mgmt.find("maven:plugins", namespaces)
            if plugins_mgmt is None:
                plugins_mgmt = etree.SubElement(plugin_mgmt, f"{ns}plugins")

            # 检查是否已存在
            for plugin in plugins_mgmt.findall("maven:plugin", namespaces):
                g = plugin.find("maven:groupId", namespaces)
                a = plugin.find("maven:artifactId", namespaces)
                if (
                    g is not None
                    and a is not None
                    and g.text == group_id
                    and a.text == artifact_id
                ):
                    # ...去除详细 log...
                    break
            else:  # 未找到，才添加
                # 构造插件元素并格式化
                plugin_elem = etree.Element(f"{ns}plugin")
                etree.SubElement(plugin_elem, f"{ns}groupId").text = group_id
                etree.SubElement(plugin_elem, f"{ns}artifactId").text = artifact_id
                etree.SubElement(plugin_elem, f"{ns}version").text = version

                plugins_mgmt.append(plugin_elem)
                # ...去除详细 log...

        # 使用自定义格式化方法
        _format_xml_and_write(tree, pom_path)
        return True
    except Exception as e:
        logger.error(
            f"Failed to manage plugin version {group_id}:{artifact_id}: {e}",
            exc_info=True,
        )
        return False


def add_maven_plugin(
    pom_path: str,
    group_id: str,
    artifact_id: str,
    executions: List[Dict] = None,
    configuration: Dict = None,
) -> bool:
    """在 <plugins> 中添加插件实例。"""
    if not os.path.exists(pom_path):
        logger.error(f"pom.xml not found: {pom_path}")
        return False

    try:
        parser = etree.XMLParser(
            strip_cdata=False, recover=True, remove_blank_text=True
        )
        tree = etree.parse(pom_path, parser)
        root = tree.getroot()
        ns_uri = _get_pom_namespace(root)
        namespaces = _create_namespaces_dict(ns_uri)
        ns = f"{{{ns_uri}}}"

        all_builds = [root.find("maven:build", namespaces)]
        all_builds += root.xpath("//maven:profile/maven:build", namespaces=namespaces)
        all_builds = [b for b in all_builds if b is not None]

        for build_elem in all_builds:
            plugins = build_elem.find("maven:plugins", namespaces)
            if plugins is None:
                plugins = etree.SubElement(build_elem, f"{ns}plugins")

            # 检查是否已存在
            for plugin in plugins.findall("maven:plugin", namespaces):
                g = plugin.find("maven:groupId", namespaces)
                a = plugin.find("maven:artifactId", namespaces)
                if (
                    g is not None
                    and a is not None
                    and g.text == group_id
                    and a.text == artifact_id
                ):
                    # ...去除详细 log...
                    break
            else:  # 未找到，才添加
                plugin_elem = etree.Element(f"{ns}plugin")
                etree.SubElement(plugin_elem, f"{ns}groupId").text = group_id
                etree.SubElement(plugin_elem, f"{ns}artifactId").text = artifact_id
                if executions:
                    execs = etree.SubElement(plugin_elem, f"{ns}executions")
                    for e in executions:
                        ex = etree.SubElement(execs, f"{ns}execution")
                        if "id" in e:
                            etree.SubElement(ex, f"{ns}id").text = e["id"]
                        if "phase" in e:
                            etree.SubElement(ex, f"{ns}phase").text = e["phase"]
                        if "goals" in e:
                            goals = etree.SubElement(ex, f"{ns}goals")
                            for goal in e["goals"]:
                                etree.SubElement(goals, f"{ns}goal").text = goal
                if configuration:
                    config = etree.SubElement(plugin_elem, f"{ns}configuration")
                    for k, v in configuration.items():
                        elem = etree.SubElement(config, f"{ns}{k}")
                        elem.text = str(v)
                plugins.append(plugin_elem)
                # ...去除详细 log...

        # 使用自定义格式化方法
        _format_xml_and_write(tree, pom_path)
        return True
    except Exception as e:
        logger.error(
            f"Failed to add plugin {group_id}:{artifact_id}: {e}", exc_info=True
        )
        return False


def update_surefire_plugin_configuration(pom_path: str) -> bool:
    """更新 maven-surefire-plugin 的 configuration。"""
    if not os.path.exists(pom_path):
        logger.error(f"pom.xml not found: {pom_path}")
        return False
    try:
        parser = etree.XMLParser(
            strip_cdata=False, recover=True, remove_blank_text=True
        )
        tree = etree.parse(pom_path, parser)
        root = tree.getroot()
        ns_uri = _get_pom_namespace(root)
        namespaces = _create_namespaces_dict(ns_uri)

        # 查找 surefire 插件 (优先在 plugins，其次在 pluginManagement)
        surefire = None
        # 在 plugins 中找
        plugins = root.find(".//maven:build/maven:plugins", namespaces)
        if plugins is not None:
            for plugin in plugins.findall("maven:plugin", namespaces):
                g = plugin.find("maven:groupId", namespaces)
                a = plugin.find("maven:artifactId", namespaces)
                if (
                    g is not None
                    and a is not None
                    and g.text == "org.apache.maven.plugins"
                    and a.text == "maven-surefire-plugin"
                ):
                    surefire = plugin
                    break
        # 在 pluginManagement 中找
        if surefire is None:
            plugin_mgmt = root.find(".//maven:build/maven:pluginManagement", namespaces)
            if plugin_mgmt is not None:
                plugins_mgmt = plugin_mgmt.find("maven:plugins", namespaces)
                if plugins_mgmt is not None:
                    for plugin in plugins_mgmt.findall("maven:plugin", namespaces):
                        g = plugin.find("maven:groupId", namespaces)
                        a = plugin.find("maven:artifactId", namespaces)
                        if (
                            g is not None
                            and a is not None
                            and g.text == "org.apache.maven.plugins"
                            and a.text == "maven-surefire-plugin"
                        ):
                            surefire = plugin
                            break

        if surefire is None:
            logger.info(
                "maven-surefire-plugin not found, skipping configuration update."
            )
            return False

        ns = f"{{{ns_uri}}}"
        config = surefire.find("maven:configuration", namespaces)
        if config is None:
            config = etree.SubElement(surefire, f"{ns}configuration")

        for key, value in [
            ("forkedProcessTimeoutInSeconds", "600"),
            ("reuseForks", "false"),
        ]:
            elem = config.find(f"maven:{key}", namespaces)
            if elem is None:
                elem = etree.SubElement(config, f"{ns}{key}")
            elem.text = value

        # 使用自定义格式化方法
        _format_xml_and_write(tree, pom_path)
    # ...去除详细 log...
        return True
    except Exception as e:
        logger.error(f"Failed to update surefire: {e}", exc_info=True)
        return False


# ================================
# 5. 主接口函数
# ================================
def add_maven_dependencies_for_jdk(jdk_version: str, pom_path: str) -> bool:
    """
    为指定 JDK 版本添加所有测试依赖。
    使用预扫描机制，确保幂等性和避免版本冲突。
    """
    config = _resolve_config(jdk_version)
    if not config:
        return False
    if not os.path.exists(pom_path):
        logger.error(f"pom.xml not found: {pom_path}")
        return False
    with open(pom_path, "r", encoding="utf-8") as f:
        pom_content = f.read()

    try:
        # 🔍 预扫描：一次性获取所有已存在的 groupId
        existing_groups = _scan_existing_elements(pom_path)
        total_groups = sum(len(groups) for groups in existing_groups.values())
    # ...去除详细 log...

        # 1. 添加 dependency_management 条目 (BOM 和普通依赖)
        for dep in config["dependency_management"]:
            if not _should_skip_dependency("dependency", dep["g"], existing_groups):
                success = manage_dependency_version(
                    pom_path=pom_path,
                    group_id=dep["g"],
                    artifact_id=dep["a"],
                    version=dep["v"],
                    scope=dep.get("scope"),  # 可能为 None
                    type=dep.get("type"),  # 可能为 None
                )

        # 2. 添加 plugin_management 条目
        for plugin_cfg in config.get("plugin_management", []):
            if not _should_skip_dependency("plugin", plugin_cfg["g"], existing_groups):
                success = manage_plugin_version(
                    pom_path=pom_path,
                    group_id=plugin_cfg["g"],
                    artifact_id=plugin_cfg["a"],
                    version=plugin_cfg["v"],
                )

        # 3. 添加 used_dependencies
        for dep in config["used_dependencies"]:
            if not _should_skip_dependency("dependency", dep["g"], existing_groups):
                success = add_dependency(
                    pom_path=pom_path,
                    group_id=dep["g"],
                    artifact_id=dep["a"],
                    scope=dep["s"],
                )

        # 4. 添加 used_plugins
        for plugin_cfg in config["used_plugins"]:
            if not _should_skip_dependency("plugin", plugin_cfg["g"], existing_groups):
                success = add_maven_plugin(
                    pom_path=pom_path,
                    group_id=plugin_cfg["g"],
                    artifact_id=plugin_cfg["a"],
                    executions=plugin_cfg.get("executions"),
                    configuration=plugin_cfg.get("configuration"),
                )

        # 5. 更新 Surefire 配置
        update_surefire_plugin_configuration(pom_path)

        return True, pom_content

    except Exception as e:
        logger.error(f"Failed to process {pom_path}: {e}", exc_info=True)
        return False, pom_content


def find_pom_xml(project_dir: str) -> Optional[str]:
    """
    在给定的项目目录下查找 pom.xml 文件。
    优先返回根目录下的 pom.xml，否则递归查找第一个 pom.xml。
    """
    root_pom = os.path.join(project_dir, "pom.xml")
    if os.path.isfile(root_pom):
        return root_pom
    for dirpath, _, filenames in os.walk(project_dir):
        if "pom.xml" in filenames:
            return os.path.join(dirpath, "pom.xml")
    logger.warning(f"No pom.xml found in {project_dir}")
    return None


if __name__ == "__main__":
    project_directory = "/Users/wangziqi/Documents/scientific/Java_codebot/Java_Maven/data/projects/jfreechart"  # 替换为你的项目路径
    pom_file = find_pom_xml(project_directory)
    if not pom_file:
        logger.error(f"pom.xml not found in {project_directory}")
        exit(1)
    success = add_maven_dependencies_for_jdk("jdk11", pom_file)
