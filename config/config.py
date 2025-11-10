from zipfile import ZipFile, ZIP_DEFLATED
import os


class Config:
  priv: str = None
  ip_addr: str = None
  srv_pub: str = None
  local_ip: str = None
  local_port: int = None
  
  def __init__(self, priv, ip_addr, srv_pub, local_ip = None, local_port = None, location = None):
    self.priv = priv
    self.ip_addr = ip_addr
    self.srv_pub = srv_pub
    self.local_ip = local_ip or os.getenv('LOCAL_IP')
    self.local_port = local_port or os.getenv('LOCAL_PORT')
    self.location = location or os.getenv('LOCATION', 'NL')
    
  @staticmethod
  def _load_sample(filename) -> str:
    filepath = os.path.join(os.path.abspath(os.path.dirname(__file__)), f'{filename}.config')
    with open(filepath, 'r') as f:
      return f.read()
    
  @staticmethod
  def _create_allowed(ip_addr):
    return ip_addr.replace(ip_addr.split('.')[-1], '0')
    
  @property
  def config(self) -> str:
    return self._load_sample('client').format(**self.__dict__)
    
  def zip(filepath) -> str:
    with ZipFile(f'{filepath}/wg.zip', 'w', ZIP_DEFLATED) as zfile:
      user_config = os.path.join(filepath, 'wg.conf')
      if not os.path.exists(user_config):
        raise FileNotFoundError(user_config)
      filename = os.path.basename(user_config)
      zfile.write(filepath, arcname=filename)
    return f'{filepath}/wg.zip'
  
  
