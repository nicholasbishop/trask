import attr


@attr.s
class Step:
    name = attr.ib()
    recipe = attr.ib()

    def as_dict(self):
        return {self.name: self.recipe}

    def __len__(self):
        return len(self.as_dict())

    def __getitem__(self, key):
        return self.as_dict()[key]

    def __iter__(self):
        return iter(self.as_dict())
