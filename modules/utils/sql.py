from peewee import *
from playhouse.db_url import connect

db_proxy = Proxy()

class BaseModel(Model):
    class Meta:
        database = db_proxy

# server side
class ModuleServer(BaseModel):
    url = CharField(unique=True)

class Module(BaseModel):
    name = CharField(unique=True)
    enabled = BooleanField(default=True)
    url = CharField()

class Command(BaseModel):
    name = CharField(unique=True)
    enabled = BooleanField(default=True)
    help = CharField(null=True)
    # requires_owner = BooleanField()
    module = ForeignKeyField(Module, backref='commands', on_delete='CASCADE')

class RequiredContext(BaseModel):
    attr = CharField(null=True)
    command = ForeignKeyField(Command, backref='required_context', on_delete='CASCADE')

class RequiredPermission(BaseModel):
    perm = CharField(null=True)
    command = ForeignKeyField(Command, backref='required_permissions', on_delete='CASCADE')

# client side
class User(BaseModel):
    id = IntegerField(primary_key=True)
    name = CharField()
    bot = BooleanField()
    banned = BooleanField(default=False)

class Server(BaseModel):
    id = IntegerField(primary_key=True)
    name = CharField()
    prefix = CharField(max_length=10, default=' ')
    owner = ForeignKeyField(User, backref='owned_servers', on_delete='CASCADE')
    can_post = BooleanField(default=True)

class Channel(BaseModel):
    id = IntegerField(primary_key=True)
    name = CharField()
    server = ForeignKeyField(Server, backref='channels', on_delete='CASCADE')
    can_post = BooleanField(default=True)
    hidden = BooleanField(default=False)

class Message(BaseModel):
    id = IntegerField(primary_key=True)
    content = CharField(max_length=2000)
    timestamp = DateTimeField()
    channel = ForeignKeyField(Channel, backref='messages', on_delete='CASCADE')
    author = ForeignKeyField(User, backref='messages', on_delete='CASCADE')

class OptionLookup(BaseModel):
    option = CharField()
    default = CharField()
    module = ForeignKeyField(Module, backref='options', on_delete='CASCADE')

class ServerOption(BaseModel):
    option = ForeignKeyField(OptionLookup, backref='server_options')
    value = CharField()
    server = ForeignKeyField(Server, backref='options', on_delete='CASCADE')

# kinda client + server side i guess
class Whitelist(BaseModel):
    module = ForeignKeyField(Module, backref='whitelist', on_delete='CASCADE')
    command = ForeignKeyField(Command, backref='whitelist', on_delete='CASCADE')
    server = ForeignKeyField(Server, backref='whitelist', on_delete='CASCADE')
    channel = ForeignKeyField(Channel, backref='whitelist', on_delete='CASCADE')

class Blacklist(BaseModel):
    module = ForeignKeyField(Module, backref='blacklist', on_delete='CASCADE')
    command = ForeignKeyField(Command, backref='blacklist', on_delete='CASCADE')
    server = ForeignKeyField(Server, backref='blacklist', on_delete='CASCADE')
    channel = ForeignKeyField(Channel, backref='blacklist', on_delete='CASCADE')

def db_init(db_url):
    db_proxy.initialize(connect(db_url, thread_safe=True))
    if db_url.startswith('sqlite'):
        # since sqlite doesnt support fks by default
        db_proxy.pragma('foreign_keys', 1, permanent=True)
    db_proxy.create_tables([
        ModuleServer, Module, Command, OptionLookup, RequiredContext, RequiredPermission,
        User, Server, Channel, Message, ServerOption,
        Whitelist, Blacklist
    ])
    db_proxy.close()
    return db_proxy
