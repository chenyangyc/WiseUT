import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent))
import re
import json
from collections import defaultdict
from code_parser import Code_AST
from code_parser.CodeBLEU.calc_code_bleu import get_codebleu
from nltk.translate.bleu_score import sentence_bleu, SmoothingFunction
from data.config import model, client, logger


def count_leading_spaces(s):
    match = re.match(r'^ +', s)
    if match:
        return len(match.group(0))
    return 0

add_comment_prompt = "Please add comments following the 'Arrange-Act-Assert' pattern which explains what is happening and the intentions of what is being done, and add docstring for the test. The test case is:\n```java\n{function_content}\n```\nDo not change the origin statement and structure. Add comments without changing any code. "

example_function_content_1 = """
public void testReplace_StrMatcher_String_int_int_int_VaryMatcher() {
    StrBuilder sb = new StrBuilder();
    sb.replace(A_NUMBER_MATCHER, "***", 0, sb.length(), -1);
    assertEquals("", sb.toString());
}
"""

example_response_1 = """
/**
 * Tests the {@code replace} method of {@code StrBuilder} with varying matchers.
 * This test verifies that the replace operation works correctly when using a specific
 * matcher ({@code A_NUMBER_MATCHER}) to replace parts of the string with a given replacement
 * string ("***") within specified start and end indices.
 * 
 * The test ensures that the string builder is initially empty and remains empty after
 * the replace operation, confirming that the replace method handles the case correctly.
 */
public void testReplace_StrMatcher_String_int_int_int_VaryMatcher() {
    // Arrange
    StrBuilder sb = new StrBuilder();

    // Act
    sb.replace(A_NUMBER_MATCHER, "***", 0, sb.length(), -1);

    // Assert
    assertEquals("", sb.toString());
}
"""

example_function_content_2 = """public void testAsWriter() throws Exception {
    StrBuilder sb = new StrBuilder("base");
    Writer writer = sb.asWriter();
    writer.write('l');
    writer.write(new char[] {'i', 'n'});
    writer.write(new char[] {'n', 'e', 'r'}, 1, 2);
    writer.write(" rout");
    writer.write("ping that server", 1, 3);
    assertEquals("baseliner routing", sb.toString());
}"""

example_add_comment_prompt_2 = add_comment_prompt.format(function_content=example_function_content_2)

example_response_2 = """```java
/**
 * Tests the {@code asWriter} method of {@code StrBuilder} to ensure it correctly writes
 * characters and strings to the underlying {@code StrBuilder} instance.
 * 
 * This test verifies that various write operations using the {@code Writer} returned by
 * {@code asWriter} correctly append the written content to the {@code StrBuilder}, and
 * the final content matches the expected string.
 * 
 * @throws Exception if an error occurs during the test execution
 */
public void testAsWriter() throws Exception {
    // Arrange
    StrBuilder sb = new StrBuilder("base");
    Writer writer = sb.asWriter();

    // Act
    writer.write('l');
    writer.write(new char[] {'i', 'n'});
    writer.write(new char[] {'n', 'e', 'r'}, 1, 2);
    writer.write(" rout");
    writer.write("ping that server", 1, 3);

    // Assert
    assertEquals("baseliner routing", sb.toString());
}
```"""

def parse_output(output):
    # Define the regex pattern to match code blocks
    output = output.replace('```java', '```')
    output = output.replace('```json', '```')
    
    pattern = r"```(.*?)```"
    
    # Find all matches in the output
    matches = re.findall(pattern, output, re.DOTALL)
    
    # Return the first match if it exists
    if matches:
        return matches[0]
    else:
        return None

def reformat_func_name(function_content, origin_function_name):
    current_function_ast = Code_AST(code=function_content, lang="java").ast
    current_function_name = current_function_ast.get_function_name() + '()'
    new_function_name = origin_function_name + '()'
    func_content = function_content.replace(current_function_name, new_function_name)
    return func_content

def collect_all_nodes(node):
    nodes = []
    # Inner function to perform DFS recursively
    def dfs(current_node):
        if not current_node:
            return
        # Add the current node to the list
        nodes.append(current_node)
        # Recursively visit all children
        for child in current_node.children:
            dfs(child)
    # Start DFS from the root node
    dfs(node)
    return nodes

def construct_node_line_dict(node):
    results = defaultdict(list)
    # Inner function to perform DFS recursively
    def dfs(current_node):
        if not current_node:
            return
        # Add the current node to the list
        if current_node.type != 'fill_in':
            current_line = current_node.start_point[0]
            results[current_line].append(current_node)
        # Recursively visit all children
        for child in current_node.children:
            dfs(child)
    # Start DFS from the root node
    dfs(node)
    return results

def find_line_comments_with_siblings(node):
    result = []

    # If the node has children, process them
    if node.children:
        for i, child in enumerate(node.children):
            # Check if the current node is a 'line_comment'
            if child.type == 'line_comment':
                # Add the 'line_comment' node and its siblings to the result
                siblings = [sibling for h, sibling in enumerate(node.children) if h > i and sibling.type != 'fill_in']
                key = child
                value = [single_node for single_node in siblings if single_node.type != 'fill_in']
                result.append((key, value))
            
            # Recursively search in the child node
            result.extend(find_line_comments_with_siblings(child))
    return result

