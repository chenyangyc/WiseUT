from collections import defaultdict
from .base_item import Item

class Branch:
    def __init__(self, line_number, column_number, end_line_number, end_column_number, content, related_funcs = set(), related_vars = set()):
        self.line_number = line_number  # 所在的行号（从 1 开始）
        self.column_number = column_number  # 所在行中的列偏移量（从 0 开始）
        self.end_line_number = end_line_number  # 结束的行号
        self.end_column_number = end_column_number  # 结束的列偏移量
        self.content = content # 语句的具体内容
        self.statically_identifier_dict = defaultdict(str)  # 该分支的标识符，变量名->类型，静态结果
        self.dynamically_identifier_dict = defaultdict(str) # 动态结果
        self.have_complex_object = False # 是否有复杂对象
        self.have_function_call = False # 是否有函数调用
        self.related_vars = related_vars # 与该分支有关的变量
        self.statically_related_funcs = related_funcs
        self.related_funcs = set() # 与该分支有关的函数
        self.related_class = set() # 与该分支有关的类
        self.belong_function = None # 该分支所属的函数
        self.is_covered = False
        
    def set_statically_identifier(self, variable_name, variable_type):
        self.statically_identifier_dict[variable_name] = variable_type
    
    def set_dynamically_identifier(self, variable_name, variable_type):
        self.dynamically_identifier_dict[variable_name] = variable_type

    def set_have_complex_object(self):
        self.have_complex_object = True

    def set_have_function_call(self):
        self.have_function_call = True
    
    def add_related_vars(self, related_vars):
        self.related_vars.update(related_vars)
    
    def add_related_funcs(self, related_funcs):
        self.related_funcs.update(related_funcs)
    
    def set_belong_function(self, belong_function):
        self.belong_function = belong_function
    
    def set_covered(self):
        self.is_covered = True

    def add_related_class(self, related_class):
        self.related_class.add(related_class)