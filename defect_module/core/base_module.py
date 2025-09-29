from .base_item import Item


class Module(Item):
    def __init__(self, name, content, module_path, imports=None, module_dir=None, functions=None, classes=None):
        super().__init__()
        self.name = name
        self.content = content
        self.module_path = module_path
        self.module_dir = module_dir
        self.functions = functions if functions is not None else []
        self.classes = classes if classes is not None else []
        self.imports = imports if imports is not None else []
        
        self.total_line_num = 0
        self.fields = []
    
    def add_function(self, new_func):
        self.functions.append(new_func)
    
    def add_class(self, new_class):
        self.classes.append(new_class)
        
    def add_imports(self, new_import):
        self.imports.append(new_import)
        
    def set_fields(self, fields):
        self.fields = fields
        
    def set_total_line_num(self, total_line_num):
        self.total_line_num = total_line_num