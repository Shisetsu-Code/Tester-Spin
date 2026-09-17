import unittest
from tester_spin.providers.rubyplay.runtime import discover_client_profile

class RubyPlayIndexEvidenceTests(unittest.TestCase):
    def test_select_constructor_records_candidate_but_not_proven_domain(self):
        source = ('B.__class="com.gongxigames.math.core.game.engine.bonus.SelectBonus";'
                  'function award(t){let options=[0,1],value=0;'
                  't.putBonus(new B(U.shuffle$com_gongxigames_math_core_game_random_Random$int_A(t.getRandom(),options),value))}')
        profile = discover_client_profile([('https://example.test/game.js', source)])
        evidence = profile.to_dict().get('index_domain_evidence')
        self.assertIsInstance(evidence, list)
        self.assertEqual(evidence[0]['candidate_indices'], [0, 1])
        self.assertEqual(evidence[0]['action'], 'select')
        self.assertFalse(evidence[0]['domain_proven'])
        self.assertEqual(evidence[0]['source_url'], 'https://example.test/game.js')
        self.assertEqual(len(evidence[0]['source_sha256']), 64)

    def test_unrelated_array_is_not_a_candidate(self):
        source = ('B.__class="com.gongxigames.math.core.game.engine.bonus.SelectBonus";'
                  'function award(t){let options=[0,1]; unrelated(options); '
                  't.putBonus(new B(dynamicValues(),0))}')
        profile = discover_client_profile([('https://example.test/game.js', source)])
        self.assertEqual(profile.to_dict().get('index_domain_evidence'), [])

class RubyPlayCandidateReplayTests(unittest.TestCase):
    def test_purchase_plan_includes_all_candidate_indices(self):
        from tester_spin.providers.rubyplay import execution
        from tester_spin.providers.rubyplay.runtime import RubyPlayClientProfile
        profile = RubyPlayClientProfile(index_domain_evidence=[{'action': 'select', 'candidate_indices': [0, 1], 'domain_proven': False, 'active_engine_constructor': True}])
        planner = execution.select_probe_plan
        self.assertEqual(planner(profile, 'select', 1), [0, 1])
        self.assertEqual(planner(profile, 'respin', 1), [0])

    def test_runtime_sends_selected_candidate(self):
        from tests.test_rubyplay_manual_continuations import _runtime_for
        from tester_spin.providers.rubyplay.runtime_contracts import post_action
        runtime, session = _runtime_for('select')
        runtime.preferred_select_index = 1
        _, request, _, _ = post_action(runtime, 'select', timeout_s=5)
        self.assertEqual(request['index'], 1)

class RubyPlayAuditEvidenceTests(unittest.TestCase):
    def test_audit_keeps_candidate_evidence_unresolved(self):
        import json
        import tempfile
        from pathlib import Path
        from tests.test_exhaustive_provider_paths import ExhaustiveProviderPathTests
        from tester_spin.providers.rubyplay.exhaustive import apply_rubyplay_path_audit
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'bootstrap').mkdir()
            (root/'bootstrap'/'index-domain-evidence.json').write_text(json.dumps([{'action':'select','candidate_indices':[0,1],'domain_proven':False}]))
            (root/'step-002-request.json').write_text(json.dumps({'action':'select','index':1}))
            (root/'step-002-response.json').write_text(json.dumps({'status':'ok','data':{'an':2,'next_action':'freespin'}}))
            result = ExhaustiveProviderPathTests._result(root,'rubyplay')
            apply_rubyplay_path_audit(result,progress=lambda _:None)
            mode = result.discovered_modes[-1]
            self.assertEqual(mode.get('accepted_indices'), [1])
            self.assertEqual(mode.get('domain_evidence')[0]['candidate_indices'], [0,1])
            self.assertEqual(mode['required_options'], ['DOMAIN_UNRESOLVED'])
            self.assertEqual(result.status,'PARCIAL')

