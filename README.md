### This bot wears pajamas.

If SQLite was its cream yellow top and peewee were the little light grey spots,
Python's runtime and dynamic environment would be its slightly-too-short bottoms.
First class and higher order functions would be the fuzzy bunny slippers that keep its feet warm,
and it would have a piping hot mug of freshley brewed websockets with an OOP biscuit before bed.

In a shocking twist however, its pajamas were sown together in around 3 weeks by an underpaid 17 year old who decided to keep the previous set of pajamas in just a single wardrobe, which of course spontaneously combusted.

There is a lot wrong with this program. It's hacky and temperamental, and just kind of almost works most of the time I think.

__However,__ it demonstrates an understanding of and/or has taught me about:
- asynchronicity
- decorators and wrappers
- the runtime in general
- creating APIs
- client-server design
- threading
- documentation and its need
- databases
- networking
- optimisation and efficiency in general
- abstract data types
- functional programming
- OOP and factories

Even though there's a lot to improve here (I don't intend to though), I'm fairly proud of it so I thought I'd share my first big project.

Prospective employers, please believe I'm much wiser than some of this program would leave one to think.

Please.

I'm begging you.

### But what does it actually do?

This is a highly extenable Discord bot, which aims to be distributable while being easy to develop. It achieve this by splitting the function of the bot into portions and allowing them to speak to each other through websockets. Said pieces are: a database containing information on all portions of the bot and the user space, a thin client for user input and pushing to worker queues, and "modules", which are managed by any number of servers as required. New modules are created simply by inheriting the `BaseModule` class, with which a number of given wrappers can be used to decorate functions that provide an interface for interacting with both the Discord API and the database, creating and loading information into the database without any effort on the side of the developer ([example](https://github.com/wurrm/pajama-socks/blob/master/modules/example_module.py)).

This is possible because any given Discord user can only interact with the bot through text -- and text can be stored in a database. The thin client only needs to know what the module and any requirements the function the user asks for has (which again, we can store in our SQL server) in order to get and send all the data needed to the necessary module server for processing.
