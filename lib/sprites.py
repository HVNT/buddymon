"""Hand-built 16x12 pixel sprites for every buddy line.

Sprites share a chibi base (head, eyes, belly, feet) plus per-species feature
stamps, so the set reads as one coherent pack. Grids are strings, one char per
pixel, '.' transparent; each species maps chars to its own palette.

Palette chars: B body · L belly/light · K dark/eyes · W white · plus species
feature chars (F fire, Y glow, G bulb, P petal, S shell, T ear tip, M mane,
D accent).
"""

W_PX, H_PX = 16, 12

# Eye blocks: 2x2 at (5,3) and (9,3); 'W' glint top-left, 'K' elsewhere.
_EYES = [(5, 3, "W"), (6, 3, "K"), (5, 4, "K"), (6, 4, "K"),
         (9, 3, "W"), (10, 3, "K"), (9, 4, "K"), (10, 4, "K")]
_EYE_CELLS = [(x, y) for x, y, _ in _EYES]


def _blank():
    return [["."] * W_PX for _ in range(H_PX)]


def _put(g, x, y, ch):
    if 0 <= x < W_PX and 0 <= y < H_PX:
        g[y][x] = ch


def _fill(g, x1, x2, y, ch):
    for x in range(x1, x2 + 1):
        _put(g, x, y, ch)


def _base(g):
    """Chibi base: round head rows 0-7, torso 8-10, feet row 11."""
    _fill(g, 5, 10, 0, "B")
    _fill(g, 4, 11, 1, "B")
    for y in (2, 3, 4, 5):
        _fill(g, 3, 12, y, "B")
    _fill(g, 4, 11, 6, "B")
    _fill(g, 5, 10, 7, "B")
    for y in (8, 9, 10):
        _fill(g, 5, 10, y, "B")
        _fill(g, 6, 9, y, "L")
    _fill(g, 4, 6, 11, "B")
    _fill(g, 9, 11, 11, "B")
    for x, y, ch in _EYES:
        _put(g, x, y, ch)
    _fill(g, 7, 8, 6, "K")  # mouth


def _tail_flame(g):
    _put(g, 14, 8, "Y")
    for x in (13, 14, 15):
        _put(g, x, 9, "F")
    _put(g, 12, 10, "B")
    _put(g, 13, 10, "B")


def _ears(g, tip="T"):
    _put(g, 3, 0, tip)
    _put(g, 4, 0, tip)
    _put(g, 3, 1, "B")
    _put(g, 11, 0, tip)
    _put(g, 12, 0, tip)
    _put(g, 12, 1, "B")


def _mane(g):
    _fill(g, 4, 11, 7, "M")
    _fill(g, 5, 10, 8, "M")


def _fluff_tail(g, ch="M"):
    _put(g, 13, 8, ch)
    _put(g, 14, 8, ch)
    _put(g, 13, 9, ch)
    _put(g, 14, 9, ch)
    _put(g, 15, 9, ch)


