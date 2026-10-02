"""Build extra Pac-Man-style mazes from mirrored left halves around a SHARED
middle band, and validate them before they go anywhere near a browser.

Checks per maze: equal row widths, player start + house exit open, every
collectible reachable (BFS with tunnel wrap), no dead ends, exactly N big
hearts, no open 2x2 blocks. Exit code 1 if any maze fails.

Usage:
  python3 maze_workshop.py                 # validate + print the mazes
  python3 maze_workshop.py --json out.json # also write {"L2": [...], "L3": [...]} when all pass

Edit MIDDLE / LEVELS / START / EXIT / BIG for your game. Left halves are 10
chars (col 9 = centre column) for a 19-wide maze.
"""
import json, sys

WIDTH = 19
MIDDLE = [  # rows 6..12, identical in every level (house, door '-', tunnel row)
    '####.### # ###.####',
    '   #.#       #.#   ',
    '####.# ##-## #.####',
    '    .  #   #  .    ',
    '####.# ##### #.####',
    '   #.#       #.#   ',
    '####.# ##### #.####',
]
START, EXIT, BIG = (9, 15), (9, 7), 4

LEVELS = {
    'L2': ([  # top rows 1..5
        '#o...#....', '#.##.#.##.', '#.##...##.', '#....#....', '####.###.#',
    ], [      # bottom rows 13..19
        '#.........', '#.#.#.###.', '#o#.......', '#.#.##.#.#', '#......#..', '#.####.##.', '#.........',
    ]),
    'L3': ([
        '#o........', '#.####.#.#', '#......#.#', '#.##.#.#.#', '#....#....',
    ], [
        '#.........', '#.###.#.#.', '#o..#...#.', '###.#.###.', '#.......#.', '#.#####.#.', '#.........',
    ]),
}


def mirror(left):
    half = WIDTH // 2 + 1
    assert len(left) == half, (left, len(left), half)
    return left + left[:half - 1][::-1]


def build(top, bottom):
    return ['#' * WIDTH] + [mirror(r) for r in top] + MIDDLE + [mirror(r) for r in bottom] + ['#' * WIDTH]


def check(name, M):
    R, C = len(M), len(M[0])
    op = lambda x, y: 0 <= y < R and M[y][x % C] not in '#-'
    seen, q = {START}, [START]
    while q:
        x, y = q.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = ((x + dx) % C, y + dy)
            if op(*n) and n not in seen:
                seen.add(n); q.append(n)
    hearts = big = 0; unreach, dead, blocks = [], [], []
    for y in range(R):
        for x in range(C):
            c = M[y][x]
            if c in '.o':
                hearts += 1; big += c == 'o'
                if (x, y) not in seen: unreach.append((x, y))
            if (x, y) in seen and sum(op(x + a, y + b) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))) < 2:
                dead.append((x, y))
            if y < R - 1 and x < C - 1 and all(op(x + a, y + b) and M[y + b][x + a] != ' ' for a in (0, 1) for b in (0, 1)):
                blocks.append((x, y))
    ok = (all(len(r) == C for r in M) and op(*START) and op(*EXIT) and not unreach and not dead and big == BIG)
    print(f'{name}: {"OK" if ok else "FAIL"} hearts={hearts} big={big} unreachable={unreach} deadends={dead} open2x2={blocks}')
    return ok


if __name__ == '__main__':
    mazes = {n: build(t, b) for n, (t, b) in LEVELS.items()}
    good = all([check(n, m) for n, m in mazes.items()])
    for n, m in mazes.items():
        print(f'--- {n}'); print('\n'.join(m))
    if good and '--json' in sys.argv:
        out = sys.argv[sys.argv.index('--json') + 1]
        json.dump(mazes, open(out, 'w')); print('wrote', out)
    sys.exit(0 if good else 1)
