import sys
from digraph_export import digraph_rows, write_workbook

DEFAULT_OUTPUT = 'hw_digraphs.xlsx'


def main(argv):
    rows = digraph_rows()
    output = argv[1] if len(argv) > 1 else DEFAULT_OUTPUT
    path = write_workbook(rows, output)
    print(f'{len(rows)} headword(s) written to {path}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
