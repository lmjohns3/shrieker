#!/usr/bin/env python

import collections
import logging
import numpy
import os
import pty
import random
import re
import select
import sys
import tempfile

import ansiterm


class CMD:
    class DIR:
        NW = 'y'
        N = 'k'
        NE = 'u'
        E = 'l'
        SE = 'n'
        S = 'j'
        SW = 'b'
        W = 'h'

        UP = '<'
        DOWN = '>'

    PICKUP = ','
    WAIT = '.'
    MORE = '\x0d' # ENTER

    APPLY = 'a'
    CLOSE = 'c'
    DROP = 'd'
    EAT = 'e'
    ENGRAVE = 'E'
    FIRE = 'f'
    INVENTORY = 'i'
    OPEN = 'o'
    PAY = 'p'
    PUTON = 'P'
    QUAFF = 'q'
    QUIVER = 'Q'
    READ = 'r'
    REMOVE = 'R'
    SEARCH = 's'
    THROW = 't'
    TAKEOFF = 'T'
    WIELD = 'w'
    WEAR = 'W'
    EXCHANGE = 'x'
    ZAP = 'z'
    CAST = 'Z'

    KICK = '\x03' # ^D
    TELEPORT = '\x14' # ^T

    class SPECIAL:
        CHAT = '#chat'
        DIP = '#dip'
        FORCE = '#force'
        INVOKE = '#invoke'
        JUMP = '#jump'
        LOOT = '#loot'
        MONSTER = '#monster'
        OFFER = '#offer'
        PRAY = '#pray'
        RIDE = '#ride'
        RUB = '#rub'
        SIT = '#sit'
        TURN = '#turn'
        WIPE = '#wipe'


class InventoryItem:
    CATEGORIES = (
        'Amulets', 'Weapons', 'Armor',
        'Comestibles', 'Scrolls', 'Spellbooks',
        'Potions', 'Rings', 'Wands', 'Tools')

    def __init__(self, raw):
        self.raw = raw.strip()

    def __str__(self):
        return self.raw

    def __repr__(self):
        return '<%s: %s>' % (self.__class__.__name__, self)

    @property
    def is_cursed(self):
        return ' cursed ' in self.raw

    @property
    def is_uncursed(self):
        return ' uncursed ' in self.raw

    @property
    def is_blessed(self):
        return ' blessed ' in self.raw

    @property
    def is_being_worn(self):
        return '(being worn)' in self.raw

    @property
    def is_in_use(self):
        return '(in use)' in self.raw

    @property
    def duplicates(self):
        m = re.match(r'^(\d+)', self.raw)
        if not m:
            return 1
        return int(m.group(1))

    @property
    def charges(self):
        m = re.match(r' \((\d+):(\d+)\)$', self.raw)
        if not m:
            return None
        return int(m.group(1)), int(m.group(2))

    @property
    def enchantment(self):
        m = re.match(r' ([-+]\d+) ', self.raw)
        if not m:
            return None
        return int(m.group(1))

    @property
    def named(self):
        m = re.match(r' named ([^\(]+)', self.raw)
        if not m:
            return None
        return m.group(1)

class AmuletsItem(InventoryItem): pass
class ArmorItem(InventoryItem): pass

class WeaponsItem(InventoryItem):
    @property
    def is_wielded(self):
        return '(weapon in hand)' in self.raw

    @property
    def is_alternate(self):
        return '(alternate weapon; not wielded)' in self.raw

    @property
    def is_quivered(self):
        return '(in quiver)' in self.raw

class ComestiblesItem(InventoryItem): pass
class ScrollsItem(InventoryItem): pass
class SpellbooksItem(InventoryItem): pass
class PotionsItem(InventoryItem): pass
class RingsItem(InventoryItem): pass
class WandsItem(InventoryItem): pass
class ToolsItem(InventoryItem): pass


