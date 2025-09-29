from .base_item import Item
    
    
class TestProgram(Item):
    """ Object representing a test program with its attributes
    """
    def __init__(self, content, target_function, single_target_time=0, total_time=0, coverage=None, called_functions=None, covered_functions=None):
        super().__init__()
        self.content = content
        self.target_function = target_function
        self.single_target_time = single_target_time
        self.total_time = total_time
        
        self.coverage = coverage if coverage is not None else dict()
        
        
        self.single_func_cov_rate = 0
        self.single_func_cov_lines = set()
        
        self.called_functions = called_functions if called_functions is not None else []
        self.covered_functions = covered_functions if covered_functions is not None else []
        
        
    def add_called_function(self, called_function):
        self.called_functions.append(called_function)
        
    def add_covered_function(self, covered_function):
        self.covered_functions.append(covered_function)
    
    def set_coverage(self, coverage: set):
        self.coverage = coverage
    
    def set_single_func_cov_rate(self, single_func_cov_rate):
        self.single_func_cov_rate = single_func_cov_rate
    
    def set_single_func_cov_lines(self, single_func_cov_lines):
        self.single_func_cov_lines = single_func_cov_lines

    def set_time(self, time):
        self.time = time
        
    def set_total_time(self, total_time):
        self.total_time = total_time

if __name__ == '__main__':
    pass