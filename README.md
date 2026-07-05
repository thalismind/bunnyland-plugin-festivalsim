# Bunnyland Festivalsim

Out-of-tree [Bunnyland](https://github.com/thalismind/bunnyland-server) plugin that hangs
**seasonal festivals and community events** on the world clock — recurring occasions with
decorations, gifts, and contests that pull characters together. An expansion-pack-sized
social pack that gives the calendar a heartbeat and a reason for everyone to be in the same
room.

The bundle:

- **A calendar of festivals** — a `FestivalConsequence` reads the world clock and season and
  **opens and closes festivals on a schedule** (Spring Bloom, High Summer, Harvest Fair,
  Midwinter), setting a `FestivalComponent` singleton and emitting world events.
- **Decorations** — a `decorate` verb hangs placeable `DecorationComponent` items (lanterns,
  banners) that raise a room's festive mood and show in descriptions.
- **Gift-giving** — a `give-gift` verb transfers a held item and warms the giver↔receiver
  `SocialBond`, warming it more during a festival.
- **Contests** — a `ContestComponent` event that other packs plug entries into via an open
  `ContestEntry` registry (`register_contest_entry`); `enter-contest` and `judge-contest`
  run a bake-off/biggest-fish/best-song, and the winner gets a trophy and reputation.
- **Seasonal mood** — a `SeasonalMoodConsequence` lifts everyone's `AffectComponent` while a
  festival is active.
- **Host-your-own festivals** (v2 headline) — a `host-festival` verb throws a festival in any
  room on any day, registered as a **core storyteller incident** (`IncidentComponent`) and
  written to world history with an imagegen illustration. `attend-festival` warms the
  guest↔host `SocialBond`, and `end-festival` resolves the incident.
- **Fairground games** (v2) — a `play-game` verb tries a `GameBoothComponent` booth; the
  win/lose outcome is a deterministic hash of player, booth, and prior plays, and a win drops
  a prize in your hands.
- **Spectacle** (v2) — a `launch-fireworks` verb dazzles the room, and (optionally, when
  `starsim` is loaded) a meteor shower overhead becomes a shared spectacle over live
  festivals.

The "contest entry" hook other packs plug into is an **open component/registry in this
package**; sibling packs' derby/bake-off/gig/game achievements are folded into a live
festival's contest by name, with **no hard dependency** on any of them (optional partners are
declared as `recommends`, and a festival runs fully standalone). Festivals are driven entirely
by the calendar and stable hashes (no wall-clock time, no randomness), so worlds replay
deterministically.

This repo intentionally keeps all festival work outside the main `bunnyland-server` repo.

## Layout

- `server/` — Python Bunnyland plugin package with the festival calendar consequence, the
  three contributed components, the decorate/gift/contest verbs, seasonal mood, prompt
  fragments, a worldgen enrichment hook, spawn factories, and tests.

## Server Plugin

The plugin exposes `bunnyland_festivalsim.bunnyland_plugins()` and contributes:

- `FestivalComponent`, `DecorationComponent`, `ContestComponent`, `ReputationComponent`,
  `HostedFestivalComponent`, `GameBoothComponent`, `SpectacleComponent`.
- Typed edges: `ContestEntry`, `Hosts`, `AttendsFestival`, `Participates`.
- `FestivalConsequence` — opens/closes festivals on the calendar and emits
  `FestivalOpenedEvent` / `FestivalClosedEvent`.
- `SeasonalMoodConsequence` — lifts every active character's mood while a festival runs.
- `MeteorShowerSpectacleConsequence` — turns a starsim meteor shower into a festival
  spectacle (disabled with a logged warning when starsim is absent).
- `FestivalStageReactor` — folds sibling packs' achievement events into a live festival's
  open contest, purely by event name.
- `decorate`, `give-gift`, `enter-contest`, `judge-contest`, `host-festival`,
  `attend-festival`, `end-festival`, `play-game`, `launch-fireworks` — the player/AI verbs.
- `register_contest_entry` — the open hook other packs call to enter their own loot.
- `festival_fragments`, `decoration_fragments`, `contest_fragments`, `hosting_fragments`,
  `game_fragments`, `spectacle_fragments` — prompt fragments.
- `FestivalWorldgenHook` — dresses generated town squares with decorations and a contest.
- `spawn_decoration`, `spawn_contest`, `spawn_booth`, `spawn_spectacle` — spawn factories.

## Running

This package builds no containers. It is loaded into the stock server via `--module`:

```bash
bunnyland serve --module bunnyland_festivalsim
```

`default_enabled=True`, so no `--plugin` flag is required once the module is imported. The
`bunnyland_festivalsim` package must be importable by the server (installed into the
server's environment, or on `PYTHONPATH`).

## Development

Run server tests against a sibling `bunnyland-server` checkout (no install required —
`server/tests/conftest.py` puts both packages on `sys.path`). From `server/`:

```bash
uv run --project ../../bunnyland-server -m pytest
uv run --project ../../bunnyland-server ruff check src tests
```

See [`server/README.md`](server/README.md) for more detail.

## Contributing & Conduct

This plugin follows the Bunnyland project's
[contribution guidelines](CONTRIBUTING.md) and [code of conduct](CODE_OF_CONDUCT.md),
which point back to the `bunnyland-server` repository.

## License

Licensed under the GNU Affero General Public License v3.0. See [LICENSE](LICENSE).
