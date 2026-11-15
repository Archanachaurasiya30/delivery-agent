"""Regression tests for the burndown live/historical split.

The bug these guard against is silent by construction: if
``ConfidenceService`` ever reads the replayed burndown series instead of live
task state, confidence becomes a function of yesterday's confidence. Nothing
raises, no assertion fails elsewhere, and the numbers just slowly stop meaning
anything. So the coupling is asserted directly, at the source level.

These are pure — no database, no fixtures — so they run anywhere.
"""

import inspect
import io
import itertools
import textwrap
import tokenize
from datetime import date

from app.services.confidence_service import ConfidenceService
from app.services.sprint_service import SprintService


def code_only(src: str) -> str:
    """Source with comments and string literals stripped.

    The rule these tests enforce is also *documented* in comments that name the
    forbidden call. Matching raw source would therefore fail on the very
    explanation of the rule, so compare executable tokens only.
    """
    out: list[str] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(textwrap.dedent(src)).readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING):
                continue
            out.append(tok.string)
    except (tokenize.TokenError, IndentationError):  # pragma: no cover - defensive
        return src
    return " ".join(out)

IDEAL = SprintService.ideal_remaining_on
START = date(2026, 6, 21)
END = date(2026, 7, 5)  # 14-day span
TOTAL = 130.0


class TestIdealLine:
    """The plan line is computed, never replayed, so it stays straight."""

    def test_starts_at_total_and_ends_at_zero(self):
        assert IDEAL(START, START, END, TOTAL) == TOTAL
        assert IDEAL(END, START, END, TOTAL) == 0.0

    def test_is_linear_across_the_span(self):
        midpoint = START + (END - START) / 2
        assert IDEAL(midpoint, START, END, TOTAL) == 65.0

    def test_clamps_outside_the_sprint_window(self):
        # Before the sprint nothing is burnt; after it, the plan is complete.
        assert IDEAL(START.replace(day=1), START, END, TOTAL) == TOTAL
        assert IDEAL(date(2026, 12, 31), START, END, TOTAL) == 0.0

    def test_single_day_sprint_does_not_divide_by_zero(self):
        assert IDEAL(START, START, START, TOTAL) == 0.0

    def test_is_independent_of_missing_readings(self):
        """Every day has an ideal value even where no snapshot exists.

        This is what lets the actual line break on a gap while the plan line
        stays continuous.
        """
        cursor, seen = START, []
        while cursor <= END:
            seen.append(IDEAL(cursor, START, END, TOTAL))
            cursor = date.fromordinal(cursor.toordinal() + 1)
        assert len(seen) == 15
        assert all(b <= a for a, b in itertools.pairwise(seen))  # monotonically down


class TestConfidenceReadsLiveStateOnly:
    """The non-negotiable split.

    ``compute_sprint_factors`` must call ``get_today_burndown_point`` and must
    NOT touch ``get_burndown`` (which replays the snapshots it is about to
    write) or ``BurndownService``.
    """

    def test_calls_the_live_point_helper(self):
        src = code_only(inspect.getsource(ConfidenceService.compute_sprint_factors))
        assert "get_today_burndown_point" in src

    def test_does_not_read_the_replayed_series(self):
        src = code_only(inspect.getsource(ConfidenceService.compute_sprint_factors))
        assert "get_burndown" not in src, (
            "compute_sprint_factors must not read the replayed burndown — that "
            "makes confidence a function of yesterday's confidence."
        )
        assert "BurndownService" not in src

    def test_confidence_service_never_imports_burndown_service(self):
        import app.services.confidence_service as mod

        assert "BurndownService" not in code_only(inspect.getsource(mod))

    def test_records_the_fields_the_replay_depends_on(self):
        """BurndownService rebuilds history from these raw factor keys."""
        src = inspect.getsource(ConfidenceService.compute_sprint_factors)
        for key in ("actual_remaining", "ideal_remaining", "total_points"):
            assert f'"{key}"' in src, f"raw factors must record {key}"


class TestBurndownServiceContract:
    def test_get_series_is_the_only_replay_path(self):
        from app.services.burndown_service import BurndownService

        src = inspect.getsource(BurndownService.get_series)
        # Gaps must be None, never zero and never carried forward.
        assert "remaining_points=None if remaining is None" in src
        assert "get_today_burndown_point" in src

    def test_sprint_service_delegates_to_it(self):
        src = inspect.getsource(SprintService.get_burndown)
        assert "BurndownService" in src
