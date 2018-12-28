# pylint: disable=missing-docstring

import argparse

import trask


def main():
    parser = argparse.ArgumentParser(
        prog='trask', description='run a trask file')
    parser.add_argument('path')
    args = parser.parse_args()

    ctx = trask.Context()
    root = trask.load_trask_file(ctx, args.path)
    root = trask.schema.SCHEMA.validate(root)

    trask.run(root)


main()
