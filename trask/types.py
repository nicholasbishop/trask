# TODO: remove this
# pylint: disable=missing-docstring

import attr


@attr.s
class Call:
    name = attr.ib()
    args = attr.ib()


@attr.s
class Step:
    name = attr.ib()
    recipe = attr.ib()
    path = attr.ib()


@attr.s
class Var:
    name = attr.ib()
    choices = attr.ib(default=None)
