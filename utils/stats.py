from pathlib import Path
import asyncio
import re
import os


class Stats:
  def __init__(self):
    self.interface = os.getenv('INTERFACE')
    self.storage = Path(os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', '..', '.wg'))
    self.users = self._get_users()
    self._WS = re.compile(r"\s+")
    
  @staticmethod
  def _to_int(val: str) -> int:
    try: return int(val)
    except Exception: return 0

  @staticmethod
  def _is_pubkey(token: str) -> bool:
    if token in ['(none)', 'none', '-']: return False
    if len(token) < 20: return False
    return all(c.isalnum() or c in "+/=" for c in token) 
    
  def _get_users(self):
    users = {}
    for entry in self.storage.iterdir():
      if entry.is_dir():
        pubkey_file = entry / 'public.key'
        if pubkey_file.exists():
          with open(pubkey_file, 'r') as f:
            users[f.read().strip()] = entry.name
    return users
  
  def _is_endpoint(self, endpoint: str = None) -> str | None:
    if not endpoint or endpoint == '(none)': return None
    if endpoint.count(":") >= 2 and endpoint.startswith("[") and "]:" in endpoint:
      host = endpoint.split("]:", 1)[0].lstrip("[")
      port = endpoint.split("]:", 1)[1]
      endpoint_ip = host.strip()
      endpoint_port = self._to_int(port.strip())
      ep = f'{endpoint_ip}:{endpoint_port}'
    elif ":" in endpoint:
      host, port = endpoint.rsplit(":", 1)
      endpoint_ip = host.strip()
      endpoint_port = self._to_int(port.strip())
      ep = f'{endpoint_ip}:{endpoint_port}'
    else:
      ep = endpoint.strip()
    return ep
    
  async def _get_wg_stats(self) -> list[dict]:
    proc = await asyncio.create_subprocess_exec(
      'sudo', 'wg', 'show', self.interface, 'dump',
      stdout=asyncio.subprocess.PIPE,
      stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await proc.communicate()
    
    stats = []
    start_idx = 1
    lines = [ln.rstrip("\n") for ln in stdout.decode('utf-8', errors='replace').splitlines() if ln.strip()]
    if not lines: return []
    for line in lines[start_idx:]:
      data = {}
      tokens = self._WS.split(line.strip())
      if not tokens or not self._is_pubkey(tokens[0]): continue
      data['pubkey'] = tokens[0] if tokens else None
      data['endpoint'] = self._is_endpoint(tokens[2]) if len(tokens) > 2 else None
      data['allowed_ips'] = tokens[3] if len(tokens) > 3 else None
      data['latest_handshake'] = self._to_int(tokens[4]) if len(tokens) > 3 else None
      data['received'] = self._to_int(tokens[5]) if len(tokens) > 5 else "0"
      data['sent'] = self._to_int(tokens[6]) if len(tokens) > 6 else "0"
      stats.append(data)
    return stats
  
  async def collect_stats(self):
    gathered = {}
    stats = await self._get_wg_stats()
    for stat in stats:
      puid = self.users[stat.pop('pubkey')]      
      gathered[puid] = stat
    return gathered


def test():
  s = Stats()
  return asyncio.run(s.collect_stats())
