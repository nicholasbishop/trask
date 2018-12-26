import argparse

import trask


def main():
    parser = argparse.ArgumentParser(description='run a trask file')
    parser.add_argument('path')
    args = parser.parse_args()

    ctx = Context(args.path)

    trask.run_trask_file(ctx, args.path)


main()
