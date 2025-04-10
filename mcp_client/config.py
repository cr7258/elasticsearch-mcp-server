from dotenv import load_dotenv
import logging
from os import getenv
import pydantic_settings as py_set

load_dotenv()

class LoggerConfig(py_set.BaseSettings):
    file: str = "logs/notifications_telegram.log"
    format: str = "[{name}]-[%(levelname)s]-[%(asctime)s]-[%(message)s]"
    to_file: bool = getenv("LOG_TO_FILE", "False").lower() == "true"
    to_terminal: bool = getenv("LOG_TO_TERMINAL", "True").lower() == "true"
    file_level: int = logging.DEBUG
    terminal_level: int = logging.INFO


class ElasticsearchConfig(py_set.BaseSettings):
    host: str = getenv("ELASTICSEARCH_HOST", "")
    port: int = int(getenv("ELASTICSEARCH_PORT", "30930"))
    scroll_size: int = 10_000
    scroll: str = "1m"
    timeout: int = 60


class AnthropicConfig(py_set.BaseSettings):
    model: str = getenv("MODEL", "claude-3-5-sonnet-20241022")
    max_tokens_message: int = int(getenv("MAX_TOKENS_MESSAGE", "1000"))


class Config(py_set.BaseSettings):
    logger: LoggerConfig
    elasticsearch: ElasticsearchConfig
    anthropic: AnthropicConfig


def read_config() -> Config:
    logger_config = LoggerConfig()
    elasticsearch_config = ElasticsearchConfig()
    anthropic_config = AnthropicConfig()
    return Config(
        logger=logger_config,
        elasticsearch=elasticsearch_config,
        anthropic=anthropic_config,
    )


def get_logger(name: str) -> logging.Logger:
    log_config = LoggerConfig()
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(log_config.format.format(name=name))
    if log_config.to_file:
        file_handler = logging.FileHandler(log_config.file, mode="a")
        file_handler.setLevel(log_config.file_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    if log_config.to_terminal:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_config.terminal_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    return logger
