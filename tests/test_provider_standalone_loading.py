from __future__ import annotations

import json
import os
import subprocess
import sys


def _loaded_provider_modules(env: dict[str, str] | None = None) -> list[str]:
    code = (
        "import json,sys; import tester_spin.providers; "
        "print(json.dumps(sorted(name for name in sys.modules "
        "if name.startswith('tester_spin.providers.') and name != 'tester_spin.providers.base')))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return json.loads(completed.stdout.strip())


def test_importing_provider_package_does_not_eager_load_provider_implementations():
    loaded = _loaded_provider_modules(os.environ.copy())
    assert loaded == []