def _species():
    s = {}

    def make(name, palette, *features):
        g = _blank()
        _base(g)
        for f in features:
            f(g)
        s[name] = (["".join(row) for row in g], palette)

    fire = {"B": "#f08030", "L": "#ffd9a0", "K": "#22223a", "W": "#ffffff",
            "F": "#ff4422", "Y": "#ffd700", "D": "#9c4a1a", "T": "#9c4a1a",
            "M": "#ffd9a0"}
    make("Charmander", fire, _tail_flame)
    make("Charmeleon", {**fire, "B": "#e8443c", "L": "#ffcf8e"}, _tail_flame,
         lambda g: (_put(g, 11, 0, "D"), _put(g, 12, 1, "D")))

    def wings(g):
        for x, y in ((1, 3), (0, 4), (1, 4), (2, 4), (0, 5), (1, 5), (1, 6)):
            _put(g, x, y, "D")
            _put(g, 15 - x, y, "D")
    make("Charizard", {**fire, "D": "#2e6e8e"}, wings, _tail_flame)

    grass = {"B": "#64c8a0", "L": "#bdf0d8", "K": "#22223a", "W": "#ffffff",
             "G": "#3da35d", "P": "#f2728c", "Y": "#ffd700", "T": "#2c7a52",
             "D": "#2c7a52"}

    def bulb(g):
        _fill(g, 6, 9, 0, "G")
        _fill(g, 5, 10, 1, "G")
    make("Bulbasaur", grass, bulb)
    make("Ivysaur", grass, bulb,
         lambda g: (_put(g, 7, 0, "P"), _put(g, 8, 0, "P")))

    def flower(g):
        _fill(g, 5, 10, 0, "P")
        _put(g, 7, 0, "Y")
        _put(g, 8, 0, "Y")
        _fill(g, 5, 10, 1, "G")
    make("Venusaur", {**grass, "B": "#4aa890"}, flower)

    water = {"B": "#58a8e8", "L": "#ffe8c0", "K": "#22223a", "W": "#ffffff",
             "S": "#b07840", "T": "#36648c", "D": "#36648c", "M": "#cfe8ff"}

    def shell(g):
        for y in (8, 9, 10):
            _put(g, 3, y, "S")
            _put(g, 12, y, "S")
    make("Squirtle", water, shell,
         lambda g: (_put(g, 13, 9, "B"), _put(g, 14, 9, "B"), _put(g, 14, 8, "B")))
    make("Wartortle", {**water, "B": "#7888d8"}, shell, _ears,
         lambda g: _fluff_tail(g, "M"))

    def cannons(g):
        for x in (2, 13):
            _put(g, x, 3, "S")
            _put(g, x, 4, "S")
            _put(g, x, 2, "D")
    make("Blastoise", {**water, "B": "#4878b8", "S": "#c8c8d0"}, shell, cannons)

    electric = {"B": "#ffd730", "L": "#fff4b0", "K": "#22223a", "W": "#ffffff",
                "F": "#ff6b6b", "T": "#22223a", "Y": "#ffd730",
                "D": "#b8860b", "M": "#fff4b0"}

    def cheeks(g):
        _put(g, 4, 5, "F")
        _put(g, 11, 5, "F")

    def bolt_tail(g):
        _put(g, 13, 9, "B")
        _put(g, 14, 8, "B")
        _put(g, 15, 7, "B")
    make("Pikachu", electric, _ears, cheeks, bolt_tail)
    make("Raichu", {**electric, "B": "#f0a030", "F": "#f6f660"},
         lambda g: _ears(g, "D"), cheeks,
         lambda g: (_put(g, 13, 10, "D"), _put(g, 14, 9, "D"),
                    _put(g, 15, 8, "Y"), _put(g, 15, 7, "Y")))

    make("Eevee", {"B": "#b07848", "L": "#f0e0c0", "K": "#22223a", "W": "#ffffff",
                   "M": "#f0e0c0", "T": "#6e4628", "D": "#6e4628"},
         _ears, _mane, _fluff_tail)
    make("Vaporeon", {"B": "#50b8d8", "L": "#c0ecf4", "K": "#22223a", "W": "#ffffff",
                      "M": "#ffffff", "T": "#2c7a9c", "D": "#2c7a9c"},
         lambda g: (_put(g, 1, 2, "D"), _put(g, 2, 3, "D"),
                    _put(g, 14, 2, "D"), _put(g, 13, 3, "D")),
         _mane,
         lambda g: (_put(g, 13, 9, "D"), _put(g, 14, 9, "D"),
                    _put(g, 15, 8, "D"), _put(g, 15, 10, "D")))

    def spikes(g):
        for x in (5, 7, 10):
            _put(g, x, 0, ".")

    def collar(g):
        for x in (4, 6, 8, 10):
            _put(g, x, 7, "W")
    make("Jolteon", {"B": "#f8d030", "L": "#fff8d0", "K": "#22223a", "W": "#ffffff",
                     "T": "#b8860b", "D": "#b8860b"}, spikes, collar)
    make("Flareon", {"B": "#e85c28", "L": "#ffd9a0", "K": "#22223a", "W": "#ffffff",
                     "M": "#ffe8b8", "T": "#9c3a10", "D": "#9c3a10"},
         _ears, _mane, _fluff_tail)

    # Fallback for caught wilds with no dedicated art: type-tinted silhouette.
    make("_silhouette", {"B": "#8890a0", "L": "#aab2c0", "K": "#22223a",
                         "W": "#ffffff"})

    return s


SPRITES = _species()


def closed_eyes(grid):
    """Blink/sleep frame: collapse each eye to a 1px lash line."""
    rows = [list(r) for r in grid]
    for x, y in _EYE_CELLS:
        rows[y][x] = "B"
    for x in (5, 6, 9, 10):
        rows[4][x] = "K"
    return ["".join(r) for r in rows]


TYPE_TINTS = {
    "Fire": "#f08030", "Water": "#58a8e8", "Grass": "#64c8a0",
    "Electric": "#f8d030", "Psychic": "#f85888", "Normal": "#a8a878",
    "Flying": "#a890f0", "Bug": "#a8b820", "Poison": "#a040a0",
    "Ground": "#e0c068", "Rock": "#b8a038", "Ghost": "#705898",
    "Fighting": "#c03028", "Fairy": "#ee99ac", "Steel": "#b8b8d0",
    "Ice": "#98d8d8", "Dragon": "#7038f8", "Dark": "#705848",
}


def sprite_for(name, ptype="Normal"):
    """Return (grid, palette) — dedicated art, or a type-tinted silhouette."""
    if name in SPRITES:
        return SPRITES[name]
    grid, palette = SPRITES["_silhouette"]
    tint = TYPE_TINTS.get(ptype, "#8890a0")
    return grid, {**palette, "B": tint}
