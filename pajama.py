import asyncio
import json

from functools import reduce

import websockets
import discord

from modules.utils import sql
from modules.utils.moduletools import Command, command, checks

class Builtin:
    """Outlines the Commands the bot should always have, without need to defer to a module"""
    def __init__(self, client):
        # Load in bot commands
        self.commands = [k for k,v in self.__class__.__dict__.items() if isinstance(v, Command)]

    @command
    @checks('administrator')
    async def get_server_options(self, message):
        with self.db.connection_context():
            all_opts = sql.OptionLookup.select()
            opts = sql.ServerOption.select().where(sql.ServerOption.server == message.server.id)
            s = ''
            for o in opts:
                t = '{}: {}\n'.format(o.option.option, o.value)
                if not t:
                    t = '{}: {}\n'.format(o.option.option, o.option.default)
                s += t
            await self.send_message(message.channel, s)

    @command
    @checks('administrator')
    async def set_server_option(self, message, option, new_val):
        with self.db.connection_context():
            opt = sql.OptionLookup.get(sql.OptionLookup.option == option)
            (sql.ServerOption
                .insert({sql.ServerOption.option: opt, sql.ServerOption.value: new_val, sql.ServerOption.server: message.server.id})
                .on_conflict('replace').execute())

    @command
    @checks('bot_owner')
    async def module_enable(self, module_serv, module_name):
        await self.call_module(module_serv, 'enable', [module_name])

    @command
    @checks('bot_owner')
    async def module_disable(self, module_serv, module_name):
        await self.call_module(module_serv, 'disable', [module_name])

    @command
    @checks('bot_owner')
    async def module_start(self, module_serv, module_name):
        await self.call_module(module_serv, 'start', [module_name])

    @command
    @checks('bot_owner')
    async def module_stop(self, module_serv, module_name):
        await self.call_module(module_serv, 'stop', [module_name])

    @command
    @checks('bot_owner')
    async def module_stop_all(self, module_serv, module_name):
        await self.call_module(module_serv, 'stop_all')

    @command
    @checks('bot_owner')
    async def module_refresh(self, module_serv, module_name):
        await self.call_module(module_serv, 'refresh', [module_name])

    @command
    @checks('bot_owner')
    async def module_refresh_all(self, module_serv, module_name):
        await self.call_module(module_serv, 'refresh_all')

    @command
    @checks('bot_owner')
    async def module_sleep(self, module_serv):
        await self.call_module(module_serv, 'sleep')


