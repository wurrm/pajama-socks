from os import walk
from os.path import dirname

__all__ = []

for p,d,f in walk(dirname(__file__)):
    [__all__.append(m[:-3]) for m in f]
    break

del walk, dirname
del p,d,f
