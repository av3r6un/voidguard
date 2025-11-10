from aiohttp.web import Request, middleware, json_response
from .logger import setup_logger

logger = setup_logger('MW|AUTH')

@middleware
async def jwt_middleware(req: Request, handler, *args):
  remote = req.headers.get('X-Forwarded-For')
  auth_header = req.headers.get('Authorization', '')
  if not auth_header.startswith('Bearer '):
    logger.error(f'Req from {remote} failed authentication. Missing token')
    return json_response(data=dict(status='error', message='Missing or invalid Auhtorization Header'), status=401)

  token = auth_header.split(' ')[-1]
  from src import settings
  if len(token) != 32 or token != settings.SERVER_TOKEN:
    logger.error(f'Req from {remote} failed authentication. Invalid token')
    return json_response(data=dict(status='error', message='Invalid token'), status=401)
  
  return await handler(req)


middlewares=[jwt_middleware]
