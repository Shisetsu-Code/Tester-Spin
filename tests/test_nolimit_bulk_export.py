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


def test_native_paid_extra_return_requires_exported_receipt_semantics(tmp_path,monkeypatch):
    provider,game,result=run(tmp_path,monkeypatch,Demo())
    result.discovered_modes[0]['choice_domains']=[{'state':'EXTRA_SPIN','options':['no','yes'],'covered':['no','yes'],
      'native_return_contract':'nolimit-city/single-extra-freespin/v1'}]
    contract=provider.build_farm_contract(game,result)
    assert not provider.validate_farm_contract(contract)
    contract['protocol']['static'].pop('native_paid_extra_return',None)
    assert 'NOLIMIT_NATIVE_EXTRA_RETURN_REQUIRED' in provider.validate_farm_contract(contract)



def test_alternate_extra_field_survives_export_and_requires_its_wire_primitive(tmp_path,monkeypatch):
    provider,game,result=run(tmp_path,monkeypatch,Demo())
    result.discovered_modes[0]['choice_domains']=[{'state':'EXTRA_SPIN','options':['no','yes'],'covered':['no','yes'],
        'request_field':'extraSpin','source':'CLIENT_QUOTED_LITERAL_EXTRA',
        'repeat_purchase_policy':'ACCEPT_UNTIL_UNAVAILABLE','repeat_purchase_probe':{'status':'COMPLETE'}}]
    contract=provider.build_farm_contract(game,result)
    assert contract['ready']
    assert not provider.validate_farm_contract(contract)
    primitive=contract['protocol']['static']['selection_primitives'].pop('extraSpin')
    assert primitive['playerInteraction']=={'extraSpin':'{choice:yes|no}'}
    assert 'NOLIMIT_CHOICE_FIELD_PRIMITIVE_REQUIRED' in provider.validate_farm_contract(contract)
