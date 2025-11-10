from aiohttp.web import Application, run_app
from dotenv import load_dotenv
from .utils import middlewares
import logging
import os

load_dotenv(os.path.join(os.path.abspath(os.path.dirname(__file__)), 'config', '.env'))


class Settings:
  SERVER_TOKEN_FILE = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'config', '.uuid')
  
  def __init__(self):
    self.SERVER_TOKEN = self._load_contents(self.SERVER_TOKEN_FILE)
    
  @staticmethod
  def _load_contents(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
      return f.read().strip()

settings = Settings()

def create_app() -> Application:
  from .routes import rts
  app = Application(middlewares=middlewares)
  logging.basicConfig(
    level=logging.INFO, filename='logs/client.log',
    format="%(asctime)s [%(levelname)s] CLIENT: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
  )
  app.add_routes(rts)
  return app


def run():
  app = create_app()
  print('Starting client..')
  run_app(
    app,
    host='0.0.0.0',
    port=int(os.getenv('WEB_PORT')),
    access_log_format='%{X-Forwarded-For}i %s - "%r" (%b | %D) %{User-Agent}i'
  )
