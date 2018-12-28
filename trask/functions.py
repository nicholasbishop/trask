# TODO: remove this
# pylint: disable=missing-docstring

import os

import attr

from trask import types


@attr.s
class Param:
    kind = attr.ib()


@attr.s
class Function:
    params = attr.ib()
    return_type = attr.ib()
    impl = attr.ib()


def get_from_env(_, args):
    key = args[0]
    return os.environ[key]


def get_functions():
    return {
        'env':
        Function((Param(types.Kind.String), ), types.Kind.String, get_from_env)
    }
