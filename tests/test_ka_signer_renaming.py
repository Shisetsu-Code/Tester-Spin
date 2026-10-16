from tester_spin.providers.ka_gaming.runtime import parse_signing_profile

# Sanitized observed build 2080 structure; synthetic public test literal.
CLIENT = r'''Cc.Pcf=function(a,b){var d=Nb.d8d(),e=Ob.rIc(a+"2080"+b.GMb+d),f=Ob.rIc(d+b.GMb+b.aMb),g=$b.Bb().k2h(),e=Rb(0==e%2?d+"1.0.267 (2080)"+e+g+f+a+"2080":g+a+f+b.aMb+e+"2080"+d);b.zwb=e+d};k2h:function(){return"test-literal"}'''


def test_current_signer_survives_obfuscator_identifier_renaming():
    assert parse_signing_profile(CLIENT) == ("2080", "1.0.267 (2080)", "test-literal")


def test_current_signer_rejects_changed_hash_input():
    assert parse_signing_profile(CLIENT.replace("d+b.GMb+b.aMb", "d+b.GMb")) is None
