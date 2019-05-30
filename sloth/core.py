#!/usr/bin/python3

import os
import re
import string
import tokenize
from io import FileIO, StringIO
from pathlib import Path
from copy import deepcopy
from collections import deque

from . import CONFIG
from .errors import VmRuntimeError
from .primitives import PRIMITIVES


TABSTOP = 8
NUMLIT_RE = re.compile('(-)?'+tokenize.Number)


class Stack(deque):
    push = deque.append
    pushleft = deque.appendleft

    def __repr__(self):
        elem = ' '.join([str(x) for x in self])
        return f'[{elem}]'

    @property
    def top(self):
        return self[-1]

    @top.setter
    def top(self, v):
        self[-1] = v

    def unary_op(self, func):
        try:
            self.top = func(self.top)
        except IndexError:
            raise VmRuntimeError('Stack underflow')

    def binary_op(self, func):
        try:
            v1 = self.pop()
            v2 = self.pop()
            self.push(func(v2, v1))
        except IndexError:
            raise VmRuntimeError('Stack underflow')


class CharStream:
    """
    A stream that provides iteration over whitespace separated words, as well
    as invdividual characters.
    """
    def __init__(self, stream):
        if isinstance(stream, str):
            self.stream = StringIO(stream)
        else:
            self.stream = stream
        self.last_word_start = None

    def __iter__(self):
        return self

    def __next__(self):
        while True:
            # Skip initial whitespace before the word
            c = self.next_char()
            if c not in string.whitespace:
                self.last_word_start = self.stream.tell()
                break
        chars = [c]
        while True:
            # Return if the stream ends with the word end
            try:
                c = self.next_char()
            except StopIteration:
                break
            # Accumulate until a whitespace character
            if c in string.whitespace:
                break
            else:
                chars.append(c)
        return ''.join(chars)

    def next_char(self):
        char = self.stream.read(1)
        if char == '':
            raise StopIteration
        return char

    def write(self, text):
        pos = self.stream.tell()
        self.stream.write('\n')
        self.stream.write(text)
        self.stream.seek(pos)


def convert_numeric_literal(name):
    if NUMLIT_RE.fullmatch(name):
        return eval(name)
    else:
        raise ValueError('Invalid numeric literal')


def is_numeric_literal(name):
    return bool(NUMLIT_RE.fullmatch(name))


class VirtualMachine:
    WARN = True

    def __init__(self, stream):
        self.stream = CharStream(stream)
        self.ip = 0
        self.stack = Stack()
        self.return_stack = Stack()
        self.frame_stack = Stack()
        self.dictionary = PRIMITIVES.copy()
        self.heap = {}
        self.last_word = None
        self.immediate = True
        self.backup = deepcopy(self)

    def make_backup(self):
        self.backup = deepcopy(self)

    def revert(self):
        self = deepcopy(self.backup)

    def enter(self):
        self.return_stack.push(self.ip)
        self.ip = 0

    def exit(self):
        self.ip = self.return_stack.pop()

    def insert_word(self, word):
        self.dictionary[word.symbol] = word
        self.last_word = word

    def next_compiled_instr(self):
        try:
            word = self.frame_stack.top
            op = word.code[self.ip+1]
            return op
        except IndexError:
            raise VmRuntimeError('End of word code on "next"')

    def next_symbol(self):
        try:
            return next(self.stream)
        except StopIteration:
            raise VmRuntimeError('End of stream')

    def parse_symbol(self, symb):
        if is_numeric_literal(symb):
            return convert_numeric_literal(symb)
        elif symb in self.dictionary:
            return self.dictionary[symb]
        else:
            raise VmRuntimeError(f'Undefined symbol: "{symb}"')

    def handle_op(self, word):
        if callable(word):
            word(self)
        else:
            self.stack.push(word)

    def compile(self, word):
        self.ip += 1
        self.last_word.code.append(word)

    def run(self):
        for symb in self.stream:
            word = self.parse_symbol(symb)
            if self.immediate:
                self.handle_op(word)
            elif hasattr(word, 'immediate') and word.immediate:
                self.handle_op(word)
            else:
                self.compile(word)

    def read_input(self, text):
        self.make_backup()
        self.stream.write(text)

    def import_module(self, modname):
        modname += '.sloth'
        system_path = (
            Path(os.getcwd()),
            Path(CONFIG.get('Paths', 'sloth_dir')).expanduser()
                / Path(CONFIG.get('Paths', 'lib_dir')),
            Path(__file__).parent.parent / Path('lib'),
        )
        for path in system_path:
            mod_path = path / Path(modname)
            if mod_path.exists():
                break
        else:
            raise VmRuntimeError(f'Could not find module: "{modname}"')
        with open(mod_path) as f:
            text = f.read()
        mod_vm = VirtualMachine(text)
        mod_vm.run()
        public_words = {
            k: v for k, v in mod_vm.dictionary.items()
            if hasattr(v, 'hidden') and not v.hidden
        }
        self.dictionary.update(public_words)


def compute(input_str):
    vm = VirtualMachine(input_str)
    vm.run()
    print( 'data: {0}'.format(vm.stack))
    print( 'retn: {0}'.format(vm.return_stack))
    print(f'  ip: {vm.ip}')


