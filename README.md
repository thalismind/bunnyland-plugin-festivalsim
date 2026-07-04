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

The "contest entry" hook other packs plug into is an **open component/registry in this
package** — Festivalsim depends on no other plugin package. Festivals are driven entirely by
the calendar (no wall-clock time, no randomness), so worlds replay deterministically.

This repo intentionally keeps all festival work outside the main `bunnyland-server` repo.

## Layout

- `server/` — Python Bunnyland plugin package with the festival calendar consequence, the
  three contributed components, the decorate/gift/contest verbs, seasonal mood, prompt
  fragments, a worldgen enrichment hook, spawn factories, and tests.

## Server Plugin

The plugin exposes `bunnyland_festivalsim.bunnyland_plugins()` and contributes:

- `FestivalComponent`, `DecorationComponent`, `ContestComponent`, `ReputationComponent`.
- `FestivalConsequence` — opens/closes festivals on the calendar and emits
  `FestivalOpenedEvent` / `FestivalClosedEvent`.
- `SeasonalMoodConsequence` — lifts every active character's mood while a festival runs.
- `decorate`, `give-gift`, `enter-contest`, `judge-contest` — the player/AI verbs.
- `register_contest_entry` — the open hook other packs call to enter their own loot.
- `festival_fragments`, `decoration_fragments`, `contest_fragments` — prompt fragments.
- `FestivalWorldgenHook` — dresses generated town squares with decorations and a contest.
- `spawn_decoration`, `spawn_contest` — spawn factories.

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
