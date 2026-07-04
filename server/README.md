# bunnyland-festivalsim (server plugin)

The out-of-tree Bunnyland plugin package `bunnyland_festivalsim`.

## Development

Tests run against a sibling `bunnyland-server` checkout without installing anything —
`tests/conftest.py` puts both this package's `src/` and `../bunnyland-server/src` on
`sys.path`. From this `server/` directory:

```bash
# uses the sibling bunnyland-server's virtualenv/deps
uv run --project ../../bunnyland-server -m pytest
# or, if bunnyland + relics are already importable:
python -m pytest
```

Lint:

```bash
uv run ruff check src tests
```

## Loading into the server

```bash
bunnyland serve --module bunnyland_festivalsim
```

`default_enabled=True`, so no `--plugin` flag is required once the module is imported.

## What it contributes

- **Components** — `FestivalComponent` (the current-festival world singleton),
  `DecorationComponent` (a placed lantern/banner), `ContestComponent` (an entry-accepting
  contest), and `ReputationComponent` (a character's standing).
- **The festival calendar** — `FestivalConsequence` reads the world clock and season with
  the core `time_of_day` helper and opens/closes festivals on a fixed, deterministic
  schedule, storing the current festival on the clock singleton and emitting
  `FestivalOpenedEvent` / `FestivalClosedEvent`.
- **Seasonal mood** — `SeasonalMoodConsequence` brightens every active character's
  `AffectComponent` a little each tick while a festival is underway (capped, and skipping
  suspended/dead characters).
- **Verbs** —
  - `decorate` hangs a fresh decoration (or a held item) in the room; `RoomDecoratedEvent`.
  - `give-gift` transfers a held item to another character in the room and warms the
    reciprocal `SocialBond`, more so during a festival; `GiftGivenEvent`.
  - `enter-contest` registers a held item into an open contest in the room;
    `ContestEnteredEvent`.
  - `judge-contest` crowns the top entry (deterministic tie-break), closes the contest, and
    awards the winner a trophy and reputation; `ContestJudgedEvent`.
- **The open contest hook** — `ContestEntry` (a contest→entry edge) and
  `register_contest_entry(...)` let any other pack enter its own loot (Hearthsim dishes,
  Anglersim catches, Bardsim songs) without importing anything else from this package.
- **Prompt fragments** — `festival_fragments` (the current festival),
  `decoration_fragments` (room decorations), and `contest_fragments` (open contests and the
  viewer's own renown).
- **A worldgen hook** — `FestivalWorldgenHook` dresses generated town squares (rooms that
  read like a square/plaza/market/green/commons) with seeded decorations and a bake-off.
- **Spawn factories** — `spawn_decoration`, `spawn_contest`.
