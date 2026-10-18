from tester_spin.providers.playtech.client_sources import script_dependencies


def test_dom_property_assignment_loader_is_not_missed():
    source='function ready(){var e=document.createElement("script");e.type="text/javascript",e.src="bundle.js",document.head.appendChild(e)}'
    assert script_dependencies(source)==['bundle.js']


def test_dynamic_property_loader_does_not_invent_a_path():
    assert script_dependencies('function ready(){var e=document.createElement("script");e.src=chooseBundle()}')==[]
