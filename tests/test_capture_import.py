import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from tester_spin.providers.bgaming.capture_import import load_capture_entries, write_capture_har


class CaptureImportTests(unittest.TestCase):
    def archive(self, root, *, host='demo.bgaming-network.com', body=None, status=200, linked=True):
        path=Path(root)/'capture.zip'
        request={'kind':'request','event_id':'one','timestamp':1,'url':f'https://{host}/api/Game/123/private-session','method':'POST','post_data':json.dumps({'command':'spin','options':{'bet':'40','mode':'2'},'token':'secret'})}
        response={'kind':'response','request_event_id':'one' if linked else 'different','status':status,'timestamp':2,'body':json.dumps(body if body is not None else {'flow':{'state':'closed'},'state_lock':'secret-lock'})}
        with zipfile.ZipFile(path,'w') as z:
            z.writestr('capture/network.jsonl','\n'.join(json.dumps(r) for r in [request,response]))
        return path

    def test_pairs_by_id_preserves_types_and_removes_credentials(self):
        with tempfile.TemporaryDirectory() as d:
            path=self.archive(d)
            target=Path(d)/'safe.har'
            write_capture_har([path], target, expected_game='Game')
            text=target.read_text(encoding='utf-8')
            self.assertNotIn('private-session',text)
            self.assertNotIn('secret',text)
            entries=json.loads(text)['log']['entries']
            req=json.loads(entries[0]['request']['postData']['text'])
            self.assertEqual(req['options']['bet'],'40')
            self.assertEqual(req['options']['mode'],'2')

    def test_mismatched_game_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                load_capture_entries(self.archive(d), expected_game='AnotherGame')

    def test_url_userinfo_is_not_retained(self):
        with tempfile.TemporaryDirectory() as d:
            entries=load_capture_entries(self.archive(d,host='user:password@demo.bgaming-network.com'),expected_game='Game')
            self.assertNotIn('password',json.dumps(entries))

    def test_unpaired_error_and_truncated_responses_are_not_executable_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(load_capture_entries(self.archive(d,linked=False),expected_game='Game'),[])
            self.assertEqual(load_capture_entries(self.archive(d,status=422),expected_game='Game'),[])
            self.assertEqual(load_capture_entries(self.archive(d,body={'error':{'code':1}}),expected_game='Game'),[])

    def test_hyperhive_host_identity_and_har_base64(self):
        import base64
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'capture.har'
            entry={'request':{'method':'POST','url':'https://yommi-rush.demo.bgaming-network.com/api','postData':{'text':json.dumps({'method':'play','params':{'req':{'bet':'200'},'token':'private'}})}},'response':{'status':200,'content':{'encoding':'base64','text':base64.b64encode(b'{"result":{"final":true}}').decode()}}}
            path.write_text(json.dumps({'log':{'entries':[entry]}}),encoding='utf-8')
            rows=load_capture_entries(path,expected_game='YommiRush')
            self.assertEqual(len(rows),1)
            self.assertTrue(json.loads(rows[0]['response']['content']['text'])['result']['final'])

    def test_unpacked_capture_directory_is_supported(self):
        with tempfile.TemporaryDirectory() as d:
            path=self.archive(d)
            folder=Path(d)/'unpacked';folder.mkdir()
            with zipfile.ZipFile(path) as z:
                (folder/'network.jsonl').write_bytes(z.read('capture/network.jsonl'))
            self.assertEqual(len(load_capture_entries(folder,expected_game='Game')),1)
