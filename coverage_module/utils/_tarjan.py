from collections import defaultdict

class TarjanSCC:
    def __init__(self, graph):
        self.graph = graph
        self.time = 0
        self.discovery_time = None
        self.low_link = None
        self.stack = None
        self.in_stack = None
        self.scc = None
        self.scc_id = 0
        self.scc_components = []

    def find_scc(self):
        """使用 Tarjan 算法查找所有强连通分量。"""
        num_nodes = max(self.graph) + 1
        self.discovery_time = [0] * num_nodes
        self.low_link = [0] * num_nodes
        self.stack = []
        self.in_stack = [False] * num_nodes
        self.scc = [0] * num_nodes

        for node in self.graph.keys():
            if self.discovery_time[node] == 0:
                self._tarjan(node)

        return self.scc, self.scc_id, self.scc_components

    def _tarjan(self, node):
        """执行 Tarjan 强连通分量算法的辅助函数。"""
        self.time += 1
        self.discovery_time[node] = self.low_link[node] = self.time
        self.stack.append(node)
        self.in_stack[node] = True

        for neighbor in self.graph.get(node, []):
            if self.discovery_time[neighbor] == 0:
                self._tarjan(neighbor)
                self.low_link[node] = min(self.low_link[node], self.low_link[neighbor])
            elif self.in_stack[neighbor]:
                self.low_link[node] = min(self.low_link[node], self.discovery_time[neighbor])

        if self.discovery_time[node] == self.low_link[node]:
            scc_component = []
            while True:
                top_node = self.stack.pop()
                self.in_stack[top_node] = False
                self.scc[top_node] = self.scc_id
                scc_component.append(top_node)
                if top_node == node:
                    break
            self.scc_components.append(scc_component)
            self.scc_id += 1


class TopologicalSort:
    def __init__(self, scc_components, original_graph):
        self.scc_components = scc_components
        self.component_graph = defaultdict(list)
        self.build_component_graph(original_graph)
        self.visited = set()
        self.sort_order = []
    


    def build_component_graph(self, original_graph):
        """从原始图和强连通分量构建组件图。"""
        for node, neighbors in original_graph.items():
            component_id = -1
            for component in self.scc_components:
                if node in component:
                    component_id = self.scc_components.index(component)
                    break
            if component_id not in self.component_graph:
                self.component_graph[component_id] = []
            for neighbor in neighbors:
                neighbor_component_id = -1
                for component in self.scc_components:
                    if neighbor in component:
                        neighbor_component_id = self.scc_components.index(component)
                        break
                if component_id != neighbor_component_id and neighbor_component_id not in self.component_graph[component_id]:
                    self.component_graph[component_id].append(neighbor_component_id)

    def dfs(self, component_id):
        """执行深度优先搜索以进行拓扑排序。"""
        if component_id not in self.visited:
            self.visited.add(component_id)
            for neighbor in self.component_graph[component_id]:
                self.dfs(neighbor)
            self.sort_order.append(component_id)

    def sort(self):
        """对组件图进行拓扑排序。"""
        for component_id in range(len(self.scc_components)):
            if component_id not in self.component_graph:
                continue
            if component_id not in self.visited:
                self.dfs(component_id)
        # self.sort_order.reverse()  # 反转以获得拓扑排序的顺序


class UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))
        self.rank = [0] * n
        self.count = n

    def find(self, x):
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x, y):
        rootX = self.find(x)
        rootY = self.find(y)
        if rootX != rootY:
            if self.rank[rootX] > self.rank[rootY]:
                self.parent[rootY] = rootX
            elif self.rank[rootX] < self.rank[rootY]:
                self.parent[rootX] = rootY
            else:
                self.parent[rootY] = rootX
                self.rank[rootX] += 1
            self.count -= 1

    def connected(self, x, y):
        return self.find(x) == self.find(y)


def find_connected_components(graph):
    """查找图中的所有连通分量。"""
    nodes = list(graph.keys())
    n = len(nodes)
    uf = UnionFind(n)

    # 将图中的边加入并查集
    for node, neighbors in graph.items():
        node_index = nodes.index(node)
        for neighbor in neighbors:
            neighbor_index = nodes.index(neighbor)
            uf.union(node_index, neighbor_index)

    # 构建连通分量
    components = {}
    for i, node in enumerate(nodes):
        root = uf.find(i)
        if root not in components:
            components[root] = []
        components[root].append(node)

    return list(components.values())