class NethackBot:
    OPTIONS = 'CHARACTER=%(character)s\nOPTIONS=hilite_pet,pickup_types:$?+!=/,gender:%(gender)s,race:%(race)s'

    def play(self, **kwargs):
        shape = (25, 80)
        self.glyphs = numpy.zeros(shape, int)
        self.reverse = numpy.zeros(shape, bool)
        self.bold = numpy.zeros(shape, bool)
        self._raw = ''
        self._term = ansiterm.Ansiterm(*shape)

        self.command = None

        self._need_inventory = True
        self._more_inventory = False

        self.messages = collections.deque(maxlen=1000)

        self.stats = {}
        self.inventory = {}
        self.spells = {}

        opts = dict(character='ran', gender=random.choice(['mal', 'fem']), race='elf')
        opts.update(kwargs)

        handle = tempfile.NamedTemporaryFile()
        handle.write(self.OPTIONS % opts)
        handle.flush()

        os.environ['NETHACKOPTIONS'] = '@' + handle.name

        pty.spawn(['nethack'], self._observe, self._act)

    def choose_action(self):
        raise NotImplementedError

    def choose_answer(self):
        raise NotImplementedError

    def neighborhood(self, n=3):
        rows, cols = self.glyphs.shape
        Y, X = self.cursor
        return self.glyphs[slice(max(0, Y - 5), min(Y + 5, rows - 3)),
                           slice(max(0, X - 5), min(X + 5, cols))]

    def _parse_inventory(self):
        found_inventory = False
        for category in InventoryItem.CATEGORIES:
            klass = eval('%sItem' % category)
            contents = self.inventory.setdefault(category, {})
            i = self._raw.find(category)
            if i > 0:
                s = self._raw[i:].split('\x1b[7m')[0]
                for letter, name in re.findall(' (\w) - (.*?)(?=\x1b\[)', s):
                    contents[letter] = klass(name)
                logging.error('inventory for %s: %s', category, contents)
                found_inventory = True
        self._need_inventory = not found_inventory

    def _parse_glyphs(self):
        Y, X = self.glyphs.shape

        self._term.feed(self._raw)

        for y in range(Y):
            tiles = self._term.get_tiles(X * y, X * (y + 1))
            logging.debug('terminal %02d: %s', y, ''.join(t.glyph for t in tiles))
            self.glyphs[y] = [ord(t.glyph) for t in tiles]
            self.bold[y] = [t.color['bold'] for t in tiles]
            self.reverse[y] = [t.color['reverse'] for t in tiles]

        self.cursor = (self._term.cursor['y'], self._term.cursor['x'])

        logging.info('current map:\n%s', '\n'.join(''.join(chr(c) for c in r) for r in self.glyphs))
        logging.warn('current neighborhood:\n%s', '\n'.join(''.join(chr(c) for c in r)
                                                            for r in self.neighborhood(3)))

        # parse messages from the first line on the screen.
        l = ''.join(chr(c) for c in self.glyphs[0])
        if l.strip() and l[0].strip():
            logging.warn('message: %s', l)
            self.messages.append(l)

        # parse character attributes.
        l = ''.join(chr(c) for c in self.glyphs[22])
        m = re.search(r'St:(?P<st>\d+)\s*'
                      r'Dx:(?P<dx>\d+)\s*'
                      r'Co:(?P<co>\d+)\s*'
                      r'In:(?P<in>\d+)\s*'
                      r'Wi:(?P<wi>\d+)\s*'
                      r'Ch:(?P<ch>\d+)\s*'
                      r'(?P<align>\S+)', l)
        if m:
            self.attributes = m.groupdict()
            logging.warn('parsed attributes: %s', ', '.join('%s: %s' % (k, self.attributes[k]) for k in sorted(self.attributes)))

        # parse stats from the penultimate line.
        l = ''.join(chr(c) for c in self.glyphs[23])
        m = re.search(r'Dlvl:(?P<dlvl>\S+)\s*'
                      r'\$:(?P<money>\d+)\s*'
                      r'HP:(?P<hp>\d+)\((?P<hp_max>\d+)\)\s*'
                      r'Pw:(?P<pw>\d+)\((?P<pw_max>\d+)\)\s*'
                      r'AC:(?P<ac>\d+)\s*'
                      r'Exp:(?P<exp>\d+)\s*'
                      r'(?P<hunger>Hungry|Weak|Fainting)?\s*'
                      r'(?P<burden>Burdened|Stressed|Strained|Overtaxed|Overloaded)?\s*'
                      r'(?P<hallu>Hallu)?\s*'
                      r'(?P<conf>Conf)?\s*'
                      r'(?P<stun>Stun)?', l)
        if m:
            self.stats = m.groupdict()
            for k, v in self.stats.items():
                if v and v.isdigit():
                    self.stats[k] = int(v)
            logging.warn('parsed stats: %s', ', '.join('%s: %s' % (k, self.stats[k]) for k in sorted(self.stats)))

    def _observe(self, raw):
        self._raw = re.sub(r'\x1b\[\?\d+h', '', raw)
        if not self._raw:
            return

        logging.debug('observed %d world bytes:\n%s',
                      len(self._raw),
                      '\n'.join(repr(p) for p in self._raw.split('\x1b[')))

        self._parse_glyphs()

        if self.command is CMD.INVENTORY:
            if not self._more_inventory:
                self.inventory = {}
            self._parse_inventory()
            self._more_inventory = '--More--' in self._raw

        self.command = None

    def _act(self):
        msg = self.messages and self.messages[-1] or ''
        if '--More--' in self._raw or '(end)' in self._raw:
            self.command = CMD.MORE
        elif 'You die' in msg:
            self.command = 'q'
        elif '? ' in msg and ' written ' not in msg:
            self.command = self.choose_answer()
        elif self._need_inventory:
            self.command = CMD.INVENTORY
        else:
            self.command = self.choose_action()
        logging.warn('sending command "%s"', self.command)
        return self.command


class RandomBot(NethackBot):
    def choose_action(self):
        return random.choice([CMD.DIR.N, CMD.DIR.NE, CMD.DIR.E, CMD.DIR.SE,
                              CMD.DIR.S, CMD.DIR.SW, CMD.DIR.W, CMD.DIR.NW,
                              ])


# drain all available bytes from the given file descriptor, until a complete
# timeout goes by with no new data.
def _drain(fd, timeout=0.3):
    more, _, _ = select.select([fd], [], [], timeout)
    buf = ''
    while more:
        buf += os.read(fd, 1024)
        more, _, _ = select.select([fd], [], [], timeout)
    return buf

# we almost want to do what pty.spawn does, except that we know how our child
# process works. so, we forever loop: read world state from nethack, then issue
# an action to nethack. repeat.
def _copy(fd, observe, act):
    while True:
        buf = _drain(fd)
        if buf:
            observe(buf)
            os.write(1, buf)
        pty._writen(fd, act())

# monkeys ahoy !
pty._copy = _copy


if __name__ == '__main__':
    logging.basicConfig(
        stream=open('/tmp/nethack-bot.log', 'w'),
        level=logging.INFO,
        format='%(levelname).1s %(asctime)s %(message)s')
    bot = RandomBot()
    bot.play()
