# from https://raw.github.com/helgefmi/ansiterm/master/ansiterm.py

import logging
import re

DEFAULT = dict(fg=37, bg=40, reverse=False, bold=False)


class Error(Exception):
    pass


class EscapeError(Error):
    pass


class Tile(object):
    """Represents a single tile in the terminal"""
    def __init__(self):
        self.color = self.glyph = None
        self.reset()

    def reset(self):
        """Resets the tile to a white-on-black space"""
        self.glyph = ' '
        self.color = DEFAULT.copy()

    def set(self, glyph, color):
        self.glyph = glyph
        self.color.update(color)


class Ansiterm(object):
    _ESCAPE_PARSER = re.compile(br'^\x1b\[([\d;]*)([A-Za-z])')

    def __init__(self, rows, cols, strict=True):
        """Initializes the ansiterm with rows*cols white-on-black spaces"""
        self.rows = rows
        self.cols = cols
        self.strict = strict
        self.tiles = [Tile() for _ in range(rows * cols)]
        self.cursor = dict(x=0, y=0)
        self.color = dict(fg=37, bg=40, reverse=False, bold=False)

    def get_string(self, from_, to):
        """Returns the character of a section of the screen"""
        return ''.join([tile.glyph for tile in self.get_tiles(from_, to)])

    def get_tiles(self, from_, to):
        """Returns the tileset of a section of the screen"""
        return [tile for tile in self.tiles[from_:to]]

    def get_cursor(self):
        """Returns the current position of the curser"""
        return self.cursor.copy()

    def _parse_sgr(self, param):
        """Handles <escape code>n[;k]m, which changes the graphic rendition"""
        if param == 0:
            self.color.update(DEFAULT)
        elif param == 1:
            self.color['bold'] = True
        elif param == 7:
            self.color['reverse'] = True
        elif 30 <= param <= 37:
            self.color['fg'] = param
        elif 40 <= param <= 47:
            self.color['bg'] = param

    def _fix_cursor(self):
        """
        Makes sure the cursor are within the boundaries of the current terminal
        size.
        """
        while self.cursor['x'] >= self.cols:
            self.cursor['y'] += 1
            self.cursor['x'] = self.cursor['x'] - self.cols

        if self.cursor['y'] >= self.rows:
            self.cursor['y'] = self.rows - 1

    def _parse_sequence(self, input):
        """
        This method parses the input into the numeric arguments and
        the type of sequence. If no numeric arguments are supplied,
        we manually insert a 0 or a 1 depending on the sequence type,
        because different types have different default values.

        Example 1: \x1b[1;37;40m -> numbers=[1, 37, 40] char=m
        Example 2: \x1b[m = numbers=[0] char=m
        """
        if input.startswith(b'\x1bM'):
            return None, input[2:]

        if input.startswith(b'\x1b[?'):
            return None, input.split(b'h', 1)[1]

        if input.startswith(b'\x1b(B') or input.startswith(b'\x1b)0'):
            return None, input[3:]

        match = Ansiterm._ESCAPE_PARSER.match(input)
        if not match:
            if self.strict:
                raise Exception('Invalid escape sequence, input[:20]=%r' % input[:20])
            return None, input[1:]

        args, char = match.groups()
        args = args.decode('utf-8')
        char = char.decode('utf-8')
        # If arguments are omitted, add the default argument for this sequence.
        if not args:
            if char in 'ABCDEFSTf':
                numbers = [1]
            elif char == 'H':
                numbers = [1, 1]
            else:
                numbers = [0]
        else:
            numbers = list(map(int, args.split(';')))

        return (char, numbers), input[match.end():]

    def get_cursor_idx(self):
        return self.cursor['y'] * self.cols + self.cursor['x']

    def _evaluate_sequence(self, char, numbers):
        """
        Evaluates a sequence (i.e., this changes the state of the terminal).
        Is meant to be called with the return values from _parse_sequence as arguments.
        """
        # Translate the cursor into an index into our 1-dimensional tileset.
        curidx = self.get_cursor_idx()

        # Sets cursor position
        if char == 'H':
            self.cursor['y'] = numbers[0] - 1  # 1-based indexes
            self.cursor['x'] = numbers[1] - 1  #
        # Sets color/boldness
        elif char.lower() == 'm':
            for num in numbers:
                self._parse_sgr(num)
        # Clears (parts of) the screen.
        elif char == 'J':
            # From cursor to end of screen
            if numbers[0] == 0:
                range_ = (curidx, self.cols - self.cursor['x'] - 1)
            # From beginning to cursor
            elif numbers[0] == 1:
                range_ = (0, curidx)
            # The whole screen
            elif numbers[0] == 2:
                range_ = (0, self.cols * self.rows - 1)
            else:
                raise EscapeError('Unknown argument for J parameter: '
                                  '%s (input=%r)' % (numbers, input[:20]))
            for i in range(*range_):
                self.tiles[i].reset()
        # Clears (parts of) the line
        elif char == 'K':
            # From cursor to end of line
            if numbers[0] == 0:
                range_ = (curidx, curidx + self.cols - self.cursor['x'] - 1)
            # From beginning of line to cursor
            elif numbers[0] == 1:
                range_ = (curidx % self.cols, curidx)
            # The whole line
            elif numbers[0] == 2:
                range_ = (curidx % self.cols, curidx % self.cols + self.cols)
            else:
                raise EscapeError('Unknown argument for K parameter: '
                                  '%s (input=%r)' % (numbers, input[:20]))
            for i in range(*range_):
                self.tiles[i].reset()
        # Move cursor up
        elif char == 'A':
            self.cursor['y'] -= numbers[0]
        # Move cursor down
        elif char == 'B':
            self.cursor['y'] += numbers[0]
        # Move cursor right
        elif char == 'C':
            self.cursor['x'] += numbers[0]
        # Move cursor left
        elif char == 'D':
            self.cursor['x'] -= numbers[0]
        elif char == 'r' or char == 'l':  # TODO
            pass
        else:
            raise EscapeError('unknown escape code: char=%r numbers=%r', char, numbers)

    def feed(self, input):
        """Feeds the terminal with input."""
        while input:
            # If the input starts with \x1b, try to parse and evaluate an escape
            # sequence.
            if input.startswith(b'\x1b'):
                parsed, input = self._parse_sequence(input)
                if parsed:
                    self._evaluate_sequence(*parsed)
                    continue
            # If we end up here, the character should should just be
            # added to the current tile and the cursor should be updated.
            # Some characters such as \r, \n will only affect the cursor.
            # TODO: Find out exactly what should be accepted here.
            #       Only ASCII-7 perhaps?
            a = input[:1]
            if a == b'\r':
                self.cursor['x'] = 0
            elif a == b'\b':
                self.cursor['x'] -= 1
            elif a == b'\n':
                self.cursor['y'] += 1
            elif a == b'\x0f' or a == b'\x00':
                pass
            else:
                self.tiles[self.get_cursor_idx()].set(a.decode('utf-8'), self.color)
                self.cursor['x'] += 1
            input = input[1:]
        self._fix_cursor()
