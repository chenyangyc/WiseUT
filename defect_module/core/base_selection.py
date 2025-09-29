import random
from .base_item import Item

class RouletteWheelSelection(Item):
    def __init__(self, items = None):
        self.items = items if items is not None else []
        self.total_weight = sum(item.weight for item in items) if len(items) > 0 else 0

    def select_item(self):
        random_value = random.uniform(0, self.total_weight)
        cumulative_weight = 0

        for item in self.items:
            cumulative_weight += item.weight
            if random_value <= cumulative_weight:
                item.add_chosen_time()
                return item


# if __name__ == '__main__':
#     # 例子用法
#     item1 = Item(0.2, '1')
#     item2 = Item(0.5, '2')
#     item3 = Item(0.3, '3')

#     items_list = [item1, item2, item3]

#     roulette_wheel = RouletteWheelSelection(items_list)
    
#     for i in range(0, 100):
#         chosen_item = roulette_wheel.select_item()
#         print("Chosen item:", chosen_item.name)
