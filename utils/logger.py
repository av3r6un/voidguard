from logging.handlers import RotatingFileHandler
import logging
import os

LOG_FILEPATH=os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', '..', 'logs', 'all.log')

def setup_logger(name: str = None, console: bool = False) -> logging.Logger:
  """ Sets up and returns a logger with the specified name"""
  logger = logging.getLogger(name)
  logger.setLevel(logging.INFO)

  formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"
  )

  console_handler = logging.StreamHandler()
  console_handler.setLevel(logging.ERROR)
  console_handler.setFormatter(formatter)

  check_logs_folder()

  file_handler = RotatingFileHandler(
    LOG_FILEPATH, maxBytes=5*1024*1024, backupCount=5
  )
  file_handler.setLevel(logging.DEBUG)
  file_handler.setFormatter(formatter)

  if console: logger.addHandler(console_handler)
  logger.addHandler(file_handler)

  logger.propagate = False

  return logger

def check_logs_folder():
  if not os.path.exists(os.path.split(LOG_FILEPATH)[0]):
    os.makedirs(os.path.split(LOG_FILEPATH)[0])
