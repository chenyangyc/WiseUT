from .base_item import Item


class File(Item):
    def __init__(self, file_path, content, package):
        super().__init__()
        self.file_path = file_path
        self.file_name = file_path.split('/')[-1]
        self.content = content
        self.classes = set()
        self.methods = set()
        self.import_map = {}
        self.belong_package = package
        # self.package_path = 'package_path'
        
    
    def add_method(self, new_func):
        self.methods.add(new_func)
    
    def add_class(self, new_class):
        self.classes.add(new_class)
