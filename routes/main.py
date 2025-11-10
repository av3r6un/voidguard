from aiohttp.web import RouteTableDef, Request, json_response, Response, FileResponse
from src.utils import Stats, setup_logger, create_passwd
from src.modules import WireGuard, SquidManager
import os

main = RouteTableDef()
wg = WireGuard()
squid = SquidManager()
logger = setup_logger('ROUTE|MAIN')


@main.get('/status')
async def handle_status(req: Request) -> Response:
  return json_response(dict(status='success', body=dict(ok=True)))


@main.post('/peer')
async def handle_peer(req: Request) -> Response:
  data = (await req.json()).get('data', {})
  try:
    config_path, save_as = wg.add_user(**data)
    return FileResponse(
      config_path,
      headers={'Content-Disposition': f'attachment; filename="{save_as}"'}
    )
  except Exception as e:
    logger.error(str(e))
    return json_response(dict(status='error', message=str(e)), status=400)


@main.patch('/peer')
async def edit_peer(req: Request) -> Response:
  data = (await req.json()).get(data, {})
  try:
    success = getattr(wg, f'{data.pop("action")}_peer')(**data)
    return json_response(dict(status='success', body=success))
  except Exception as e:
    logger.error(str(e))
    return json_response(dict(status='error', message=str(e)), status=400)


@main.delete('/peer')
async def remove_peer(req: Request) -> Response:
  uid = req.query.get('puid')
  try:
    succeed = wg.remove_user(uid)
    return json_response(dict(status='success', body=dict(ok=succeed)))
  except Exception as e:
    logger.error(str(e))
    return json_response(dict(status='error', message=str(e)), status=400)


@main.get('/stats')
async def handle_stats(req: Request) -> Response:
  try:
    stats = Stats()
    traffic = await stats.collect_stats()
    return json_response(dict(status='success', body=traffic))
  except Exception as ex:
    logger.error(str(ex))
    return json_response(dict(status='error', message=str(ex)), status=400)


@main.post('/proxy/users')
async def add_proxy_user(req: Request) -> Response:
  data = (await req.json()).get('data', {})
  if not data.get('username'):
    return json_response(dict(status='error', mesasage='At least username is required!'), status=400)
  passwd, hashed = create_passwd(data.get('username'))
  success, message = await squid.add_user(data.get('username'), passwd)
  body = dict(username=data.get('username'), password=hashed, ip_address=os.getenv("LOCAL_IP"), port=os.getenv("SQUID_PORT"))
  return json_response(dict(status='success' if success else 'error', message=message, body=body), status=200 if success else 400)


@main.delete('/proxy/users')
async def delete_proxy_user(req: Request) -> Response:
  username = req.query.get('username')
  if not username:
    return json_response(dict(status='error', message='Username is required!'), status=400)
  success, message = await squid.delete_user(username)
  return json_response(dict(status='success' if success else 'error', message=message), status=200 if success else 400)


@main.patch('/proxy/users')
async def purge_proxy_users(req: Request) -> Response:
  days = req.query.get('days', 30)
  success, body = await squid.purge_inactive(int(days))
  return json_response(dict(status='success' if success else 'error', body=body), status=200 if success else 400)
