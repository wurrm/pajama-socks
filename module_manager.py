from aioprocessing import AioProcess, AioQueue, AioJoinableQueue
from types import ModuleType
import sys
import websockets
import json
import asyncio
import re

from modules import *
from modules.utils import sql
from modules.utils.moduletools import BaseModule

MANAGER_ACTIONS = ['wake', 'enable', 'disable', 'start', 'stop', 'stop_all', 'refresh', 'refresh_all', 'sleep']

class Manager:
    def __init__(self):
        self.config = self._load_config('module_server_config.json')
        self.db = sql.db_init(self.config['database_url'])
        self._init_module_server()
        self.modules = self.get_modules() 
        self.processes = {}

    def _load_config(self, cfg):
        with open(cfg, 'r') as f:
            return json.load(f)

    def _init_module_server(self):
        addr,port = self.config['uri']
        sql.ModuleServer.get_or_create(
                url=':'.join(self.config['uri'])+'/main'
        )

    def get_modules(self):
        _modules = dict([(k,v) for k,v in globals().items() if isinstance(v, ModuleType)])
        modules = {}
        for name, module in _modules.items():
            for attr in module.__dict__.values():
                try:
                    if issubclass(attr, BaseModule) and attr != BaseModule:
                        # ensure initialised in case db entry does not exist
                        m = attr()
                        modules.update({name: [attr, sql.Module.get(sql.Module.name == attr.__name__)]})
                except TypeError:
                    continue
        return modules

    async def start(self, module_name):
        if not self.modules[module_name][1].enabled:
            return False
        elif module_name in self.processes.keys():
            return True
        module_class = self.modules[module_name][0]
        input_queue = AioJoinableQueue()
        output_queue = AioQueue()
        module_instance = module_class(input_queue, output_queue)
        proc = AioProcess(target=module_instance.run)
        proc.start()
        self.processes.update({module_name: [
            proc,
            input_queue,
            output_queue,
            re.compile(r'^{}$'.format(module_instance.route))
            ]
        })
        return True

    async def wake(self):
        mod_res = []
        for k in self.modules.keys():
            if not self.modules[k][1].enabled:
                mod_res.append(False)
            else:
                mod_res.append(await self.start(k))
        return mod_res
    
    async def stop(self, module_name):
        p = self.processes[module_name][0]
        inp = self.processes[module_name][1]
        await inp.coro_put(None)
        await inp.coro_join()
        await p.coro_join()
        self.processes.pop(module_name)
        return True
    
    async def stop_all(self):
        mod_res = []
        ps = list(self.processes.keys())
        for k in ps:
            mod_res.append(await self.stop(k))
        return mod_res

    async def refresh(self, module_name):
        if module_name in self.processes.keys():
            await self.stop(module_name)
        if self.modules[module_name][1].enabled:
            await self.start(module_name)
            return True
        else:
            return False
    
    async def refresh_all(self):
        mod_res = []
        for k in self.modules.keys():
            mod_res.append(await self.refresh(k))
        return mod_res

    async def enable(self, module_name):
        m = self.modules[module_name][1]
        m.enabled = True
        m.save()
        return True

    async def disable(self, module_name):
        m = self.modules[module_name][1]
        m.enabled = False
        m.save()
        return True

    async def sleep(self):
        await self.stop_all()
        sys.exit()

    async def handler(self, websocket, route):
        payload = await websocket.recv()
        j = json.loads(payload)
        act = j['action']
        args = j.get('args', [])
        kwargs = j.get('kwargs', {})
        if act in MANAGER_ACTIONS:
            action = getattr(self, act)
            try:
                r = await action()
            except TypeError:
                r = await action(*args)
            await websocket.send(json.dumps(r))
        for proc, inq, outq, regex_pattern in self.processes.values():
            if regex_pattern.match(route):
                await inq.coro_put([act, args, kwargs])
                response = await outq.coro_get()
                await websocket.send(json.dumps(response))
    
    def run(self):
        loop = asyncio.get_event_loop()
        addr,port = self.config['uri']
        loop.run_until_complete(websockets.serve(self.handler, addr, port))
        loop.run_forever()
        loop.close()

if __name__ == '__main__':
    main = Manager()
    main.run()
