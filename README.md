# py-nethack

A pseudo-terminal wrapper over the best game of all time. Use it to record
games, or to play around with coding game control strategies.

## Installation

With pip

    pip install lmj.nethack

Or by downloading

    git clone http://github.com/lmjohns3/py-nethack
    cd py-nethack
    python setup.py install

## A note about `ansiterm.py`

This wrapper wouldn't be possible without the rad `ansiterm.py` module, which I
got from https://github.com/helgefmi/ansiterm and is distributed under the terms
of the MIT license. I did not write `ansiterm.py`, but it is included directly
in `./lmj/ansiterm.py` to make the `./lmj/nethack.py` module work smoothly.
