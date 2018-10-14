import asyncio

from modules.utils.moduletools import BaseModule, command, requires, checks

class ExampleModule(BaseModule):
    options = {'example_option': 'example_default'}

    @command
    def my_function(self, *args, **ctx):
        """Synchronously returns given arguments, seperated by commas."""
        r = 'All the parameters given: {}'.format(', '.join(args))
        return ['send_message', ctx['channel.id'], r]

    @command
    async def my_coroutine(self, *args, **ctx):
        """Asynchronously returns given arguments, seperated by commas."""
        r = 'All the parameters given, asynchronously: {}'.format(', '.join(args))
        return ['send_message', ctx['channel.id'], r]

    @command
    async def my_option(self, *args, **ctx):
        """Returns the server's example_option."""
        option = ctx['server_options'].example_option
        r = 'Server\'s option is {}'.format(option)
        return ['send_message', ctx['channel.id'], r]
    
    @command
    @requires('server.name', 'author.name')
    async def my_ctx(self, *args, **ctx):
        """Returns the server's and author's names."""
        serv = ctx['server.name']
        user = ctx['author.name']
        return ['send_message', ctx['channel.id'], 'Server: {}, Author: {}'.format(serv, user)]
    
    @command
    @checks('manage_messages')
    async def delete_me(self, *args, **ctx):
        return ['delete_message', ctx['message.id']]
