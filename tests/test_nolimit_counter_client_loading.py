import pytest
from tests.test_nolimit_executor import Demo,run

class FloatingCounterDemo(Demo):
    def __init__(self,source):
        super().__init__();self.source=source;self.loads=0;self.choice_client=None
    def _load_choice_client(self):
        self.loads+=1;self.choice_client=self.source
    def exchange(self,content,directory):
        response=super().exchange(content,directory)
        response['game']['freespinsLeft']=float(response['game']['freespinsLeft'])
        return response

def test_current_client_is_loaded_before_float_counter_closure(tmp_path,monkeypatch):
    demo=FloatingCounterDemo('g.keypadPlugin.setZeroBetSpinCounter(g.model.data.freespinsLeft)')
    _,_,result=run(tmp_path,monkeypatch,demo)
    assert demo.loads>0
    assert result.status=='OK',result.error

def test_loading_client_without_binding_does_not_coerce_counter(tmp_path,monkeypatch):
    demo=FloatingCounterDemo('unrelated.keypadCounter=0')
    _,_,result=run(tmp_path,monkeypatch,demo)
    assert result.status!='OK'
