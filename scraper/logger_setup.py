"""
Structured (JSON) logging so scraper run logs are machine-readable and easy
to grep in GitHub Actions run output.
"""
import logging
import sys

from pythonjsonlogger import jsonlogger


def get_logger(name: str = "brandywine_scraper") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # avoid duplicate handlers on repeated calls

    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
