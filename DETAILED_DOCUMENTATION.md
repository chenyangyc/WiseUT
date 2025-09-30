# Documentation

This is the detailed documentation of WiseUT's implementation.

## 1. Directory Structure

### Root Directory

- **main.py**: Main entry point of the project.  
- **main_config.json**: Global configuration file.  
- **main_utils.py**: Utility functions for the main program.

### coverage_module

- **collect_coverage.py / collect_coverage_maven.py**: Scripts for collecting test coverage data (Python/Maven).  
- **starter_mvn.py**: Maven project starter script.  
- **requirements.txt**: Python dependencies.  
- **core/**: Core abstractions for coverage analysis (file, method, package, test program, chatbot).  
- **data/**: Stores configuration, analysis results, and temporary files.  
- **utils/**: Utility scripts for coverage analysis, dependency management, static analysis, and test construction.

### defect_module

- **extract_focal_method.py**: Extracts focal methods from code.  
- **extract_triggering_focal_method.py**: Extracts triggering focal methods.  
- **our_chain_gen.py**: Chain generation logic for defect analysis.  
- **run_generation.py**: Runs the defect generation process.  
- **core/**: Core abstractions for assistant tools (AST objects, branches, functions, modules, selections, test programs, chatbot, prompts).  
- **data/**: Stores configurations, reports, temporary directories, and new project results.  
- **generated_results/**: Stores generated results (error-seeking and non-error-seeking).  
- **utils/**: Utility scripts for assistant tools.

### refine_module

- **main.py**: Entry point for code refinement.  
- **run_code_slicing.py**: Code slicing script.  
- **run_llm_refine.py**: LLM-based code refinement script.  
- **tree_sitter_query.py**: Tree-sitter syntax tree query script.  
- **code_parser/**: Code parsing utilities.  
- **data/**: Data storage for refinement module.



## 2. Core Implementation Overview

### 2.1 Coverage

#### 2.1.1 Static Analysis

**Location**: `coverage_module/utils/_static_analysis_call_chaining.py`  
**Functionality**: Performs static analysis on Java projects to extract structural elements (packages, classes, files, methods) and build inter-method call relationships, including branch-related method calls.

##### **Key APIs**

**`add_classes_and_methods_in_package(package, source_code, single_file)`**

- **Description**: Extracts class and method information from source code and populates custom `Package` and `File` objects.
- **Parameters**:
  - `package` (`Package`): The `Package` object corresponding to the Java file.
  - `source_code` (`str`): Source code of the Java file.
  - `single_file` (`File`): The `File` object representing the Java file.
- **Returns**: None.

**`find_call_method(package, method_map, class_map)`**

- **Description**: Analyzes a given `Package` to extract call chains for all its `Method` objects.
- **Parameters**:
  - `package` (`Package`): The package to analyze.
  - `method_map` (`dict`): Mapping from fully qualified method names (including package and class) to `Method` objects.
  - `class_map` (`dict`): Mapping from fully qualified class names (including package) to `Class` objects.
- **Returns**: None.

**`extract_called_functions(source_code, all_packages, method_map, class_map)`**

- **Description**: Extracts all method names and their argument lists invoked in a given test source code.
- **Parameters**:
  - `source_code` (`str`): Source code of the test file.
  - `all_packages` (`list`): List of all `Package` objects in the project.
  - `method_map` (`dict`): Mapping from fully qualified method names to `Method` objects.
  - `class_map` (`dict`): Mapping from fully qualified class names to `Class` objects.
- **Returns**:
  - `case_called_functions` (`list`): List of called method names and their argument lists.



#### 2.1.2 Test Strategy Selection Module

**Location**: `coverage_module/utils/strategy_utils.py`  
**Functionality**: Selects appropriate TELPA strategies (direct invocation, indirect invocation, or new generation) for a given method based on context and prior attempts.

##### Key APIs

**`update_strategies(strtegies_rounds, single_target, direct_selected_examples)`**

- **Description**: Updates test strategies based on strategy rounds to determine whether to use direct, indirect, or newly generated test cases.
- **Parameters**:
  - `strtegies_rounds` (`dict`): Dictionary containing strategy round information.
  - `single_target` (`object`): Target object containing direct program, call chains, etc.
  - `direct_selected_examples` (`list`): List of already selected direct test examples.
- **Returns**: A list of three booleans indicating whether direct, indirect, or new strategies should be applied.

**`called_chain_filtering(single_func)`**

- **Description**: Filters and processes function call chains, retaining only those with distinct starting points or minimal length.
- **Parameters**:
  - `single_func` (`object`): Function object containing call chain information.
- **Returns**: None. Modifies the `using_callee_chains` attribute of `single_func`.



#### 2.1.3 Test Execution and Coverage Collection Module

**Location**: `coverage_module/utils/test_excute_utils.py`  
**Functionality**: Executes assembled test classes via Maven and collects code coverage metrics.

##### Key APIs

**`write_test_class_and_execute(project_root, test_root_dir, test_class_sig, test_class_content, type, existing)`**

- **Description**: Writes a generated test class to disk, executes Maven tests, and analyzes code coverage.
- **Parameters**:
  - `project_root` (`str`): Path to the project root directory.
  - `test_root_dir` (`str`): Path to the test source root directory.
  - `test_class_sig` (`str`): Signature of the test class.
  - `test_class_content` (`str`): Full content of the test class.
  - `type` (`str`): Test command type (`'clean test'` or `'only test'`).
  - `existing` (`bool`): If `False`, the test file is deleted after execution.
- **Returns**: A dictionary with keys:
  - `result` (`str`): Test outcome (`'Passed'`, `'Failed Compilation'`, `'Failed Execution'`, etc.).
  - `coverage`: Coverage data (or `None` if test failed).
  - `directory` (`str`): Execution directory path.

**`process_test_case(single_target, all_packages, method_map, class_map, test_class_content, compile_res)`**

- **Description**: Processes a single test case by extracting called functions and updating coverage information.
- **Parameters**:
  - `single_target` (`object`): Test target object.
  - `all_packages` (`list`): List of all `Package` objects.
  - `method_map` (`dict`): Method name-to-object mapping.
  - `class_map` (`dict`): Class name-to-object mapping.
  - `test_class_content` (`str`): Full test class content.
  - `compile_res` (`dict`): Compilation result dictionary.
- **Returns**:
  - `compile_err` (`str`): Compilation error message.
  - `exec_err` (`str`): Execution error message.
  - `is_compiled` (`bool`): Whether the test compiled successfully.
  - `res` (`str`): Processing result (`'better!'` or `'useless!'`).

**`compile_and_collect_coverage_test(single_target, project_root, test_root_dir, test_class_content, test_class_sig, all_packages, method_map, class_map)`**

- **Description**: Compiles a test case and collects coverage data.
- **Parameters**:
  - `single_target` (`object`): Test target object.
  - `project_root` (`str`): Project root path.
  - `test_root_dir` (`str`): Test source root path.
  - `test_class_content` (`str`): Full test class content.
  - `test_class_sig` (`str`): Test class signature.
  - `all_packages` (`list`): List of all `Package` objects.
  - `method_map` (`dict`): Method name-to-object mapping.
  - `class_map` (`dict`): Class name-to-object mapping.
- **Returns**:
  - `compile_err` (`str`): Compilation error message.
  - `exec_err` (`str`): Execution error message.
  - `is_compiled` (`bool`): Whether the test compiled successfully.
  - `res` (`str`): Processing result.



#### 2.1.4 Program Slicing Module

**Location**: `refine_module/run_code_slicing.py`  
**Functionality**: Slices Java unit test functions into multiple smaller test functions using assertions as slicing criteria.

##### Key APIs

**`splited_code(test_source_code)`**

- **Description**: Splits a Java test source file into multiple test functions based on assertion statements.
- **Parameters**:
  - `test_source_code` (`str`): Java test source code.
- **Returns**: Split code segments as a list or structured representation.



### 2.2 Test Refinement

**Location**: `refine_module/run_llm_refine.py`  
**Functionality**: Enhances Java unit test cases using Large Language Models (LLMs) by (1) inserting structured Arrange-Act-Assert (AAA) comments and Javadoc, and (2) renaming test methods and local variables to be more descriptive—while preserving original behavior through AST-guided merging and collision-aware renaming.

##### Key APIs

**`refine_single_test(function_content)`**

- **Description**: Main entry point that performs end-to-end refinement of a Java test method, including comment augmentation and identifier renaming.
- **Parameters**:
  - `function_content` (`str`): Source code of the original Java test method.
- **Returns**:
  - Refined test code as a string, or `None` if refinement fails.

**`merge_add_comment_tests(origin_test_content, comment_test_content)`**

- **Description**: Safely merges LLM-generated comments into the original test by aligning AST nodes using structural and lexical similarity, ensuring comments are inserted at correct locations without code modification.
- **Parameters**:
  - `origin_test_content` (`str`): Original test code.
  - `comment_test_content` (`str`): LLM output with AAA comments and docstring.
- **Returns**:
  - Merged test code with comments properly inserted (`str`).

**`merge_rename_tests(rename_dict, source_code, source_ast)`**

- **Description**: Applies semantic-preserving renaming to test identifiers (method name and variables) using an AST to avoid renaming method invocations (e.g., `assertEquals`), ensuring only relevant identifiers are updated.
- **Parameters**:
  - `rename_dict` (`dict`): Mapping from original names to new descriptive names.
  - `source_code` (`str`): Test code to rename.
  - `source_ast` (`ASTNode`): Parsed AST for precise identifier targeting.
- **Returns**:
  - Renamed test code with improved readability (`str`).

**`extract_target_variable_names(node)`**

- **Description**: Identifies local variables that are both declared and subsequently used in the test, making them suitable candidates for renaming (excludes unused or constant-like identifiers).
- **Parameters**:
  - `node` (`ASTNode`): Root AST node of the test method.
- **Returns**:
  - Set of variable names eligible for renaming (`set[str]`).



### 2.3 Defect Detection

**Location**: `defect_module/run_generation.py`  
**Functionality**: It builds prompts from code context (functions, classes, call chains), executes generated tests inside the target environment, and verifies correctness through type checks, semantic verification, and lightweight coverage collection. The pipeline coordinates prompt construction, iterative refinement, and execution to ensure high-quality, executable test cases.

##### Key APIs

**`generate_seperate_prompt(function_info, backward=True)`**

- **Description**: Constructs an LLM prompt for a single function by embedding contextual information such as class membership and constructor usage. Supports *backward reasoning* to incorporate caller-side type information.
- **Parameters**:
  - `function_info` (`dict`): Metadata of the target function (e.g., class name, parameters, usage context).
  - `backward` (`bool`, default=`True`): Whether to include backward reasoning context (caller perspective).
- **Returns**:
  - A formatted prompt string (`str`) for test generation.



**`generate_type_seperate_prompt(call_chain, inference_prompt_cache_dict, infered_results)`**

- **Description**: Builds prompts for type-aware reasoning on a call chain. Integrates cached prompt fragments and previously inferred type results to guide LLM output.
- **Parameters**:
  - `call_chain` (`list`): Sequence of functions/methods forming a call dependency chain.
  - `inference_prompt_cache_dict` (`dict`): Cache of previously used prompts.
  - `infered_results` (`dict`): Accumulated type inference results.
- **Returns**:
  - Type-enhanced prompt string (`str`).



**`generate_iterative_prompt(function_info, called_name_chain, backward=True)`**

- **Description**: Produces iterative prompts that refine test generation across multiple steps, combining contextual function info and chains of invoked methods.
- **Parameters**:
  - `function_info` (`dict`): Metadata of the target function.
  - `called_name_chain` (`list`): Names of methods invoked by the function.
  - `backward` (`bool`, default=`True`): Enable backward reasoning context.
- **Returns**:
  - Iteratively refined prompt string (`str`).



**`generate_type_iterative_prompt(call_chain, inference_prompt_cache_dict, infered_results)`**

- **Description**: Similar to `generate_iterative_prompt`, but focuses on type-level iterative reasoning along a call chain.
- **Parameters**: Same as `generate_type_seperate_prompt`.
- **Returns**: Type-refined iterative prompt string (`str`).



**`run_single_method(origin_test_file, origin_test_func, proj_name, focal_method, focal_dir, fixed_dir, env_name, debugging_mode, prompt_cache_dict, tmp_dir_for_test, type_inference_history, triggering_method, called_name_chain, run_rethink, chain_identifier_hash)`**

- **Description**: Core entry point to generate, refine, and execute a single unit test method. It constructs prompts, calls LLMs, merges results, and validates execution inside the project environment.
- **Parameters** (high-level):
  - `origin_test_file` (`str`): Path to the original test file.
  - `origin_test_func` (`str`): Target function name.
  - `proj_name` (`str`): Project identifier.
  - `focal_method` (`str`): Method under test.
  - `focal_dir` / `fixed_dir` (`str`): Project source and fixed directories.
  - `env_name` (`str`): Target conda/virtual environment.
  - `debugging_mode` (`bool`): Toggle for verbose debugging.
  - `prompt_cache_dict`, `type_inference_history` (`dict`): Prompt/inference histories.
  - `triggering_method`, `called_name_chain` (`list`/`str`): Contextual methods invoked.
  - `run_rethink` (`bool`): Whether to trigger iterative refinement.
  - `chain_identifier_hash` (`str`): Hash ID of the call chain for caching.
- **Returns**:
  - Generated and validated test code (`str`), or `None` if unsuccessful.



**`execute_test(test_content, relative_test_file, focal_method, used_framework, env_name, tmp_dir_for_test, focal_proj_dir, fixed_proj_dir)`**

- **Description**: Executes generated test content within the specified environment and framework. Collects runtime results and lightweight coverage feedback.
- **Parameters**:
  - `test_content` (`str`): Source code of the test.
  - `relative_test_file` (`str`): Relative file path for saving the test.
  - `focal_method` (`str`): Target method under test.
  - `used_framework` (`str`): Testing framework (e.g., JUnit, PyTest).
  - `env_name` (`str`): Execution environment.
  - `tmp_dir_for_test` (`str`): Directory for temporary test execution.
  - `focal_proj_dir`, `fixed_proj_dir` (`str`): Project directories.
- **Returns**:
  - Execution results and coverage data (`dict`).



**`find_corresponding_ast_node(call_chain, function_dict)`**

- **Description**: Locates the AST node corresponding to a specific call chain in the function dictionary, enabling precise alignment between generated and original code.
- **Parameters**:
  - `call_chain` (`list`): Sequence of invoked functions.
  - `function_dict` (`dict`): Parsed function ASTs.
- **Returns**:
  - Matching AST node object, or `None` if not found.



**`type_error_detection_entry()`**

- **Description**: Entry point for detecting type errors in generated tests. Likely orchestrates type-checking passes using previously defined verification prompts.
- **Parameters**: None.
- **Returns**:
  - Detection results (`dict` or `bool`), depending on implementation.