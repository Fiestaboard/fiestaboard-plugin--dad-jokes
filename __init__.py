"""Dad Jokes plugin for FiestaBoard.

Displays random dad jokes from the icanhazdadjoke API.
"""

from typing import List, Optional
import logging
import requests

from src.devices import BoardContext
from src.plugins.base import PluginBase, PluginResult
from src.text_to_board import count_tiles

logger = logging.getLogger(__name__)

API_URL = "https://icanhazdadjoke.com/"
USER_AGENT = "FiestaBoard (https://github.com/FiestaBoard/FiestaBoard)"


def _wrap_joke(joke: str, cols: int) -> List[str]:
    """Word-wrap *joke* to at most *cols* tiles per line.

    Measured in tiles via ``count_tiles``, not characters, so a colour
    marker like ``{66}`` would count as the one tile it actually occupies.
    A single word wider than the board (more likely on a Note's 15 tiles)
    is hard-broken so no line this function emits ever exceeds *cols*.
    """
    cols = max(1, cols)
    lines: List[str] = []
    current = ""
    for word in joke.split():
        candidate = f"{current} {word}".strip()
        if count_tiles(candidate) <= cols:
            current = candidate
            continue
        if current:
            lines.append(current)
            current = ""
        while count_tiles(word) > cols:
            lines.append(word[:cols])
            word = word[cols:]
        current = word
    if current:
        lines.append(current)
    return lines or [""]


def _fit_joke_lines(lines: List[str], rows: int, cols: int) -> List[str]:
    """Fit *lines* within *rows*, keeping the ending rather than the start.

    A joke that overflows a small board loses its earliest lines, not its
    last one: the setup ("Why don't skeletons fight?") is guessable filler
    next to the delivery ("They don't have the guts."), so dropping from the
    front is what "graceful truncation that still lands the punchline"
    means here. The first surviving line gets a leading "..." when there is
    room for it, so a reader knows text was cut rather than assuming that
    is where the joke started.
    """
    rows = max(0, rows)
    if rows == 0 or len(lines) <= rows:
        return lines[:rows]

    kept = lines[-rows:]
    marker = f"...{kept[0]}" if kept[0] else "..."
    if count_tiles(marker) <= cols:
        kept[0] = marker
    return kept


def _lines_for_board(board: Optional[BoardContext], joke: str) -> List[str]:
    """Render *joke* to fit *board*, treating ``None`` as a Flagship.

    Every dimension comes from ``board.cols``/``board.rows`` -- there is no
    dimension literal on this path -- so a Note gets a short, truncated
    joke, a Flagship gets the classic 22x6 layout, and a tall note_array
    panel gets as many wrapped lines as it has rows for instead of six.
    """
    board = board or BoardContext.from_device_type("flagship")
    wrapped = _wrap_joke(joke, board.cols)
    return _fit_joke_lines(wrapped, board.rows, board.cols)


class DadJokesPlugin(PluginBase):
    """Dad Jokes plugin.

    Fetches random dad jokes from the icanhazdadjoke API
    and displays them on the board.
    """

    @property
    def plugin_id(self) -> str:
        return "dad_jokes"

    def fetch_data(self) -> PluginResult:
        """Fetch a random dad joke from the icanhazdadjoke API."""
        try:
            response = requests.get(
                API_URL,
                headers={
                    "Accept": "application/json",
                    "User-Agent": USER_AGENT,
                },
                timeout=10,
            )
            response.raise_for_status()

            joke_data = response.json()
            joke_text = joke_data.get("joke", "")

            if not joke_text:
                return PluginResult(
                    available=False,
                    error="No joke returned from API",
                )

            # ``formatted_lines`` is the path src/displays/service.py
            # actually renders (get_formatted_display() below has no caller
            # in core) -- computing it here, sized to self.board, is what
            # makes the board-aware layout reach a live board rather than
            # staying dead code.
            return PluginResult(
                available=True,
                data={"joke": joke_text},
                formatted_lines=_lines_for_board(self.board, joke_text),
            )

        except Exception as e:
            logger.exception("Error fetching dad joke")
            return PluginResult(
                available=False,
                error=str(e),
            )

    def get_formatted_display(self) -> Optional[List[str]]:
        """Return the joke formatted to fit ``self.board``.

        ``self.board`` is ``None`` outside a board-scoped render (unit
        tests and legacy callers), which is treated as a Flagship (22x6),
        the platform's own default. Width and the line budget both come
        from the board, never from a hardcoded 22/6.
        """
        result = self.get_data()
        if not result.available or not result.data:
            return None

        joke = result.data["joke"]
        board = self.board or BoardContext.from_device_type("flagship")

        lines = _lines_for_board(board, joke)
        while len(lines) < board.rows:
            lines.append("")

        return lines


# Export the plugin class
Plugin = DadJokesPlugin
