#!/usr/bin/env python

from distutils.core import setup

setup(
    name='pype',
    version='1.0',
    description='Object-oriented model for routing and online processing of data streams',
    author='Nima Alamatsaz',
    author_email='nima.alamatsaz@gmail.com',
    url='https://github.com/nalamat/pype',
    py_modules=['pype'],
    install_requires=[
        'numpy',
        'scipy',
        ],
    )
