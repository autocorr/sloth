#!/usr/bin/env python3

from os import path
from setuptools import setup


here = path.abspath(path.dirname(__file__))
with open(path.join(here, 'README.rst'), 'r') as f:
    long_description = f.read()


setup(
    name='Sloth',
    version='0.1',
    description='Sloth programming language',
    long_description=long_description,
    author='Brian Svoboda',
    license='GPLv3',
    url='https://github.com/autocorr/sloth',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Software Development :: Interpreters',
    ],
    keywords='concatentive',
    packages=['sloth'],
    install_requires=[
        'termcolor',
        'pygments',
        'prompt_toolkit',
    ],
    python_requires='>=3',
    extras_require={
        'test': ['pytest'],
    },
    data_files=[
        ('lib', ['lib/std.sloth', 'lib/examples.sloth']),
    ],
)
