from base64 import b64encode
import secrets
import string


def create_string(length: int = 8) -> str:
  forbidden = {':', '\n', '\r', ' '}
  alphabet = ''.join(ch for ch in (string.ascii_letters + string.digits) if ch not in forbidden)
  return ''.join(secrets.choice(alphabet) for _ in range(length))

def create_passwd(username:str):
  pswd = create_string(8)
  return pswd, b64encode(username.encode() + pswd.encode('utf-8')).decode()