def find_block_comment(node):
    result = []
    if node.children:
        for child in node.children:
            if child.type == 'block_comment':
                result.append(child)
            result.extend(find_block_comment(child))
    return result

def calculate_similarity(node1, node2):
    """
    Calculate similarity between two AST nodes.

    Args:
        node1 (ASTNode): The first AST node.
        node2 (ASTNode): The second AST node.

    Returns:
        float: The similarity score (0 to 1).
    """
    # Check for exact match in node types
    type_similarity = 1.0 if node1.type == node2.type else 0.0
    
    if type_similarity == 0:
        return 0.0
    
    # # Calculate BLEU score for the source similarity
    # bleu_score = get_codebleu(["expected = sb.write('haha')"], "expected = sb.write('?')", "java", '0.25,0.25,0.25,0.25')

    reference = node1.source.split(' ')
    candidate = node2.source.split(' ')
    bleu_score = sentence_bleu(
        [reference], candidate, smoothing_function=SmoothingFunction().method1
    )
    # Combine the two scores; adjust weights as needed
    combined_similarity = 0.5 * type_similarity + 0.5 * bleu_score
    return combined_similarity

def find_most_similar_node(tgt_node, all_source_nodes):
    # Calculate similarity for each source node with the target node
    node_similarity = {src_node: calculate_similarity(src_node, tgt_node) for src_node in all_source_nodes}
    
    # Find the node with the maximum similarity score
    most_similar_node = max(node_similarity, key=node_similarity.get)
    max_similarity = node_similarity[most_similar_node]

    return most_similar_node, max_similarity

def extract_specified_node(node, node_type):
    results = set()
    # If the node has children, process them
    if node.children:
        for i, child in enumerate(node.children):
            # Check if the current node is a 'line_comment'
            if child.type == node_type:
                # Add the 'line_comment' node and its siblings to the result
                results.add(child)
            
            results = results.union(extract_specified_node(child, node_type))

    return results

def extract_target_variable_names(node):
    variables = extract_specified_node(node, 'variable_declarator')
    variable_names = set()
    for var in variables:
        for child in var.children:
            if child.type == 'identifier':
                variable_names.add(child.source)
                break

    identifiers = extract_specified_node(node, 'identifier')
    identifier_names = set([i.source for i in identifiers])

    target_variable_names = variable_names.intersection(identifier_names)
    return target_variable_names

def merge_add_comment_tests(origin_test_content, comment_test_content):
    origin_test_ast = Code_AST(code=origin_test_content, lang="java").ast
    all_source_nodes = collect_all_nodes(origin_test_ast)
    
    add_comment_test_ast = Code_AST(code=comment_test_content, lang="java").ast
    line_comments_with_siblings = find_line_comments_with_siblings(add_comment_test_ast)
    node_line_dict = construct_node_line_dict(add_comment_test_ast)
    
    block_comments = find_block_comment(add_comment_test_ast)
    if block_comments:
        block_comments = block_comments[0]
    
    merged_test_content = origin_test_content
    added_nodes = set()
    processed_comment_nodes = set()
    tmp_cnt = 1
    
    tmp_dict = defaultdict(list)
    for comment_node, sibling_nodes in line_comments_with_siblings:
        tmp_dict[comment_node] = sibling_nodes
        
    for comment_node, sibling_nodes in line_comments_with_siblings:
        if comment_node in processed_comment_nodes:
            continue
        processed_comment_nodes.add(comment_node)
        
        comment = comment_node.source
        if not any([i in comment.lower() for i in ['arrange', 'act', 'assert']]):
            continue
        
        if len(node_line_dict[comment_node.start_point[0]]) > 1: 
            tgt_node = node_line_dict[comment_node.start_point[0]][0]
        else:
            if sibling_nodes:
                tgt_node = sibling_nodes[0]
            else:
                continue
        
        if tgt_node.type == 'line_comment':
            prev_node = tgt_node
            first = True
            while tgt_node.type == 'line_comment' and (first or tgt_node.start_point[0] == prev_node.start_point[0] + 1):
                processed_comment_nodes.add(tgt_node)
                new_com = tgt_node.source.replace('//', '')
                comment = f'{comment}: {new_com}'
                prev_node = tgt_node
                tgt_node = tmp_dict[tgt_node][0]
                first = False
            
        if tgt_node.type == 'line_comment':
            continue

        most_similar_node, max_similarity = find_most_similar_node(tgt_node, all_source_nodes)
        
        if max_similarity < 0.55 and most_similar_node.source not in tgt_node.source:
            continue
        
        origin_source = most_similar_node.source_line
        origin_indent = ' ' * count_leading_spaces(origin_source)
        
        if origin_source in added_nodes:
            continue
        added_nodes.add(origin_source)
        
        if tmp_cnt > 1:
            new_source = f'\n{origin_indent}{comment}\n{origin_source}'
        else:
            new_source = f'{origin_indent}{comment}\n{origin_source}'
        
        merged_test_content = merged_test_content.replace(origin_source, new_source)
        tmp_cnt += 1
    
    if block_comments:
        merged_test_content = block_comments.source_line + '\n' + merged_test_content
    return merged_test_content