class PajamaClient(discord.Client):

    def __init__(self, *args, **kwargs):
        self.config = self._load_config('data/config.json')
        self.modules = {}
        self.db = sql.db_init(self.config['database_url'])
        self.token = self.config['bot_token']
        self.builtins = Builtin(self)

        super().__init__(*args, **kwargs)

    def _load_config(self, cfg):
        with open(cfg, 'r') as f:
            return json.load(f)
    
    async def get_prefixes(self, channel):
        if channel.is_private:
            server_prefix = ' '
        else:
            with self.db.connection_context():
                server_prefix = sql.Server[channel.server.id].prefix
        return (self.config['global_prefix'], server_prefix)

    async def _checks(self, message, cmd):
        # True -> allowed action
        # False -> disallowed action
        # channel > server > global 

        if message.author.id in self.config.get('bot_owner_ids'):
            return True

        with self.db.connection_context():
            author = sql.User[message.author.id]
            channel = sql.Channel[message.channel.id]
            command = sql.Command.get_or_none(sql.Command.name == cmd)
        module = command.module
        permissions = command.required_permissions

        # owner check
        if 'bot_owner' in permissions:
            return False

        # general user checks
        if author.banned:
            return False

        # enabled check
        if not module.enabled or not command.enabled:
            return False
        
        sess_perms = message.author.permissions_in(message.channel)
        for row in permissions:
            if not getattr(sess_perms, row.perm):
                return False
        
        # channel/server checks
        if not message.channel.is_private:
            server = channel.server
            if author == server.owner:
                return True
            # blacklist/whitelist
            # whitelist > blacklist but discord hierarchy remains
            if hasattr(command, 'whitelist'):
                if command.whitelist.get(sql.Whitelist.channel == channel):
                    return True
                else:
                    return False

            if hasattr(command, 'blacklist'):
                if command.blacklist.get(sql.Blacklist.channel == channel):
                    return False
                else:
                    return True

            if hasattr(command, 'whitelist'):
                if command.whitelist.get(sql.Whitelist.server == server):
                    return True
                else:
                    return False

            if hasattr(command, 'blacklist'):
                if command.blacklist.get(sql.Blacklist.server == server):
                    return False
                else:
                    return True

            # finally 
            if channel.can_post:
                return True
            else:
                return False

    async def call_module(self, url, action, *args, **kwargs):
        async with websockets.connect('ws://{}'.format(url)) as websocket:
            payload = json.dumps({"action":action, "args":args, "kwargs":kwargs})
            await websocket.send(payload)
            response = json.loads(await websocket.recv())
            return response

    async def on_ready(self):
        module_responses = []
        with self.db.connection_context():
            for m in sql.ModuleServer.select():
                try:
                    res = await self.call_module(url=m.url, action='wake')
                    module_responses += res
                except:
                    print('Error connecting to {}'.format(m.url)) 

        total_modules = len(module_responses)
        enabled_modules = module_responses.count(True)
        disabled_modules = module_responses.count(False)
        missing_modules = total_modules - (enabled_modules + disabled_modules)

        print('Logged in as {}'.format(self.user.name))
        print('ID: {}'.format(self.user.id))

        print('\nModules:')
        print('{} Total'.format(total_modules))
        print('{} Enabled'.format(enabled_modules))
        print('{} Disabled'.format(disabled_modules))
        print('{} Missing'.format(missing_modules))
    
    def iter_getattr(self, obj, attr):
        attrs = attr.split('.')
        while len(attrs) > 0:
            obj = getattr(obj, attrs.pop(0))
        return obj
    
    async def preprocess_command(self, cmd, message):
        kwargs = {}
        with self.db.connection_context():
            try:
                command = sql.Command.get(sql.Command.name == cmd)
            except:
                if message.author.id in self.config['bot_owner_ids']:
                    return {}
                else:
                    return None
        kwargs.update({
            'server.id': message.server.id,
            'message.id': message.id,
            'channel.id': message.channel.id
        })
        for field in command.required_context:
            k = field.attr
            v = self.iter_getattr(message, k)
            kwargs.update({k: v})
        return kwargs

    async def log_message(self, message):
        with self.db.connection_context():
            sql.Message.create(
                    id = message.id,
                    content = message.content,
                    timestamp = message.timestamp,
                    channel = message.channel.id,
                    author = message.author.id
            )

    async def on_message(self, message):
        self.db.connect(reuse_if_open=True)
        author = message.author
        if author.bot:
            return
        sql_author,created = sql.User.get_or_create(id=author.id)
        sql_author.name = author.name
        sql_author.bot = author.bot
        if created:
            sql_author.save(force_insert=True)
        else:
            sql_author.save()

        content = message.content
        prefixes = await self.get_prefixes(message.channel)
        prefix = ''
        for p in prefixes:
            if content.startswith(p):
                prefix = p
        if not p:
            await self.log_message(message)
        else:
            cmd,*args = content[len(prefix):].split(' ')
            if cmd in self.builtins.commands:
                self.db.close()
                act = getattr(self.builtins, cmd)
                if cmd == 'set_server_option' or 'get_server_options':
                    await act.func(self, message, *args)
                else:
                    await act.func(self, *args)
                return
            kwargs = await self.preprocess_command(cmd, message)
            if kwargs is None:
                return
            if await self._checks(message, cmd):
                module = sql.Command.get(sql.Command.name == cmd).module
                rattr,*rargs = await self.call_module(module.url, cmd, *args, **kwargs)
                for i in range(len(rargs)):
                    obj = ''
                    for k,v in kwargs.items():
                        if v == rargs[i]:
                            if k == 'message.id':
                                obj = message
                            else:
                                var = k.split('.')[0]
                                obj = getattr(message, var)
                            rargs[i] = obj
                action = getattr(self, rattr)
                await action(*rargs)
        self.db.close()

    async def on_server_join(self, server):
        self.db.connect(reuse_if_open=True)
        print('Joined server {}'.format(server.name))
        owner = server.owner
        sql.User.get_or_create(
                id=owner.id,
                name=owner.name,
                bot=False
        )

        joined_server = sql.Server.create(
                id=server.id,
                name=server.name,
                owner=owner.id
        )

        channel_dicts = []
        for ch in server.channels:
            channel_dicts.append({
                'id': ch.id,
                'name': ch.name,
                'server': server.id
            })

        with self.db.atomic():
            sql.Channel.insert_many(channel_dicts).execute()
        self.db.close()
    
    async def on_server_remove(self, server):
        with self.db.connection_context():
            sql.Server[server.id].delete_instance()
        
    async def on_server_update(self, before, after):
        if before.name != after.name:
            with self.db.connection_context():
                serv = sql.Server[after.id]
                serv.name = after.name
                serv.save()

    async def on_channel_create(self, channel):
        if not channel.is_private:
            with self.db.connection_context():
                ch = sql.Channel(
                        id=channel.id,
                        name=channel.name,
                        server=sql.Server[channel.server.id]
                )
                ch.save()

    async def on_channel_delete(self, channel):
        with self.db.connection_context():
            sql.Channel[channel.id].delete_instance()

    async def on_channel_update(self, before, after):
        if before.name != after.name:
            with self.db.connection_context():
                ch = sql.Channel[after.id]
                ch.name = after.name
                ch.save()
        
if __name__ == '__main__':
    client = PajamaClient()
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(client.start(client.token))
    except KeyboardInterrupt:
        loop.run_until_complete(client.logout())
    finally:
        loop.close()

## RUNTIME
# message send
#   - on response, do relevant action
# changes to servers/channels/users
# shutdown
#   - ensure everything safely downs
