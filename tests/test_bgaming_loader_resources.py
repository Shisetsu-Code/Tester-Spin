import json
from unittest.mock import Mock

from tester_spin.providers.bgaming.runtime import (
    BGamingRuntime, _declared_loader_skin_directory, _provider_script_references,
    discover_api_v2_wire_profile,
)


LOADER = """window.__OPTIONS__.game_bundle_source = '';
const appendScript = () => {const script = window.document.createElement('script');script.type = 'module';window.document.body.append(script);return script;}
const script = appendScript();
script.src = (window.__OPTIONS__.resources_path + '/assets/index-fixture.js');
"""


def runtime():
    return BGamingRuntime(session=Mock(), launch_url="https://demo.bgaming-network.com/play/Fixture/FUN",
        api_url="https://demo.bgaming-network.com/api/Fixture/1/session", identifier="Fixture",
        csrf_header_name="", csrf_header_value="", round_series_id=1,
        options={"resources_path": "https://cdn.bgaming-network.com/html/Fixture",
                 "games_loader_source": "https://cdn.bgaming-network.com/html/Fixture/loader.js"})


def test_loader_resource_concatenation_resolves_against_declared_resource_directory():
    observed = _provider_script_references(runtime(), parent_url="https://cdn.bgaming-network.com/html/Fixture/loader.js", text=LOADER)
    assert observed == ["https://cdn.bgaming-network.com/html/Fixture/assets/index-fixture.js"]


def test_resource_loader_reaches_the_protocol_bundle_without_browser():
    rt = runtime()
    class Response:
        status_code = 200
        def __init__(self, text): self.text = text
        def raise_for_status(self): pass
    resources = {
        "https://cdn.bgaming-network.com/html/Fixture/loader.js": LOADER,
        "https://cdn.bgaming-network.com/html/Fixture/assets/index-fixture.js":
            'this.linesCount=this.linesCount||"2";this.additionalSpinOptions.mode=this.linesCount;',
    }
    rt.session.get.side_effect = lambda url, **kwargs: Response(resources[url])
    profile = discover_api_v2_wire_profile(rt, timeout_s=1)
    assert profile["spin_options"] == {"mode": "2"}
    assert profile["source"] == "https://cdn.bgaming-network.com/html/Fixture/assets/index-fixture.js"


def test_resource_assignment_must_be_executable_and_unchanged():
    correct = "https://cdn.bgaming-network.com/html/Fixture/assets/index-fixture.js"
    for source in ["/*" + LOADER + "*/", "const documentation=" + json.dumps(LOADER) + ";",
                   'window.__OPTIONS__.resources_path="https://unrelated.invalid/";'+LOADER,
                   LOADER.replace("index-fixture.js');", "index-fixture.js' + variant);"),
                   LOADER.replace("resources_path +", "other_path +")]:
        assert correct not in _provider_script_references(runtime(), parent_url="https://cdn.bgaming-network.com/html/Fixture/loader.js", text=source)


SKIN_LOADER = (
    "const SKIN_DIRS={basic:'basic',mobile:'mobile'};"
    "const skin=SKIN_DIRS.basic;"
    "const release={res:t='v0.0.38_v14.19.2'};"
    "const url=skin+'/'+t+'/bundle.js';"
)


def test_selected_skin_loader_resolves_versioned_bundle_from_provider_source():
    rt = runtime()
    base = "https://cdn.bgaming-network.com/html/Fixture"
    selected = base + "/basic/v0.0.38_v14.19.2/bundle.js"

    class Response:
        status_code = 200

        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            pass

    resources = {
        base + "/loader.js": SKIN_LOADER,
        selected: (
            'this.linesCount=this.linesCount||"2";'
            'this.additionalSpinOptions.mode=this.linesCount;'
        ),
    }
    rt.session.get.side_effect = lambda url, **kwargs: Response(resources[url])
    profile = discover_api_v2_wire_profile(rt, timeout_s=1)
    assert _declared_loader_skin_directory(SKIN_LOADER) == "basic"
    assert profile["source"] == selected
    assert profile["spin_options"] == {"mode": "2"}
    assert any(
        diag.get("url") == selected and diag.get("ok")
        for diag in profile["diagnostics"]
    )


def test_skin_loader_rejects_ambiguous_mutated_or_nonexecutable_paths():
    untrusted = [
        SKIN_LOADER.replace("SKIN_DIRS.basic", "SKIN_DIRS[skinName]"),
        SKIN_LOADER.replace(
            "const skin=SKIN_DIRS.basic;",
            "const skin=SKIN_DIRS.basic;const other=SKIN_DIRS.mobile;",
        ),
        SKIN_LOADER.replace("basic:'basic'", "basic:'../secret'"),
        SKIN_LOADER.replace("const skin=SKIN_DIRS.basic;", 
                            'const skin="SKIN_DIRS.basic";'),
        SKIN_LOADER.replace("const skin=SKIN_DIRS.basic;",
                            "/* const skin=SKIN_DIRS.basic; */"),
        SKIN_LOADER + "SKIN_DIRS.basic='changed';",
        SKIN_LOADER + "Object.assign(SKIN_DIRS,{basic:'changed'});",
        SKIN_LOADER.replace("basic:'basic'", "basic:'basic',basic:'other'"),
    ]
    untrusted += [
        SKIN_LOADER.replace(
            "const url=skin+'/'+t+'/bundle.js';",
            "const url='/unrelated/'+t+'/bundle.js';",
        ),
        SKIN_LOADER.replace(
            "const url=skin+'/'+t+'/bundle.js';",
            "const url=skin+'/'+other+'/bundle.js';",
        ),
        SKIN_LOADER.replace(
            "const skin=SKIN_DIRS.basic;",
            "const skin=SKIN_DIRS.basic;skin='mobile';",
        ),
        SKIN_LOADER.replace("res:t='v0.0.38_v14.19.2'", "res:t='v1..bad'"),
    ]
    for loader in untrusted:
        assert _declared_loader_skin_directory(loader) == ""


def test_skin_loader_checks_bundle_version_and_direct_path():
    assert _declared_loader_skin_directory(
        SKIN_LOADER, version="v0.0.38_v14.19.2"
    ) == "basic"
    assert _declared_loader_skin_directory(
        SKIN_LOADER, version="different"
    ) == ""
    direct_loader = SKIN_LOADER.replace(
        "const skin=SKIN_DIRS.basic;const release",
        "const release",
    ).replace(
        "const url=skin+'/'+t+'/bundle.js';",
        "const url=SKIN_DIRS.basic+'/'+t+'/bundle.js';",
    )
    assert _declared_loader_skin_directory(direct_loader) == "basic"
