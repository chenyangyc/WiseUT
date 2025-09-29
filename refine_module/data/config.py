import os
import json
import logging
from rich.logging import RichHandler
from openai import OpenAI


code_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
_config_file = os.path.join(code_base, 'main_config.json')

with open(_config_file, 'r', encoding='utf-8') as f:
    CONFIG = json.loads(f.read())['refine']

model = CONFIG['model']
api_key = CONFIG['api_key']
api_base = CONFIG['api_base']

project_names = CONFIG['path_mappings'].keys()

client = OpenAI(
    api_key=api_key,
    base_url=api_base
)

def init_logger(project_name="myproject"):
    logger = logging.getLogger(project_name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False 

    # 清理旧 handler，避免重复打印
    logger.handlers.clear()

    handler = RichHandler(
        rich_tracebacks=True,
        show_time=True,   # 关掉时间
        show_path=True,   # 关掉路径
        show_level=True    # 只保留彩色等级 + message
    )

    # RichHandler 自己控制格式，这里只留 message
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    return logger


# 使用
logger = init_logger("current_file_logger")

