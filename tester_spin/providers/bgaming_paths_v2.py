from __future__ import annotations

import threading

from tester_spin.models import Game, GameTestResult
from tester_spin.providers.base import Progress
from tester_spin.providers import bgaming_exhaustive as _exhaustive
from tester_spin.providers.bgaming_path_policy import (
    begin_policy_run,
    end_policy_run,
    finalize_policy_artifacts,
    install_policy,
)


install_policy(_exhaustive)


class BGamingProvider(_exhaustive.BGamingProvider):
    """BGaming exhaustive traversal with scoped purchase/wager policy.

    The legacy exhaustive adapter remains responsible for traversing every
    client-proven finite path. This layer tightens two invariants:

    * purchase identity/level are scoped PURCHASE_* dimensions, never global
      spin-option Cartesian dimensions;
    * protocol traversal uses the minimum provider-advertised wager when the
      runtime exposes one, while preserving the provider default/full wager
      domain in wager-catalog.json for later statistical sampling/emulation.

    Server-advertised purchases without client-proven wire construction are
    catalogued as unresolved instead of being probed with an invented request.
    """

    def test_game(
        self,
        game: Game,
        *,
        spins: int,
        timeout_s: float,
        stop_event: threading.Event,
        progress: Progress,
    ) -> GameTestResult:
        begin_policy_run()
        try:
            result = super().test_game(
                game,
                spins=spins,
                timeout_s=timeout_s,
                stop_event=stop_event,
                progress=progress,
            )
        finally:
            end_policy_run()

        return finalize_policy_artifacts(result)


# Preserve the public provider boundary used by registry/wiring tests.
BGamingProvider.__module__ = "tester_spin.providers.bgaming"

__all__ = ["BGamingProvider"]
