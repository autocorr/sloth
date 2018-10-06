#!/usr/bin/env python3

import sys
import operator
import textwrap
from functools import wraps
from collections import deque

from .errors import VmRuntimeError, WordExit


PRIMITIVES = {}


class Word:
    def __repr__(self):
        return f'w:{self.symbol}'


class BuiltinWord(Word):
    def __init__(self, func, symbol=None, immediate=False, stack_effect=None):
        self.func = func
        self.__doc__ = func.__doc__
        self.symbol = func.__name__ if symbol is None else symbol
        self.stack_effect = stack_effect
        self.immediate = immediate

    def __call__(self, vm):
        self.func(vm)


class DefinedWord(Word):
    def __init__(self, symbol):
        self.symbol = symbol
        self.immediate = False
        self.code = []
        self.definition_text = None
        self.stack_effect = None
        self.hidden = False
        self.text_location = None

    def __call__(self, vm):
        vm.frame_stack.push(self)
        vm.enter()
        while True:
            try:
                op = self.code[vm.ip]
                vm.handle_op(op)
                vm.ip += 1
            except (IndexError, WordExit):
                break
        vm.exit()
        vm.frame_stack.pop()


class RegisterBuiltin:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __call__(self, func):
        word = BuiltinWord(func, *self.args, **self.kwargs)
        PRIMITIVES[word.symbol] = word
        return func


# TODO
# user defined words
# - string for definition, all characters between : and ; for `see`


##############################################################################
#                               Arithmetic
##############################################################################

@RegisterBuiltin(stack_effect='( n -- -n )')
def neg(vm):
    """Negate a number."""
    vm.stack.unary_op(operator.neg)


@RegisterBuiltin('+')
def add(vm):
    vm.stack.binary_op(operator.add)


@RegisterBuiltin('-')
def sub(vm):
    vm.stack.binary_op(operator.sub)


@RegisterBuiltin('*')
def mul(vm):
    vm.stack.binary_op(operator.mul)


@RegisterBuiltin('/')
def div(vm):
    vm.stack.binary_op(operator.truediv)


@RegisterBuiltin('//')
def fdiv(vm):
    vm.stack.binary_op(operator.floordiv)


@RegisterBuiltin('mod')
def mod(vm):
    vm.stack.binary_op(operator.mod)


@RegisterBuiltin('**')
def pow(vm):
    vm.stack.binary_op(operator.pow)


@RegisterBuiltin('1+')
def oneplus(vm):
    vm.stack.top += 1


@RegisterBuiltin('1-')
def oneminus(vm):
    vm.stack.top -= 1


##############################################################################
#                           Comparison and Logical
##############################################################################

@RegisterBuiltin('=')
def eq(vm):
    vm.stack.binary_op(operator.eq)


@RegisterBuiltin('<>')
def ne(vm):
    vm.stack.binary_op(operator.ne)


@RegisterBuiltin('>')
def gt(vm):
    vm.stack.binary_op(operator.gt)


@RegisterBuiltin('<')
def lt(vm):
    vm.stack.binary_op(operator.lt)


@RegisterBuiltin('>=')
def ge(vm):
    vm.stack.binary_op(operator.ge)


@RegisterBuiltin('<=')
def le(vm):
    vm.stack.binary_op(operator.le)


@RegisterBuiltin('not')
def logical_not(vm):
    vm.stack.top = not vm.stack.top


@RegisterBuiltin('and')
def logical_and(vm):
    v1 = vm.stack.pop()
    v2 = vm.stack.pop()
    vm.stack.push(v2 and v1)


@RegisterBuiltin('or')
def logical_or(vm):
    v1 = vm.stack.pop()
    v2 = vm.stack.pop()
    vm.stack.push(v2 or v1)


##############################################################################
#                              Stack Shufflers
##############################################################################

@RegisterBuiltin()
def drop(vm):
    vm.stack.pop()


@RegisterBuiltin()
def swap(vm):
    ds = vm.stack
    ds[-2], ds[-1] = ds[-1], ds[-2]


@RegisterBuiltin()
def dup(vm):
    vm.stack.push(vm.stack.top)


@RegisterBuiltin()
def over(vm):
    vm.stack.push(vm.stack[-2])


@RegisterBuiltin()
def rot(vm):
    ds = vm.stack
    ds[-3], ds[-2], ds[-1] = ds[-2], ds[-1], ds[-3]


@RegisterBuiltin('-rot')
def mrot(vm):
    ds = vm.stack
    ds[-3], ds[-2], ds[-1] = ds[-1], ds[-3], ds[-2]


@RegisterBuiltin('2swap')
def twoswap(vm):
    ds = vm.stack
    ds[-4], ds[-3], ds[-2], ds[-1] = ds[-2], ds[-1], ds[-4], ds[-3]


@RegisterBuiltin('?dup')
def qdup(vm):
    if vm.stack.top:
        dup(vm)


@RegisterBuiltin()
def depth(vm):
    vm.stack.push(len(vm.stack))


@RegisterBuiltin()
def pick(vm):
    index = -vm.stack.pop() - 1
    vm.stack.push(vm.stack[index])


@RegisterBuiltin()
def clear(vm):
    vm.stack.clear()


##############################################################################
#                              Return Stack
##############################################################################

@RegisterBuiltin('>r')
def rpush(vm):
    vm.return_stack.push(vm.stack.pop())


@RegisterBuiltin('r>')
def rpop(vm):
    vm.stack.push(vm.return_stack.pop())


