### This bot wears pajamas.

If SQLite was its cream yellow top and peewee were the little light grey spots,
Python's runtime and dynamic environment would be its slightly-too-short bottoms.
First class and higher order functions would be the fuzzy bunny slippers that keep its feet warm,
and it would have a piping hot mug of freshly brewed websockets with an OOP biscuit before bed.

In a shocking twist however, its pajamas were sown together in around 3 weeks by an underpaid 17 year old who decided to keep the previous set of pajamas in just a single wardrobe, which of course spontaneously combusted.

There is a lot wrong with this program. It's hacky and temperamental, and just kind of almost works most of the time I think.

__However,__ it demonstrates an understanding of and/or has taught me about:
- asynchronicity
- decorators and wrappers
- the runtime in general
- creating APIs
- client-server design
- multithreading
- scalability
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

This is a highly extendable Discord bot, which aims to be distributable while being easy to develop. It achieves this by splitting the function of the bot into portions and allowing them to speak to each other through websockets. 

In particular, these pieces are: 
a database containing information on all portions of the bot and the user space, 
a thin client for preprocessing user input and offloading to thick workers, 
and "modules", which are managed among any number of servers as required.

New modules are created simply by creating a new class inheriting the `BaseModule` class and decorating functions with wrappers, creating and loading information into the database at runtime without any extra effort on the side of the developer ([example](https://github.com/wurrm/pajama-socks/blob/master/modules/example_module.py)).

The flow of data during normal operation is something like: Discord (user posts) -> thin client (parses post) -> database (retrieves information on command) -> thin client (requests any needed context from Discord API) -> module server (identifies module) -> module queue (processes command) {-> database (if needed, change records)} -> thin client -> Discord