class RubyPlayActiveCandidateTests(unittest.TestCase):
    def test_live_engine_constructor_is_distinguished_from_stale_source(self):
        source = ('B.__class="com.gongxigames.math.core.game.engine.bonus.SelectBonus";'
                  'var Engine=class extends Base{constructor(){super(K.MATH_VERSION)}'
                  'award(t){let options=[0,1],value=0;t.putBonus(new B(U.shuffle$com_gongxigames_math_core_game_random_Random$int_A(t.getRandom(),options),value))}};'
                  'Engine.__class="example.Engine";factory.initBinaryFactory(new Engine);')
        evidence = discover_client_profile([('https://example.test/game.js',source)]).index_domain_evidence
        self.assertTrue(evidence[0].get('active_engine_constructor'))

    def test_stale_candidate_does_not_expand_purchase_execution(self):
        from tester_spin.providers.rubyplay.execution import select_probe_plan
        from tester_spin.providers.rubyplay.runtime import RubyPlayClientProfile
        profile = RubyPlayClientProfile(index_domain_evidence=[{'action':'select','candidate_indices':[0,1], 'active_engine_constructor':False}])
        self.assertEqual(select_probe_plan(profile,'select',1),[0])

class RubyPlayCertifiedDomainTests(unittest.TestCase):
    def source(self):
        from pathlib import Path
        return Path(__file__).with_name('fixtures').joinpath('rubyplay-select-contract.js').read_text(encoding='utf-8')

    def test_complete_client_contract_certifies_select_domain(self):
        evidence = discover_client_profile([('https://example.test/game.js',self.source())]).index_domain_evidence
        self.assertTrue(evidence[0]['domain_proven'])
        self.assertEqual(evidence[0]['candidate_indices'],[0,1])
        self.assertTrue(evidence[0]['proof_excerpts']['handler_registration'])

    def test_override_of_handle_invalidates_certificate(self):
        source = self.source().replace('class i extends Ib{','class i extends Ib{handle(t,e){return other(t,e)}')
        self.assertFalse(discover_client_profile([('x',source)]).index_domain_evidence[0]['domain_proven'])

    def test_missing_handler_binding_invalidates_certificate(self):
        source = self.source().replace('register(this.handlers,4,new tu.Selection(this,this))','register(this.handlers,5,new tu.Selection(this,this))')
        self.assertFalse(discover_client_profile([('x',source)]).index_domain_evidence[0]['domain_proven'])

    def test_length_changing_shuffle_invalidates_certificate(self):
        source = self.source().replace('e=e.slice(0,i);','e=e.slice(0,i);e.push(7);')
        self.assertFalse(discover_client_profile([('x',source)]).index_domain_evidence[0]['domain_proven'])

class RubyPlayFiniteAuditTests(unittest.TestCase):
    def test_complete_domain_requires_terminal_chain_and_two_base_confirmations(self):
        import tempfile,json
        from pathlib import Path
        from tests.test_exhaustive_provider_paths import ExhaustiveProviderPathTests
        from tester_spin.providers.rubyplay.exhaustive import apply_rubyplay_path_audit
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'bootstrap').mkdir()
            proof=discover_client_profile([('x',RubyPlayCertifiedDomainTests().source())]).index_domain_evidence
            (root/'bootstrap'/'index-domain-evidence.json').write_text(json.dumps(proof))
            for index in (0,1):
                attempt=root/f'attempt-{index}';attempt.mkdir()
                (attempt/'step-002-request.json').write_text(json.dumps({'action':'select','index':index}))
                (attempt/'step-002-response.json').write_text(json.dumps({'status':'ok','data':{'next_action':'spin'}}))
                (attempt/'return-to-base.json').write_text(json.dumps({'status':'CONFIRMED','required':2,'consecutive_base':2}))
            result=ExhaustiveProviderPathTests._result(root,'rubyplay')
            apply_rubyplay_path_audit(result,progress=lambda _:None)
            self.assertEqual(result.status,'OK')
            self.assertEqual(result.discovered_modes[-1]['required_options'],['0','1'])
            self.assertEqual(result.discovered_modes[-1]['covered_options'],['0','1'])
            (root/'attempt-1'/'return-to-base.json').write_text(json.dumps({'status':'CONFIRMED','required':1,'consecutive_base':1}))
            result=ExhaustiveProviderPathTests._result(root,'rubyplay')
            apply_rubyplay_path_audit(result,progress=lambda _:None)
            self.assertEqual(result.status,'PARCIAL')
            self.assertEqual(result.discovered_modes[-1]['covered_options'],['0'])