@RegisterBuiltin()
def rdrop(vm):
    vm.return_stack.pop()


@RegisterBuiltin('>here')
def herepush(vm):
    vm.ip = vm.stack.pop()


@RegisterBuiltin('here>')
def herepop(vm):
    vm.stack.push(vm.ip)


@RegisterBuiltin()
def exit(vm):
    if len(vm.return_stack) == 0:
        raise VmRuntimeError('Error in "exit": cannot exit outside of a definition')
    else:
        raise WordExit


##############################################################################
#                              Input / Output
##############################################################################

# TODO
# stdin
# stdout
# files

@RegisterBuiltin()
def emit(vm):
    print(chr(vm.stack.pop()))


@RegisterBuiltin()
def key(vm):
    s = vm.stream.next_char()
    vm.stack.push(ord(s))


@RegisterBuiltin()
def word(vm):
    try:
        name = next(vm.stream)
        vm.stack.push(name)
    except StopIteration:
        raise VmRuntimeError('Error in "word": cannot read word, end of stream')


##############################################################################
#                       Comments and Documentation
##############################################################################

def accum_until(vm, sentinel):
    length = len(sentinel)
    stop_buff = deque(sentinel)
    word_buff = deque([None]) * len(sentinel)
    accum = deque()
    while True:
        try:
            char = vm.stream.next_char()
            word_buff.popleft()
            word_buff.append(char)
            if word_buff == stop_buff:
                break
            else:
                accum.append(char)
        except StopIteration:
            break
    for _ in range(length-1):
        accum.pop()
    return ''.join(accum)


@RegisterBuiltin('\\', immediate=True)
def line_comment(vm):
    accum_until(vm, '\n')


@RegisterBuiltin('(', immediate=True)
def paired_comment(vm):
    text = accum_until(vm, ')')
    try:
        if not vm.last_word.code and vm.last_word.stack_effect is None:
            pretty = '( {0} )'.format(text.strip())
            vm.last_word.stack_effect = pretty
    except AttributeError:
        pass


@RegisterBuiltin('("', immediate=True)
def doc_comment(vm):
    text = accum_until(vm, '")')
    pretty = textwrap.indent(textwrap.dedent(text), " "*2)
    if vm.last_word is not None and vm.return_stack:
        vm.last_word.__doc__ = pretty
    else:
        raise VmRuntimeError('Invalid doc-comment: outside of definition.')


@RegisterBuiltin(immediate=True)
def help(vm):
    symb = vm.next_symbol()
    word = vm.dictionary[symb]
    print(word.stack_effect)
    print(word.__doc__)


@RegisterBuiltin()
def words(vm):
    print(' '.join(vm.dictionary.keys()))


##############################################################################
#                               Variables
##############################################################################

@RegisterBuiltin('!')
def bang(vm):
    adr = vm.stack.pop()
    v = vm.stack.pop()
    vm.heap[adr] = v


@RegisterBuiltin('+!')
def plus_bang(vm):
    adr = vm.stack.pop()
    v = vm.stack.pop()
    try:
        vm.heap[adr] += v
    except KeyError:
        vm.heap[adr] = v


@RegisterBuiltin('-!')
def minus_bang(vm):
    adr = vm.stack.pop()
    v = vm.stack.pop()
    try:
        vm.heap[adr] -= v
    except KeyError:
        vm.heap[adr] = v


@RegisterBuiltin('@')
def at(vm):
    adr = vm.stack.pop()
    try:
        v = vm.heap[adr]
        vm.stack.push(v)
    except KeyError:
        raise VmRuntimeError(f'Address "{adr}" uninitialized')


@RegisterBuiltin('.m')
def dotm(vm):
    for k, v in vm.heap.items():
        print(f'{k} -> {v}')


##############################################################################
#                                Other
##############################################################################

# TODO
# lit

@RegisterBuiltin(immediate=True)
def immediate(vm):
    vm.last_word.immediate = True


@RegisterBuiltin()
def branch(vm):
    offset = vm.next_compiled_instr()
    vm.ip += offset + 1


@RegisterBuiltin('0branch')
def zbranch(vm):
    if not vm.stack.pop():
        branch(vm)
    else:
        vm.ip += 1


@RegisterBuiltin('[', immediate=True)
def lbrac(vm):
    vm.immediate = True


@RegisterBuiltin(']')
def rbrac(vm):
    vm.immediate = False


@RegisterBuiltin('interpret?')
def interpretq(vm):
    vm.stack.push(vm.immediate)


@RegisterBuiltin("'")
def tick(vm):
    symb = vm.next_symbol()
    try:
        word = vm.dictionary[symb]
        vm.stack.push(word)
    except KeyError:
        raise VmRuntimeError(f'Undefined symbol: "{symb}"')


@RegisterBuiltin(',')
def comma(vm):
    word = vm.stack.pop()
    vm.last_word.code.push(word)


@RegisterBuiltin()
def create(vm):
    symb = vm.next_symbol()
    word = DefinedWord(symb)
    vm.insert_word(word)


@RegisterBuiltin(':')
def colon(vm):
    create(vm)
    vm.last_word.text_location = vm.stream.last_word_start
    vm.enter()
    vm.immediate = False


@RegisterBuiltin(';', immediate=True)
def semicolon(vm):
    vm.exit()
    vm.immediate = True


@RegisterBuiltin(immediate=True)
def hidden(vm):
    vm.last_word.hidden = True


@RegisterBuiltin()
def bye(vm):
    sys.exit(0)


