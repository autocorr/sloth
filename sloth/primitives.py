#!/usr/bin/env python3

import sys
import operator
import textwrap
from functools import wraps
from collections import deque

from termcolor import colored

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
            except (IndexError, WordExit):
                break
            vm.handle_op(op)
            vm.ip += 1
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


@RegisterBuiltin('max')
def max_(vm):
    vm.stack.binary_op(max)


@RegisterBuiltin('min')
def min_(vm):
    vm.stack.binary_op(min)


@RegisterBuiltin('abs')
def abs_(vm):
    vm.stack.unary_op(abs)


##############################################################################
#                           Comparison and Logical
##############################################################################

@RegisterBuiltin('True')
def true(vm):
    vm.stack.push(True)


@RegisterBuiltin('False')
def false(vm):
    vm.stack.push(False)


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


@RegisterBuiltin('0=')
def zero_eq(vm):
    vm.stack.push(vm.stack.top == 0)


@RegisterBuiltin('0<>')
def zero_ne(vm):
    vm.stack.push(vm.stack.top != 0)


@RegisterBuiltin('0<')
def zero_lt(vm):
    vm.stack.push(vm.stack.top < 0)


@RegisterBuiltin('0>')
def zero_gt(vm):
    vm.stack.push(vm.stack.top > 0)


@RegisterBuiltin('1=')
def one_eq(vm):
    vm.stack.push(vm.stack.top == 1)


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


@RegisterBuiltin('2over')
def two_over(vm):
    vm.stack.push(vm.stack[-4])
    vm.stack.push(vm.stack[-4])


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
def clearstack(vm):
    vm.stack.clear()


@RegisterBuiltin()
def clearstacks(vm):
    vm.stack.clear()
    vm.return_stack.clear()


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


@RegisterBuiltin('rp@')
def rpointer(vm):
    vm.stack.push(len(vm.return_stack))


@RegisterBuiltin('r+')
def rplus(vm):
    vm.return_stack.top += 1


@RegisterBuiltin('r-')
def rplus(vm):
    vm.return_stack.top -= 1


@RegisterBuiltin('i')
def eye(vm):
    vm.stack.push(vm.return_stack.top)


@RegisterBuiltin()
def here(vm):
    try:
        adr = len(vm.last_word.code)
        vm.stack.push(adr)
    except AttributeError:
        raise VmRuntimeError('Error in "here": no previously compiled word')


@RegisterBuiltin()
def exit(vm):
    if len(vm.return_stack) == 0:
        raise VmRuntimeError('Error in "exit": cannot exit outside of a definition')
    else:
        raise WordExit


@RegisterBuiltin('.r')
def print_rstack(vm):
    print(vm.return_stack)


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
    symb = vm.next_symbol()
    vm.stack.push(symb)


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


@RegisterBuiltin('w!')
def word_bang(vm):
    adr = vm.stack.pop()
    v = vm.stack.pop()
    try:
        vm.last_word.code[adr] = v
    except IndexError:
        raise VmRuntimeError(f'Address "{adr}" out of bounds')


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


@RegisterBuiltin('w@')
def word_at(vm):
    adr = vm.stack.pop()
    try:
        v = vm.last_word.code[adr]
        vm.stack.push(v)
    except IndexError:
        raise VmRuntimeError(f'Address "{adr}" out of bounds')


@RegisterBuiltin('.m')
def dotm(vm):
    for k, v in vm.heap.items():
        print(f'{k} -> {v}')


##############################################################################
#                             Parsing Words
##############################################################################

@RegisterBuiltin(immediate=True)
def immediate(vm):
    vm.last_word.immediate = True


@RegisterBuiltin('immediate?')
def immediateq(vm):
    word = vm.stack.pop()
    try:
        vm.stack.push(word.immediate)
    except AttributeError:
        raise VmRuntimeError(f'Immediate flag not defined for "{word}"')


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


@RegisterBuiltin("[']")
def compiled_tick(vm):
    word = vm.next_compiled_instr()
    vm.stack.push(word)
    vm.ip += 1


@RegisterBuiltin("'")
def interp_tick(vm):
    symb = vm.next_symbol()
    word = vm.parse_symbol(symb)
    vm.stack.push(word)


@RegisterBuiltin('does>')
def does(vm):
    word = vm.frame_stack.top
    ops = word.code[vm.ip+1:]
    vm.last_word.code.extend(ops)
    raise WordExit


@RegisterBuiltin(',')
def comma(vm):
    word = vm.stack.pop()
    vm.last_word.code.append(word)


@RegisterBuiltin()
def lastword(vm):
    vm.stack.push(vm.last_word)


@RegisterBuiltin()
def create(vm):
    symb = vm.next_symbol()
    if symb in vm.dictionary and vm.WARN:
        red_warn = colored('Warning:', 'red')
        print(red_warn, f'redefining "{symb}" in dictionary')
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


@RegisterBuiltin('import', immediate=True)
def import_module(vm):
    symb = vm.next_symbol()
    vm.import_module(symb)


##############################################################################
#                          Virtual Machine State
##############################################################################

@RegisterBuiltin('toggle-warnings')
def toggle_warnings(vm):
    vm.WARN = not vm.WARN
    state = 'on' if vm.WARN else 'off'
    print(f'Warnings turned {state}')


##############################################################################
#                              Interpreter
##############################################################################

@RegisterBuiltin()
def bye(vm):
    sys.exit(0)


@RegisterBuiltin()
def pdb(vm):
    import ipdb
    ipdb.set_trace()


@RegisterBuiltin()
def decompile(vm):
    xt = vm.stack.pop()
    print(xt.code)


