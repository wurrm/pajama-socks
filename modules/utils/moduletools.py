import asyncio
import re
import json
import websockets

from inspect import iscoroutinefunction
from collections import UserDict

from . import sql

from os.path import dirname

class AttrDict(UserDict):
    """Allows us to treat attributes as a dict"""
    def __getattr__(self, attr):
        return self.data[attr]

class Command:
    """Represents a user command"""
    def __init__(self, name, func, help, requires, permissions):
        self.name = name
        self.func = func
        self.help = help
        self.requires = requires
        self.permissions = permissions

def command(cmd):
    """User command decorator"""
    if not hasattr(cmd, 'requires'):
        cmd.requires = []
    if not hasattr(cmd, 'permissions'):
        cmd.permissions = []
    return Command(cmd.__name__, cmd, cmd.__doc__, cmd.requires, cmd.permissions)
    
def requires(*args):
    """Decorator that signifies a Command needs context from the API"""
    def wrapper(cmd):
        cmd.requires = args
        return cmd
    return wrapper

def checks(*args):
    """User permissions decorator"""
    def wrapper(cmd):
        cmd.permissions = args
        return cmd
    return wrapper

class BaseModule:
    """Base class for new modules to inherit"""

    def __init__(self, inq=None, outq=None):
        """Initialise database connection, classify data, create and access tables, create worker queues"""
        # kind of ugly here
        self.config = self._load_config(dirname(dirname(dirname(__file__))) + '/module_server_config.json')
        self.db = sql.db_init(self.config['database_url'])
        self.uri = ':'.join(self.config['uri'])
        self.route = '/' + self.__class__.__name__.lower()
        self.module = self._init_module()
        self.commands = self._init_commands()
        self.options = AttrDict(self.__class__.options)
        self._init_options()
        self.in_queue = inq
        self.out_queue = outq

    def _load_config(self, cfg):
        with open(cfg, 'r') as f:
            return json.load(f)

    def _init_module(self):
        name = self.__class__.__name__
        # refresh tables on startup
        with self.db.connection_context():
            sql.Module.delete().where(sql.Module.name == name).execute()

            module = sql.Module.create(
                    name=name,
                    url=self.uri+self.route
            )
        return module

    def _init_commands(self):
        """Load Commands into tables"""
        command_fields = [sql.Command.name, sql.Command.help, sql.Command.module]
        context_fields = [sql.RequiredContext.attr, sql.RequiredContext.command]
        perms_fields = [sql.RequiredPermission.perm, sql.RequiredPermission.command]
        
        commands = []
        _required_contexts = []
        _required_perms = []
        for k,v in self.__class__.__dict__.items():
            if isinstance(v, Command):
                commands.append((v.name, v.help, self.module))
                _required_contexts.append((v.requires, v.name))
                _required_perms.append((v.permissions, v.name))
        
        self.db.connect()

        sql.Command.insert_many(commands, fields=command_fields).execute()
        
        required_context = []
        for t in _required_contexts:
            attrs = t[0]
            cmd = t[1]
            for attr in attrs:
                required_context.append((attr, sql.Command.get(sql.Command.name == cmd)))
        sql.RequiredContext.insert_many(required_context, fields=context_fields).execute()

        required_perms = []
        for p in _required_perms:
            perms = p[0]
            cmd = p[1]
            for perm in perms:
                required_perms.append((perm, sql.Command.get(sql.Command.name == cmd)))
        sql.RequiredPermission.insert_many(required_perms, fields=perms_fields).execute()
        
        self.db.close()
        return commands

    def _init_options(self):
        """Load options into table"""
        fields = [sql.OptionLookup.option, sql.OptionLookup.default, sql.OptionLookup.module]
        ks = list(self.options.keys())
        vs = list(self.options.values())
        r = [self.module for i in self.options]
        opts = list(zip(ks, vs, r))
        with self.db.connection_context():
            sql.OptionLookup.insert_many(opts, fields=fields).execute()

    async def main(self):
        """Worker function, processes incoming commands and returns to sender"""
        next_task = await self.in_queue.coro_get()
        if next_task is None:
            self.in_queue.task_done()
            raise Exception
        act,args,kwargs = next_task
        action = getattr(self, act).func
        if self.options:
            try:
                with self.db.connection_context():
                    server_options = sql.ServerOption.select().where(sql.ServerOption.server == context['server.id'])
            except:
                server_options = self.options
            kwargs.update({'server_options': server_options})

        response = {}
        if iscoroutinefunction(action):
            response = await action(self, *args, **kwargs)
        else:
            response = action(self, *args, **kwargs)
        await self.out_queue.coro_put(response)
        self.in_queue.task_done()
        
    def run(self):
        loop = asyncio.new_event_loop()
        while True:
            try:
                loop.run_until_complete(self.main())
            except:
                break
        loop.close()
