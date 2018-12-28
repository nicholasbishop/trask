# pylint: disable=missing-docstring

import argparse

import trask


def main():
    parser = argparse.ArgumentParser(
        prog='trask', description='run a trask file')
    parser.add_argument('-n', '--dry-run', action='store_true')
    parser.add_argument('path')
    args = parser.parse_args()

    trask.run(args.path, args.dry_run)


main()
