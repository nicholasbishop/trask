# pylint: disable=missing-docstring

import trask


def main():
    args = trask.parse_args()
    trask.run(args.path, args.dry_run)


main()
