import sys
sys.path.append(r'Z:\config')
import patch_mt5
patch_mt5.apply_ipc_patch()
import MetaTrader5 as mt5

import time
time.sleep(15)
res = mt5.initialize(r'C:\Program Files\MetaTrader 5 IC Markets Global\terminal64.exe', timeout=30000, portable=True)
print('MT5 Initialized on start:', res)
print('MT5 initialization error:', mt5.last_error(), flush=True)

import rpyc
from rpyc.utils.server import ThreadedServer
from rpyc.utils.classic import ClassicService

if __name__ == '__main__':
    t = ThreadedServer(ClassicService, port=18812, hostname='127.0.0.1', protocol_config={'allow_all_attrs': True})
    print('Starting RPyC Server on 18812...')
    t.start()
