from tests.test_nolimit_executor import Demo,run


def test_terminal_catalog_subset_rule_survives_export_and_is_required(tmp_path,monkeypatch):
    provider,game,result=run(tmp_path,monkeypatch,Demo())
    result.discovered_modes[0]['settlement_observations']=['SETTLED_CATALOG_SUBSET']
    contract=provider.build_farm_contract(game,result)
    assert contract['modes'][0]['options']['settlement_observations']==['SETTLED_CATALOG_SUBSET']
    assert not provider.validate_farm_contract(contract)
    contract['protocol']['static'].pop('settled_catalog_subset')
    assert 'NOLIMIT_SETTLED_CATALOG_SUBSET_REQUIRED' in provider.validate_farm_contract(contract)


def test_source_counter_snapshot_requires_exported_counter_semantics(tmp_path,monkeypatch):
    provider,game,result=run(tmp_path,monkeypatch,Demo())
    result.discovered_modes[0]['choice_domains']=[{'state':'EXAMPLE','options':[0],'covered':[0],
      'remaining_counter_contract':{'field':'example','source_sha256':'a'*64}}]
    contract=provider.build_farm_contract(game,result)
    assert not provider.validate_farm_contract(contract)
    contract['protocol']['static'].pop('client_remaining_counter')
    assert 'NOLIMIT_CLIENT_COUNTER_REQUIRED' in provider.validate_farm_contract(contract)
