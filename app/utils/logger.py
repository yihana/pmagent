import logging
import os
import sys
from typing import Optional

def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """
    간단한 로거 팩토리.
    - 환경변수 LOG_LEVEL 사용(없으면 INFO)
    - 중복 핸들러 추가를 방지함
    """
    if level is None:
        level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
        level = getattr(logging, level_name, logging.INFO)

    logger = logging.getLogger(name)

    if getattr(logger, "_custom_configured", False):
        logger.setLevel(level)
        return logger

    logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    fmt = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
    formatter = logging.Formatter(fmt)
    handler.setFormatter(formatter)

    logger.propagate = False
    logger.addHandler(handler)

    logger._custom_configured = True

    return logger