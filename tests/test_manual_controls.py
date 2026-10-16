import pytest
from tester_spin.manual_controls import ManualControls
from tester_spin.hardfire_launcher import HardFireError


class Client:
    def __init__(self):self.calls=[];self.fail=False
    def _rpc(self,name,args,**kwargs):
        self.calls.append((name,args))
        if name=="hardfire_status":return {"connected":True,"tab_id":7,"url":"https://demo.example/game","recording":False}
        if name=="hardfire_snapshot":return {"canvas":True,"elements":[
            {"ref":"spin","role":"button","name":"Spin","visible":True,"disabled":False},
            {"ref":"buy","role":"button","name":"Buy free spins","visible":True,"disabled":False},
            {"ref":"pick","role":"button","name":"Pick 1","visible":True,"disabled":True},
            {"ref":"hidden","role":"button","name":"Hidden","visible":False}]}
        if name=="hardfire_click_ref" and self.fail:raise HardFireError("stale_ref")
        if name=="hardfire_record_save":return {"ok":True,"path":"capture.har"}
        return {"ok":True}


def test_unknown_visible_controls_keep_purchases_but_filter_normal_spin():
    c=Client();session=ManualControls(c);r=session.refresh()
    assert [o["ref"] for o in r["options"]]==["buy"]
    assert r["canvas"] is True
    assert all("click" not in name for name,args in c.calls)


def test_exactly_one_selected_control_clicked_and_har_saved():
    c=Client();session=ManualControls(c);session.refresh();r=session.execute(ref="buy")
    assert r["executed"] is True
    assert r["har_path"]=="capture.har"
    names=[name for name,args in c.calls]
    assert names.count("hardfire_click_ref")==1
    assert names.index("hardfire_record_start")<names.index("hardfire_click_ref")<names.index("hardfire_record_save")


def test_unlisted_reference_rejected_without_action():
    c=Client();session=ManualControls(c);session.refresh()
    with pytest.raises(ValueError):session.execute(ref="made-up")
    assert not any("click" in n for n,a in c.calls)


def test_stale_click_is_not_retried_and_capture_is_saved():
    c=Client();session=ManualControls(c);session.refresh();c.fail=True;r=session.execute(ref="buy")
    assert not r["executed"]
    assert r["har_path"]=="capture.har"
    assert sum(n=="hardfire_click_ref" for n,a in c.calls)==1


def test_tab_changed_refuses_click():
    c=Client();session=ManualControls(c);session.refresh();session.observation["tab_id"]=99
    with pytest.raises(ValueError):session.execute(ref="buy")
    assert not any("click" in n for n,a in c.calls)


def test_failed_har_save_cannot_repeat_action_and_can_retry_only_saving():
    c=Client();session=ManualControls(c);session.refresh();original=c._rpc
    def fail_save(name,args,**kwargs):
        if name=="hardfire_record_save":raise HardFireError("disk full")
        return original(name,args,**kwargs)
    c._rpc=fail_save
    result=session.execute(ref="buy")
    assert result["executed"] is True
    assert "disk full" in result["capture_error"]
    with pytest.raises(ValueError):session.execute(ref="buy")
    c._rpc=original
    saved=session.save_pending()
    assert saved["har_path"]=="capture.har"
    assert sum(n=="hardfire_click_ref" for n,a in c.calls)==1