def topu_to_find_related(variable_related):
    """
    Finds the related components and performs topological sorting on them.
    Args:
        variable_related (dict): A dictionary containing information about the variables and their related components.
    Returns:
        None
    Raises:
        None
    """
    variable_index = {}
    index_variable = {}
    index = 0
    for variable in variable_related.keys():
        variable_index[variable] = index
        index_variable[index] = variable
        index += 1
    
    graph = {}
    for variable, info in variable_related.items():
        graph[variable_index[variable]] = []
        for related_variable in info['variable']:
            graph[variable_index[variable]].append(variable_index[related_variable])
    
    connected_components = find_connected_components(graph)

    # print("连通分量:")
    # for component in connected_components:
    #     print(component)

    scc_components = []
    for component in connected_components:
        tarjan = TarjanSCC({node: [n for n in graph[node] if n in component] for node in component})
        _, _, component_scc = tarjan.find_scc()
        scc_components.extend(component_scc)

    # print("\n强连通分量:")
    # for component in scc_components:
    #     print(component)


    for i, component in enumerate(connected_components):
        topo_sort = TopologicalSort(scc_components, {node: [n for n in graph[node] if n in component] for node in component})
        topo_sort.sort()
        
        father_component_graph = {}
        for component_id in topo_sort.component_graph.keys():
            if component_id not in father_component_graph:
                father_component_graph[component_id] = []
            for neighbor in topo_sort.component_graph[component_id]:
                if neighbor not in father_component_graph:
                    father_component_graph[neighbor] = []
                father_component_graph[neighbor].append(component_id)

        # print(f"\n连通分量 {i+1} 中强连通分量的拓扑排序顺序:")
        for component_id in topo_sort.sort_order:
            # print(scc_components[component_id])
            
            component_methods = []
            for variable in scc_components[component_id]:
                for method in variable_related[index_variable[variable]]['method']:
                    component_methods.append(method)
                for add_variable in scc_components[component_id]:
                    if add_variable != variable:
                        variable_related[index_variable[add_variable]]['variable'].append(index_variable[variable])
            component_methods = list(set(component_methods))
            for variable in scc_components[component_id]:
                variable_related[index_variable[variable]]['method'] = component_methods
            for father_component in father_component_graph[component_id]:
                for method in component_methods:
                    for fa_variable in scc_components[father_component]:
                        variable_related[index_variable[fa_variable]]['method'].append(method)
                for variable in scc_components[component_id]:
                    for fa_variable in scc_components[father_component]:
                        variable_related[index_variable[fa_variable]]['variable'].append(index_variable[variable])
        
        for variable, variable_info in variable_related.items():
            variable_related[variable]['variable'] = list(set(variable_related[variable]['variable']))
            variable_related[variable]['method'] = list(set(variable_related[variable]['method']))
    return variable_related
    
if __name__ == '__main__':

    graph = {
        0: [1, 5],
        1: [2],
        2: [3, 4],
        3: [4, 1],
        4: [],
        5: [6],
        6: [0],
        7: [8],
        8: [9],
        9: [10],
        10: [11],
        11: [7]
    }

    connected_components = find_connected_components(graph)

    print("连通分量:")
    for component in connected_components:
        print(component)

    scc_components = []
    for component in connected_components:
        tarjan = TarjanSCC({node: [n for n in graph[node] if n in component] for node in component})
        _, _, component_scc = tarjan.find_scc()
        scc_components.extend(component_scc)

    print("\n强连通分量:")
    for component in scc_components:
        print(component)

    for i, component in enumerate(connected_components):
        topo_sort = TopologicalSort(scc_components, {node: [n for n in graph[node] if n in component] for node in component})
        topo_sort.sort()

        print(f"\n连通分量 {i+1} 中强连通分量的拓扑排序顺序:")
        for component_id in topo_sort.sort_order:
            print(scc_components[component_id])
    
    variable_related = {
        'var1': {'variable': ['var2', 'var5'], 'method': ['method1', 'method2']},
        'var2': {'variable': ['var3'], 'method': ['method3']},
        'var3': {'variable': ['var4'], 'method': ['method5']},
        'var4': {'variable': ['var2', 'var6'], 'method': ['method6']},
        'var5': {'variable': [], 'method': ['method7']},
        'var6': {'variable': ['var4'], 'method': ['method8']},
    }
    variable_related = topu_to_find_related(variable_related)
    print(variable_related)