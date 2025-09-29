def construct_type_constraints_verification_prompt(
    focal_method, module_relative_dir, triggering_method, called_name_chain, code_content, focal_test_res
):
    return f'''This is the generated test file for the function "{focal_method.name}" located in the module "{module_relative_dir}". The TypeError is expected to be triggered from the focal function "{focal_method.name}" via the function "{triggering_method.name}", following the call chain:  
"{called_name_chain}". Below is the content of the generated test file:
```python
{code_content}
```

This is the execution result of the test:
```
{focal_test_res}
```
Based on the above, please determine whether this TypeError is a true positive or a false positive. If it is a false positive, explain where the deviation occurred and what caused the TypeError, and suggest a correction or retry strategy as required in the system prompt.'''


def construct_type_constraints_verification_prompt_non_buggy(
    focal_method, module_relative_dir, triggering_method, called_name_chain, code_content, focal_test_res
):
    return f'''This is the generated test file for the function "{focal_method.name}" located in the module "{module_relative_dir}". Below is the content of the generated test file:
```python
{code_content}
```

This is the execution result of the test:
```
{focal_test_res}
```
Based on the above, please determine whether this TypeError is a true positive or a false positive. If it is a false positive, explain where the deviation occurred and what caused the TypeError, and suggest a correction or retry strategy as required in the system prompt.'''


def construct_semantic_verification_prompt(
    focal_method, module_relative_dir, code_content, focal_test_res
):
    return f'''This is the generated test file for the function "{focal_method.name}" located in the module "{module_relative_dir}". Now perform the Semantic-Invariance check on the candidate test provided below based on the code the the type analysis.

Candidate Test Code
```python
{code_content}
```

Execution Trace
```
{focal_test_res}
```
Based on the above, please determine whether this TypeError is a true positive or a false positive. If it is a false positive, explain where the deviation occurred and what caused the TypeError, and suggest a correction or retry strategy as required in the system prompt.
'''


def construct_coordinator_prompt(
    focal_method, module_relative_dir, code_content, type_verification_response, semantic_verification_response
):
    return f'''This is the generated test file for the function "{focal_method.name}" located in the module "{module_relative_dir}":
```python
{code_content}
```

This is the re-think decisions from other agents:
{{
"Type-Consistency": {type_verification_response},
"Semantic-Invariance": {semantic_verification_response}
}}

Accordingly to the above information, please provide your decision as required in the system prompt. 
'''


def construct_refine_prompt(current_condition, focal_method, triggering_method, called_name_chain, verification_response, code_content, focal_test_res):
    return f'''{current_condition} The expected TypeError should be triggered from the focal function "{focal_method.name}" through the function "{triggering_method.name}", following the call chain:
"{called_name_chain}". 
Below is the content of the generated test file:
```python
{code_content}
```

This is the execution result of the test:
```
{focal_test_res}
```

However, the current test does not follow the call path or violates the expected type constraints:
{verification_response}

Please revise the test file to ensure it:
- Follows the correct call chain.
- Satisfies the inferred type constraints and semantic context at each step.
- Triggers the TypeError at the correct location.
Your goal is to produce a test file that results in a true positive.
'''


def construct_refine_prompt_non_buggy(current_condition, focal_method, triggering_method, called_name_chain, verification_response, code_content, focal_test_res):
    return f'''{current_condition} Below is the content of the generated test file:
```python
{code_content}
```

This is the execution result of the test:
```
{focal_test_res}
```

However, the current test does not follow the call path or violates the expected type constraints:
{verification_response}

Please revise the test file to ensure it:
- Follows the correct call chain.
- Satisfies the inferred type constraints and semantic context at each step.
Your goal is to produce a test file that results in a true positive.
'''