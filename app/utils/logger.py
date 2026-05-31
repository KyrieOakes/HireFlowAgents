"""
app/utils/logger.py
====================
日志记录工具。

提供统一的日志记录接口，让系统运行时的信息可追踪。
日志记录了系统在做什么、什么时候做的、有没有出错。

使用 Python 内置的 logging 模块，它比 print() 更好因为:
1. 可以同时输出到控制台和文件
2. 有日志级别 (DEBUG/INFO/WARNING/ERROR)
3. 自动记录时间戳
"""

import logging
import sys

# 创建日志记录器
# getLogger(__name__) 用当前模块名作为 logger 名
# 这样在日志中可以看到是哪段代码输出的日志
logger = logging.getLogger(__name__)

# 设置日志级别
# DEBUG < INFO < WARNING < ERROR < CRITICAL
# 设置为 INFO 意味着 INFO 及以上级别的日志才会显示
logger.setLevel(logging.INFO)

# 创建控制台输出的 handler
# StreamHandler 将日志输出到终端 (sys.stdout)
console_handler = logging.StreamHandler(sys.stdout)
# 设置日志格式: [时间] [级别] [模块名] 消息内容
console_handler.setFormatter(
    logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
)
logger.addHandler(console_handler)


def get_logger():
    """获取全局日志记录器。"""
    return logger