def construct_rename_dict(json_output):
    origin_dict = json.loads(json_output)
    # count the occurances of values
    value_count = defaultdict(int)
    for key, value in origin_dict.items():
        value_count[value] += 1
    
    # reverse the dict keys list
    keys = list(origin_dict.keys())
    keys.reverse()
        
    for key in keys:
        value = origin_dict[key]
        if value_count[value] > 1:
            origin_dict[key] = value + str(value_count[value])
            value_count[value] -= 1
    return origin_dict

def extract_variables_need_renaming(node, rename_dict):
    all_identifiers = extract_specified_node(node, 'identifier')
    initial_rename_identifiers = [i for i in all_identifiers if i.source in rename_dict]
    filtered_rename_identifiers = []
    
    for single_identifier in initial_rename_identifiers:
        identifier_parent = single_identifier.parent
        
        if identifier_parent.type == 'method_invocation' and single_identifier.origin_node == identifier_parent.origin_node.child_by_field_name('name'):
            continue
        filtered_rename_identifiers.append(single_identifier)
    return filtered_rename_identifiers

def merge_rename_tests(rename_dict, source_code, source_ast):
    # Extract all identifiers from the node
    all_identifiers = extract_variables_need_renaming(source_ast, rename_dict)

    # Dictionary to store modifications based on byte ranges
    modify_dict = {}
    for identifier in all_identifiers:
        identifier_name = identifier.source   
        range = (identifier.start_byte, identifier.end_byte)
        modify_dict[range] = rename_dict[identifier_name]

    # Convert the source code into a list of characters for mutable operations
    source_list = list(source_code)

    # Apply the modifications to the source list
    # Note: Need to process ranges in reverse order to avoid issues with shifting indices
    for range, value in sorted(modify_dict.items(), key=lambda x: x[0][0], reverse=True):
        start, end = range
        source_list[start:end] = value

    # Join the list back into a string
    modified_source = ''.join(source_list)
    
    return modified_source

def construct_rename_prompt(target_variables, function_content, test_name):
    prompt = "Please rename the test and the variables in the test case to more descriptive names that reflect their purpose and usage. The test case is:\n```java\n"
    prompt += function_content
    prompt += "\n```\n"
    prompt += "The names that need to be renamed are:\n"
    target_variables = [test_name] + list(target_variables)
    for var in target_variables:
        prompt += f"- {var}\n"
    prompt += '\nProvide the result in json format with the following structure:\n```json\n{\n'
    for index, var in enumerate(target_variables):
        postfix = ','
        if index == len(target_variables) - 1:
            postfix = ''
        prompt += f'    "{var}": "<new_name>"{postfix}\n'
    prompt += '}\n```\n Note that the json content should be wrapped in a pair of ```'
    return prompt



def refine_single_test(function_content):
    # refine
    input_add_comment_prompt = add_comment_prompt.format(function_content=function_content)
    
    comment_messages = [
        {"role": "user", "content": example_add_comment_prompt_2},
        {"role": "assistant", "content": example_response_2}, 
        {"role": "user", "content": input_add_comment_prompt},
    ]
    # logger.debug(f"Invkoing the llm for comment")
    response = client.chat.completions.create(
        model=model,
        messages=comment_messages,
        temperature=0.0,
        # stop=["```"],
    )
    add_comment_response = response.choices[0].message.content
    # logger.debug(f"Get the response for comment")
    add_comment_test = parse_output(add_comment_response)
    
    if add_comment_test is None:
        return
        
    add_comment_test = merge_add_comment_tests(function_content, add_comment_test)
    
    # logger.debug(f"processed for comment")
    
    comment_test_ast = Code_AST(code=add_comment_test, lang="java").ast
    target_variables = extract_target_variable_names(comment_test_ast)
    test_name = comment_test_ast.get_function_name()

    rename_prompt = construct_rename_prompt(target_variables, add_comment_test, test_name)

    rename_message = [
        {"role": "user", "content": rename_prompt},
    ]
    # logger.debug(f"Invkoing the llm for rename")
    response = client.chat.completions.create(
        model=model,
        messages=rename_message,
        temperature=0.0,
        # stop=["```"],
    )
    rename_response = response.choices[0].message.content
    
    json_output = parse_output(rename_response)
    try:
        # 处理大模型重命名后的重名情况
        rename_dict = construct_rename_dict(json_output)
    except:
        # return add_comment_test
        for key, value in rename_dict.items():
            rename_dict[key] = key.strip()

    new_test = merge_rename_tests(rename_dict, add_comment_test, comment_test_ast)
    return new_test
