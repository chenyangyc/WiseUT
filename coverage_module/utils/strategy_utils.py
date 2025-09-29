def are_last_three_sets_same(lst):
    if len(lst) < 2:
        return False
    return lst[-1] == lst[-2]

def find_shortest_chains(chains):
    shortest_chains = list()
    min_length = min(len(chain) for chain in chains)
    shortest_chains = [chain for chain in chains if len(chain) == min_length]
    
    return shortest_chains

def called_chain_filtering(single_func):
    callee_chains = [i for i in single_func.callee_chains if i not in single_func.used_callee_chains]
    # 处理callee_chains
    startpoint_chains = {}
    for chain in callee_chains:
        startpoint = chain[0]  # 链的起点

        if startpoint not in startpoint_chains:
            startpoint_chains[startpoint] = []

        startpoint_chains[startpoint].append(chain)

    callee_chains.clear()
    for chains_with_same_startpoint in startpoint_chains.values():
        shortest_callee_chains = find_shortest_chains(chains_with_same_startpoint)
        callee_chains.extend(shortest_callee_chains)
        # 处理 shortest_callee_chain
    # 注意这里用深拷贝
    single_func.using_callee_chains = callee_chains
    

def update_strategies(strtegies_rounds, single_target, direct_selected_examples):
    is_direct_available = not are_last_three_sets_same(strtegies_rounds['direct'])
    is_indirect_available = not are_last_three_sets_same(strtegies_rounds['indirect'])   
    new = not are_last_three_sets_same(strtegies_rounds['new'])
    # 有直接调用的测试样
    if is_direct_available:
        candidate_programs = [i for i in single_target.direct_programs if i not in direct_selected_examples]
        is_direct_available = True if candidate_programs else False
    # 处理可选的链
    if is_indirect_available:
        called_chain_filtering(single_target)
        available_callee_chains = [i for i in single_target.using_callee_chains if i[0].direct_programs]
        is_indirect_available = True if available_callee_chains else False
    
    if is_direct_available or is_indirect_available:
        new = False
    all_conditions = [is_direct_available, is_indirect_available, new]
    return all_conditions