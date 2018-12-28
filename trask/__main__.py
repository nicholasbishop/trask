# pylint: disable=missing-docstring

import argparse

import trask
from trask import phase1, phase2


def main():
    parser = argparse.ArgumentParser(
        prog='trask', description='run a trask file')
    parser.add_argument('-n', '--dry-run', action='store_true')
    parser.add_argument('path')
    args = parser.parse_args()

    root = phase1.load(args.path)
    root = phase2.Phase2.load(phase2.SCHEMA, root)

    if not args.dry_run:
        trask.run(root)


main()
