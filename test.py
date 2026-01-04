from utils.stats import test
import inspect
import sys


def test_stats():
  return test()

def _get_all_tasks():
  current_module = sys.modules[__name__]
  funcs = {}
  for name, obj in inspect.getmembers(current_module, inspect.isfunction):
    if obj.__module__ != __name__:
      continue
    if name.startswith('_'):
      continue
    if name in ['main']:
      continue
    funcs[name] = obj
  return funcs


def main():
  funcs = _get_all_tasks()
  if not funcs: print('Nothing to run!'); sys.exit(-1)
  args = sys.argv[1:]
  if args:
    for name in args:
      fn = funcs.get(name)
      if not fn: continue
      print(f'Executing {name}!')
      print(f'Result:', fn())
  else:
    for name, fn in funcs.items():
      print(f'Executing {name}!')
      print('Result:', fn())


if __name__ == '__main__':
  main()
