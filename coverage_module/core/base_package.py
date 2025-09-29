from .base_item import Item


class Package(Item):
    def __init__(self, package_name, package_path = None):
        super().__init__()
        self.name = package_name
        self.methods = set()
        self.classes = set()
        self.files = set()
        self.import_map = {}
        self.package_path = package_path if package_path else ''
        
    
    def add_method(self, new_func):
        self.methods.add(new_func)
    
    def add_class(self, new_class):
        self.classes.add(new_class)
    
    def add_file(self, new_file):
        self.files.add(new_file)
