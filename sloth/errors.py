#!/usr/bin/env python3


class SlothError(Exception):
    pass


class VmRuntimeError(SlothError):
    pass


class WordExit(SlothError):
    pass


