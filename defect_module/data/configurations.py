import os
import json
import logging
from rich.logging import RichHandler


_config_file = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')), 'main_config.json')

with open(_config_file, 'r', encoding='utf-8') as f:
    CONFIG = json.loads(f.read())['defect']

model = CONFIG['model']
api_key = CONFIG['api_key']
base_url = CONFIG['api_base']
temperature = CONFIG['temperature']

verification_api_key = api_key
verification_base_url = base_url
verification_model = model
verification_temperature = temperature

project_configs = CONFIG['path_mappings']
project_names = CONFIG['path_mappings'].keys()

expr_identifier = CONFIG['expr_identifier']

code_base = CONFIG['code_base']

conda_base = '/root/anaconda3'
coverage_tool = '/root/anaconda3/envs/llm/bin/coverage'

base_report = f'{code_base}/data/reports'
os.makedirs(base_report, exist_ok=True)

def init_logger(project_name="myproject"):
    logger = logging.getLogger(project_name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False 

    # 清理旧 handler，避免重复打印
    logger.handlers.clear()

    handler = RichHandler(
        rich_tracebacks=True,
        show_time=True,   # 关掉时间
        show_path=True,   # 关掉路径
        show_level=True    # 只保留彩色等级 + message
    )

    # RichHandler 自己控制格式，这里只留 message
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    return logger


# 使用
logger = init_logger("current_file_logger")


example_response = """
To trigger a `TypeError` in the provided `verify_collections` method, we need to identify a scenario where the method expects a certain type but receives a different type. One potential area for a `TypeError` is the `collection` parameter, which is expected to be an iterable (likely a list of tuples or lists). If we pass a non-iterable or an iterable with incorrect types, it could raise a `TypeError`.

Here’s a pytest unit test that triggers a `TypeError` by passing a non-iterable (e.g., an integer) as the `collections` parameter:

```python
import pytest
from ansible.errors import AnsibleError
from ansible.galaxy.collection import verify_collections

def test_verify_collections_type_error():
    # Define invalid inputs that should trigger a TypeError
    invalid_collections = 12345  # Non-iterable type
    search_paths = ["/some/path"]
    apis = []
    validate_certs = True
    ignore_errors = False

    # Expecting a TypeError due to invalid type for 'collections'
    with pytest.raises(TypeError):
        verify_collections(invalid_collections, search_paths, apis, validate_certs, ignore_errors)
```

### Explanation:
- `invalid_collections = 12345`: This is an integer, which is not an iterable. The `verify_collections` method expects `collections` to be an iterable (e.g., a list of tuples or lists).
- `pytest.raises(TypeError)`: This context manager ensures that the test will pass only if a `TypeError` is raised. If no `TypeError` is raised, the test will fail.

### Running the Test:
- If the test is correctly written, it should raise a `TypeError` when the `verify_collections` method tries to iterate over `invalid_collections`.
- The test will fail if the `TypeError` is not raised, indicating that the method does not handle the type correctly.

### Note:
- This test assumes that the `verify_collections` method does not have any type-checking or validation for the `collections` parameter. If there is any type-checking, this test might need to be adjusted to find another area where a `TypeError` can be triggered.
"""


example_prompt_1 = '''
This is an example. The function `b` needs to be analyzed is as below:
```python
def b(x, y):
    return c(x * 2, y["user_id"])
```

You are provided with type information for the arguments of the called function. Use this as backward-flow type information to guide your inference in the caller.
Function being called: c

Arguments defined in this called function: (score, user_id)
Arguments passed to this called function: (x * 2, y["user_id"])

Known type information for this called function's parameters:
```json
{
  "score": {
    "type": "int",
    "fields": \{\},
    "methods": [],
    "built-in": []
  },
  "user_id": {
    "type": "str",
    "fields": \{\},
    "methods": [],
    "built-in": []
  }
}
```

Please infer the type, fields, methods, and built-in characteristics of each parameter based on its usage within the function `b`, and using any constraints from the callee if available. Provide the result in JSON format. Please only output the JSON result without any additional explanations or comments.
'''

example_response_1 = '''
```json
{
  "x": {
    "type": "int",
    "fields": \{\},
    "methods": [],
    "built-in": []
  },
  "y": {
    "type": "dict",
    "fields": {
      "user_id": {
        "type": "str",
        "fields": \{\},
        "methods": [],
        "built-in": []
      }
    },
    "methods": [],
    "built-in": ["__getitem__"]
  }
}
```
'''

example_prompt_2 = '''
This is an example. The function `handler` needs to be analyzed is as below:
```python
def handler(request):
    token = request.user.token
    return validate(token)
```

You are provided with type information for the arguments of the called function. Use this as backward-flow type information to guide your inference in the caller.
Function being called: validate

Arguments defined in this called function: (token)
Arguments passed to this called function: (request.user.token)

Known type information for this called function's parameters:
```json
{
  "token": {
    "type": "str",
    "fields": {},
    "methods": [],
    "built-in": []
  }
}
```

Please infer the type, fields, methods, and built-in characteristics of each parameter based on its usage within the function `b`, and using any constraints from the callee if available. Provide the result in JSON format. Please only output the JSON result without any additional explanations or comments.
'''

example_response_2 = '''
```json
{
  "request": {
    "type": "class",
    "fields": {
      "user": {
        "type": "class",
        "fields": {
          "token": {
            "type": "str",
            "fields": \{\},
            "methods": [],
            "built-in": []
          }
        },
        "methods": [],
        "built-in": []
      }
    },
    "methods": [],
    "built-in": []
  }
}
```
'''


infer_system_prompt = '''You are an expert in Python type inference and static code analysis. Your task is to analyze a single function call within a chain of method invocations. You are provided with only one function call at a time, along with the code and known type information of both the caller and the callee. Your objective is to infer the structure and type of each parameter of the caller function. This includes:
- The parameter’s type (e.g., int, str, List[str], custom class, etc.)
- Any required fields or attributes
- Any required custom methods
- Relevant built-in behaviors or characteristics
    
You must base your inference on two sources of information:
- Caller Usage: Analyze how each parameter is used inside the caller function (e.g., arithmetic, method calls, attribute access, passed to other functions).
- Callee Constraints: Analyze what the callee function expects, based on how the corresponding arguments are passed and any known type information of the callee’s parameters.
    '''
    # - The type constraints imposed by the callee. That is, match each parameter in the call to its corresponding parameter in the callee’s definition, and use its expected type and usage pattern to constrain your inference of the caller’s variable types.


infer_instruction_prompt = f'''Your task is to analyze the parameters of a provided function.
You'll see detailed input formats, tasks, and output formats below. Please follow them strictly.
Input Conditions:
    - A Python function code snippet that demonstrates how the parameters are used.
    - Parameters may be built-in types (e.g., list, dict, etc.) or custom objects.
    - For custom objects, fields and methods may be inferred from usage within the function body.
    
Analysis Requirements:
    - Type: Determine whether the parameter is a custom object or a built-in object.
    - Fields: If the parameter is a custom object, list its fields and their types. If a field is also a custom object, recursively describe its structure.
    - Custom Methods: List any custom methods called on the parameter.
    - Built-in Characteristics: List supported Python built-in methods or dunder methods (e.g., __iter__, __getitem__, etc.).
    
Output Format:
Provide the analysis results in JSON format, structured as follows:
```json
{{
    "parameter_name": {{
        "type": "class/dict/list/other",
        "fields": {{
            "field_name": {{
                "type": "field_type",
                "fields": {{...}},  // Recursively describe if the field is a custom object
                "methods": ["method1", "method2"],
                "built-in": ["__iter__", "__getitem__"]
            }}
        }},
        "methods": ["method1", "method2"],
        "built-in": ["__iter__", "__getitem__"]
    }}
}}
```

Notice:
1. Please pay attention to whether the parameters have a constructor, and there may be fields defined within the constructor.
2. Use backward type constraints if available to constrain your inference.
'''

iterative_infer_system_prompt = f'''
You are an expert in Python type inference and static code analysis. Your objective is to infer the structure and type constraints of each parameter in a given function, under different analysis phases. This includes:
- Type: Determine whether the parameter is a custom object or a built-in object.
- Fields: If the parameter is a custom object, list its fields and their types. If a field is also a custom object, recursively describe its structure.
- Custom Methods: List any custom methods called on the parameter.
- Built-in Characteristics: List supported Python built-in methods or dunder methods (e.g., __iter__, __getitem__, etc.).

Your task is composed of two phases:

## Phase 1: Inference Based on a TypeError

You will be provided with a focal function that raises a `TypeError`. Your goal in this phase is to:
- Analyze the usage of each parameter inside the function.
- Infer the specific type structures that would trigger this TypeError.
- Focus only on type patterns that are consistent with the error's triggering condition.

## Phase 2: Backward Type Propagation Through a Call Chain

You will then be provided a sequence of caller–callee function pairs, going backwards from the focal function to earlier entry points.  
At each step, your job is to reconstruct the caller’s parameter type constraints that would allow the error-triggering configuration to propagate through the call chain.

For each caller–callee pair:
- Caller Usage: Infer the types of the caller's parameters by analyzing how they are used (e.g., arithmetic, attribute access, indexing, or passed as arguments).
- Callee Constraints: Incorporate any known type constraints of the callee's parameters and how arguments are passed to it.

## Output Format (Required)

Return your result using the following JSON structure for each parameter:

```json
{{
    "parameter_name": {{
        "type": "class/dict/list/other",
        "fields": {{
            "field_name": {{
                "type": "field_type",
                "fields": {{...}},  // Recursively describe if the field is a custom object
                "methods": ["method1", "method2"],
                "built-in": ["__iter__", "__getitem__"]
            }}
        }},
        "methods": ["method1", "method2"],
        "built-in": ["__iter__", "__getitem__"]
    }}
}}
```

If a valid configuration of types can no longer be inferred without contradiction, report the inference as unsatisfiable. In that case: 
- Return 'Unable to satisfy' at the begining of the response.
- Summarize the current inferred process.
- Identify the point of failure in the call chain.

## Input Conditions

- Each function snippet may use built-in or user-defined types.
- Parameter types and structures should be inferred based on:
  - How parameters are used within the function.
  - Any known types or constraints passed down from previous analysis (e.g., "backward constraints").
  - Observations from constructors (e.g., fields initialized in `__init__`).
- Recursive inference is required for nested custom types.


## Important Notes

1. Use all available context (including known constraints from callee or prior inference) to guide your reasoning.
2. Be recursive when custom fields themselves are objects.
3. Your reasoning must be consistent with both local usage and cross-function relationships.
4. Your response must contain only the final JSON output, with no explanation or commentary.

You will first be provided with two example conversations (marked with "This is an example") to help you learn the task format.  
After that, begin processing new inputs based on the instructions above.
'''


type_verification_system_prompt = '''You are an expert in Python static analysis, type inference, and unit test reasoning. Your task is to verify whether a TypeError raised during the execution of a unit test is a true positive, meaning that it corresponds to the intended focal method in the codebase and is triggered under valid type constraints as previously inferred.

You will be provided with the following inputs:
1. Parameter Tracing Analysis: A step-by-step inference of type constraints propagated through the call chain, ending at the focal method that contains the known TypeError.
2. Generated Unit Test: The code of a test that triggers a TypeError.
3. Test Execution Result: The exact traceback or runtime output when the test is executed.

Your task is to analyze these inputs and determine whether:
- The test inputs satisfy the inferred type constraints at each step of the call chain.
- The execution path of the test indeed reaches the focal method where the TypeError is defined.
- The TypeError observed in the traceback is due to the focal method, not caused earlier or in unrelated locations.

If all of the above are true, the result is a true positive.  
If any condition is violated (e.g., incorrect types, or the test fails earlier), the result is a false positive.

Your output should include:
1. A binary decision: `"true_positive"` or `"false_positive"`
2. A short explanation of your reasoning:
    - Were the type constraints followed?
    - Did the execution reach the focal method?
    - Did the TypeError occur in the correct context?
3. If the test is a false positive, try to identify the actual source of the TypeError (e.g., mismatched types, early failure), and suggest a correction or retry strategy.

Output Format (Required):
Return your result using the following JSON structure:
```json
{{
    "decision": "true_positive" | "false_positive",
    "confidence": "high" | "medium" | "low", // Indicate your confidence level
    "reasoning": "Your reasoning here.",
    "suggestion": "Your suggestion here."  // Only if the test is a false positive
}}
```
'''

semantic_verification_system_prompt = '''You are an expert in Python testing and type analysis.  
Your goal is to verify that the observed exception in the candidate test is purely a TypeError caused by the intended type mismatch—and not a false positive arising from wrong usage of parameters or invalid inputs upstream.

Below are two guiding examples:
### Example A: True TypeError

```python
# Function under test
def add_strings_and_ints(a, b):
    # Expects both a and b to be of the same type
    return a + b

# Candidate test
def test_add_type_error():
    # a is a string, b is an integer → TypeError on '+' between str and int
    result = add_strings_and_ints("hello", 5)
```

- Failure:  
  TypeError: can only concatenate str (not "int") to str

- Why “true TypeError”:  
  The operation `a + b` itself is invalid given mismatched types.  
  If we correct both to the same type (e.g., both ints or both str), the error disappears.


### Example B: False-Positive TypeError

```python
# Function under test
def process_list(items):
    # Supposed to sum all ints in the list
    total = 0
    for x in items:
        total += x
    return total

# Candidate test
def test_process_list_type_error():
    # Wrong usage: passing None instead of a list
    result = process_list(None)
```

- Failure:  
  TypeError: 'NoneType' object is not iterable

- Why NOT the intended TypeError:  
  The error occurs at the iteration step (`for x in items`), because `items` is `None`, not a list.  
  This is a false positive: the test violates the basic input constraint (“must be an iterable of ints”) rather than exposing a mismatch inside the core summing logic.  
  If we pass a valid list (e.g., `[1,2,3]`), no error occurs; this demonstrates that the exception does not arise from a deeper type mismatch in the loop body itself.

Your output should include:
1. A binary decision: `"true_positive"` or `"false_positive"`
2. A short explanation of your reasoning:
    - Were the type constraints followed?
    - Did the TypeError occur in the correct semantic context?
3. If the test is a false positive, try to identify the actual source of the TypeError (e.g., mismatched types, early failure), and suggest a correction or retry strategy.

Output Format (Required):
Return your result using the following JSON structure:
```json
{{
    "decision": "true_positive" | "false_positive",
    "confidence": "high" | "medium" | "low", // Indicate your confidence level
    "reasoning": "Your reasoning here.",
    "suggestion": "Your suggestion here."  // Only if the test is a false positive
}}
```
'''

coordinator_system_prompt = '''You are the Test Evaluation Coordinator, responsible for aggregating feedback from multiple “Re-Think” lens agents and deciding whether a generated unit test is ready to pass to the final Judge or needs to be refined.

You will receive:

1. Candidate Test
  The source code of the candidate test
  
2. Lens Reports
  A JSON object where each key is the lens name and each value is an object:
  {
    "Type-Consistency": { "decision": "true_positive" | "false_positive", "confidence": "high" | "medium" | "low", "reasoning": "…", "suggestion": "…" },
    "Semantic-Invariance": { "decision": "true_positive" | "false_positive", "confidence": "high" | "medium" | "low", "reasoning": "…", "suggestion": "…" },
  }

Task:  
1. Compute an overall confidence score by weighting each lens’s `confidence` (you may treat all weights equally, unless a lens is marked critical).  
2. If all critical lenses have `status: "true_positive"` and the overall confidence is higher than medium, decide "true_positive".  
3. Otherwise, decide "false_positive" and identify the strongest failure signals.

**Output Format:**  
Return a JSON object:
```json
{
  "decision": "true_positive" | "false_positive",
  "overall_score": "high" | "medium" | "low",
  "failed_lenses": [ ... ],  // list of lens names that failed
  "rationale": "…brief explanation for the decision and summarize suggestions from other agents…"
}
```
'''

generation_system_prompt = (
        "You are an intelligent and expert programming assistant that helps users write high-quality Python unit tests.\n"
        "You will first be provided with one or more rounds of type inference results. These describe the types, fields, methods, "
        "and built-in characteristics of parameters involved in a chain of function calls, inferred through their usage.\n"
        "After the type inference phase is complete, you will be provided with the focal function's code context.\n"
        "Your task is to generate meaningful and thorough Python unit tests for the focal function using the combined context "
        "from type inference and the function implementation.\n"
        "When generating code, always format it using triple backticks and the 'python' tag, like this: ```python <code> ```.\n"
        "Make sure the generated tests are syntactically correct, logically sound, and cover normal behavior, edge cases, "
        "and valid inputs based on the inferred types and structure."
    )

judgement_system_prompt = '''You are an expert static analyzer and programming assistant specialized in detecting potential Python TypeErrors.

You will be given a complete call chain involving multiple functions, including parameter usage and type information inferred from both code and context. Your task is to assess whether the parameter flow along this call chain is at risk of causing a TypeError.

You must reason about:
- Type mismatches between expected and actual arguments at each step.
- Reassignments, casts, or indirect usages that could invalidate type assumptions.
- The final operation in the chain, which might invoke a method or operation that fails under the passed-in type.

Make your decision based on a semantic, cross-function understanding of how the input parameter flows and transforms along the chain.

Do not assume runtime state or actual values unless clearly given. Focus on logical risks that could trigger a TypeError due to invalid type usage.

You will be asked to output:
1. A risk level: `"high"`, `"moderate"`, or `"low"`.
2. A justification summarizing what part of the chain is risky and why.

Always be precise, conservative, and context-aware.
'''