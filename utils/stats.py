from pathlib import Path
import asyncio
import os


class Stats:
  def __init__(self):
    self.interface = os.getenv('INTERFACE')
    self.storage = Path(os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', '..', '.wg'))
    self.users = self._get_users()
    
  def _get_users(self):
    users = {}
    for entry in self.storage.iterdir():
      if entry.is_dir():
        pubkey_file = entry / 'public.key'
        if pubkey_file.exists():
          with open(pubkey_file, 'r') as f:
            users[f.read().strip()] = entry.name
    return users
    
  async def _get_wg_stats(self) -> list[dict]:
    proc = await asyncio.create_subprocess_exec(
      'sudo', 'wg', 'show', self.interface, 'dump',
      stdout=asyncio.subprocess.PIPE,
      stderr=asyncio.subprocess.PIPE
    )
    stdout, _ = await proc.communicate()
    
    stats = []
    for line in stdout.decode().splitlines()[1:]:
      fields = line.split('\t')
      stats.append({
        'pubkey': fields[0],
        'endpoint': fields[2].split(':')[0].strip(),
        'latest_handshake': int(fields[4]) if fields[4].isdigit() else None,
        'received': int(fields[5]),
        'sent': int(fields[6])
      })
    return stats
  
  async def collect_stats(self):
    gathered = {}
    stats = await self._get_wg_stats()
    for stat in stats:
      puid = self.users[stat.pop('pubkey')]      
      gathered[puid] = stat
    return gathered
