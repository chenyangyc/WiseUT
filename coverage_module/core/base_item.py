# 用于随机选择的基类，包括被选择的概率以及被选择过的次数
class Item():
    def __init__(self, weight:int = 1, chosen_time:int = 1, useful_time: int = 1):
        self.weight = weight 
        self.chosen_time = chosen_time
        self.useful_time = useful_time
    
    def add_chosen_time(self):
        self.chosen_time += 1
        self.modify_weight()
    
    def add_useful_time(self):
        self.useful_time += 1
        self.modify_weight()
    
    def modify_weight(self):
        self.weight = self.useful_time / self.chosen_time
