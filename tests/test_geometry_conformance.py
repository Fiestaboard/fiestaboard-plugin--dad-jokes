"""Board-geometry conformance for the Dad Jokes plugin.

Runs the shared suite from FiestaBoard core (``src/plugins/geometry_conformance.py``)
across every supported board shape: Flagship (22x6), Note (15x3), and
note_array panels from a tall-narrow 15x12 up to the largest 120x24
FiestaPanel. See that module's docstring for what "conformance" means and
why arrays are not simply "bigger than a Flagship".

Unlike a clock or a single status line, a joke is variable-length prose with
no natural cap, so ``strict_growth=True``: a taller board (holding width
constant) must show strictly more of the joke whenever a shorter board was
already full.

The plugin is non-deterministic in production -- ``fetch_data`` asks
icanhazdadjoke.com for a random joke -- which would make the suite's many
renders flake against different content on different geometries if left
unstubbed. ``requests.get`` is patched for the life of the test to always
return one fixed, long joke, so the same content is exercised at every
board size and only the layout math is what the suite is judging.
"""

import json
from pathlib import Path
from unittest.mock import Mock

from src.plugins.geometry_conformance import assert_board_conformance

from plugins.dad_jokes import DadJokesPlugin

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "manifest.json"

# Long enough that, wrapped to a Note's 15-tile width, it needs 13 lines --
# more than even a 15x12 note_array panel (12 rows) has room for, so the
# growth ladder's every rung (3 -> 12 -> 13 rows) is genuinely exercised:
# the Note is full and truncated, the 1x4 array is full but shows more, and
# the 1x8 array finally shows the whole joke uncapped.
_JOKE = (
    "I told my computer I needed a break, and now it will not stop sending "
    "me vacation ads for a beach that does not seem to actually exist "
    "anywhere on any map."
)


def _manifest() -> dict:
    with open(MANIFEST_PATH) as f:
        return json.load(f)


def _make_plugin_factory(monkeypatch):
    """Build a factory returning a fresh, network-stubbed plugin.

    The suite renders the returned plugin many times and never touches the
    network itself, so the stub is installed once here, up front, for
    whichever plugin instance(s) ``assert_board_conformance`` constructs.
    """

    def _stub_get(url, headers=None, timeout=None):
        response = Mock()
        response.raise_for_status = Mock()
        response.json.return_value = {"joke": _JOKE, "status": 200}
        return response

    monkeypatch.setattr("plugins.dad_jokes.requests.get", _stub_get)

    def make_plugin() -> DadJokesPlugin:
        plugin = DadJokesPlugin(_manifest())
        plugin.config = {"enabled": True, "refresh_seconds": 300}
        return plugin

    return make_plugin


def test_renders_on_every_board_shape(monkeypatch):
    make_plugin = _make_plugin_factory(monkeypatch)
    assert_board_conformance(
        make_plugin,
        manifest=_manifest(),
        strict_growth=True,
        require_note_array_preview=True,
    )
