# pylint: disable=missing-docstring

import setuptools


def long_description():
    with open('README.md') as rfile:
        return rfile.read()


setuptools.setup(
    name='trask',
    version='1.1.0',
    description='Declarative recipe-based task runner',
    long_description=long_description(),
    long_description_content_type='text/markdown',
    url='https://github.com/nicholasbishop/trask',
    author='Nicholas Bishop',
    author_email='nicholasbishop@gmail.com',
    py_modules=['trask'],
    install_requires=['attrs', 'tatsu'])
