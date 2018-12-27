import attr


@attr.s
class Step:
    name = attr.ib()
    recipe = attr.ib()
    path = attr.ib()
