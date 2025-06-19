import contextlib
import os
import sys

@contextlib.contextmanager
def silence(toggled:bool=True):
    if toggled:
        with open(os.devnull, 'w') as devnull:
            old_stdout = sys.stdout
            sys.stdout = devnull
            try:
                yield
            finally:
                sys.stdout = old_stdout
    else:
        yield