"""
日志工具
"""
import logging
import sys


def get_logger(name: str = 'simulation', level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            '[%(asctime)s] %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        ))
        logger.addHandler(handler)
        logger.setLevel(level)
    return logger
