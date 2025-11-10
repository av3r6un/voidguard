from src.utils import setup_logger
from src.config import Config
from pathlib import Path
import subprocess
import sys
import os

from python_wireguard import Key

logger = setup_logger('WireGuard')

class WireGuard:
  def __init__(self) -> None: 
    self.storage = Path(os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', '..', '.wg'))
    self.storage.mkdir(parents=True, exist_ok=True)
    
  def _get_users(self):
    users = {}
    for entry in self.storage.iterdir():
      if entry.is_dir():
        pubkey_file = entry / 'public.key'
        if pubkey_file.exists():
          with open(pubkey_file, 'r') as f:
            users[entry.name] = f.read().strip()
    return users

  def _save(self, filename, content) -> str:
    path = self.storage / filename
    folder = os.path.split(path)[0]
    if not os.path.exists(folder):
      os.makedirs(folder, exist_ok=True)
    with open(path, 'w') as f:
      f.write(content)
    return path  
    
  def _load_key(self, filename: str) -> Key:
    return Key((self.storage / filename).read_text().strip())
  
  def _create_keys(self, username) -> tuple[Key, Key]:
    client_priv, client_pub = Key.key_pair()
    self._save(f'{username}/private.key', str(client_priv))
    self._save(f'{username}/public.key', str(client_pub))
    return client_priv, client_pub
   
  @staticmethod
  def _add_user_globally(client_pub, ip_addr, isolate) -> None:
    allowed_ips = f"{ip_addr}/32" if isolate else f"{'.'.join(ip_addr.split('.')[:-1])}.0/24"
    subprocess.run(['sudo', 'wg', 'set', os.getenv('INTERFACE'), 'peer', client_pub, 'allowed-ips', allowed_ips], check=True)
    
  def deactivate_peer(self, uuid, **kwargs) -> bool:
    pubkeys = self._get_users()
    subprocess.run(['sudo', 'wg', 'set', os.getenv('INTERFACE'), 'peer', pubkeys[uuid], 'allowed-ips', '0.0.0.0/32'], check=True)
    return True
  
  def reactivate_peer(self, uuid, ip_addr, **kwargs) -> bool:
    pubkeys = self._get_users()
    subprocess.run(['sudo', 'wg', 'set', os.getenv('INTERFACE'), 'peer', pubkeys[uuid], 'allowed-ips', f'{ip_addr}/24'], check=True)
    return True
  
  def remove_user(self, uuid, **kwargs) -> bool:
    pubkeys = self._get_users()
    subprocess.run(['sudo', 'wg', 'set', os.getenv('INTERFACE'), 'peer', pubkeys[uuid], 'allowed-ips', 'remove'], check=True)
    return True
  
  def add_user(self, username, ip_addr, isolate=True, **kwargs) -> tuple[str, str]:
    priv, pub = self._create_keys(username)
    srv_pub = self._load_key('server_public.key')
    config = Config(priv, ip_addr, srv_pub)
    client = config.config
    conf_path = self._save(f'{username}/wg.conf', client)
    self._add_user_globally(str(pub), ip_addr, isolate)
    return conf_path, f'{username}.conf'

