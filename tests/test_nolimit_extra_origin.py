from pathlib import Path
import pytest
from tester_spin.providers.nolimit_city.extra_choices import _bound_returns

@pytest.mark.parametrize(('name','version'), [('Seamen', '1.1.41-battlenopixi.15'), ('SoakedBySeamen', '1.0.264')])
def test_extra_return_probe_preserves_acknowledged_origin(name,version):
    path=Path('data/providers/nolimit_city/_clients')/name/(version+'.js')
    if not path.exists():pytest.skip('optional exact public client unavailable')
    # Tested source is pinned below by its actual version, never sent remotely.
    source=path.read_text(encoding='utf-8')
    assert ('FREESPIN_RESPIN',0) in _bound_returns(source,True)
