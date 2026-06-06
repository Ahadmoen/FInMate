from loguru import logger
import sys

# Remove default logger
logger.remove()

# Add console logger with colors
logger.add(
    sys.stdout,
    colorize=True,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <cyan>{name}</cyan> | <white>{message}</white>",
    level="INFO"
)

# Add file logger to save all logs
logger.add(
    "logs/aiva_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="7 days",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name} | {message}"
)