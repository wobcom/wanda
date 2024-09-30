import ipaddress
from subprocess import CalledProcessError

import pytest

from wanda.irrd_client import IRRDClient

WDZ_PREFIX_LIST_MOCK_V4 = """
198.51.100.0/24
"""
WDZ_PREFIX_LIST_MOCK_V6 = """
2001:db8::42/32
"""

WOBCOM_PREFIX_LIST_MOCK_V4 = """
203.0.113.0/26
203.0.113.64/26
203.0.113.128/26
203.0.113.192/26
"""

WOBCOM_PREFIX_LIST_MOCK_V6 = """
2001:db8::a/32
2001:db8::c/32
2001:db8::1/32
2001:db8::5/32
"""

AS_PATH_WOBCOM = """
policy-options {
replace:
 as-list-group AS9136_ORIGINS {
  as-list a0 members 9136;
  as-list a1 members [ 112 248 250 3573 3624 6766 12654 12748 13020 13130 20488 21158 24679 24956 29670 31451 33940 34219 39788 41955 44194 44780 48387 48777 49009 49225 49745 49933 50017 50472 59568 59645 60729 60802 62028 64404 64475 197532 198824 200490 201173 201567 201701 202329 204867 204911 205597 206236 206313 206356 206506 206554 206618 206740 206813 206946 207180 207592 207871 207921 208135 208183 208230 208395 208633 208727 208772 208893 208942 209347 209530 209894 210909 210916 211286 211479 212488 212520 212989 213027 213097 213106 213341 215236 215250 216188 216355 216441 396507 ];
 }
}
"""

AS_PATH_WDZ = """
policy-options {
replace:
 as-list-group AS208395_ORIGINS {
  as-list a0 members 208395;
 }
}
"""


# We mock each response and threat this as a unit test since bgpq4 is considered stable.
# We might test an additional integration test later on.
@pytest.mark.unit
class TestIRRDClient:

    @pytest.fixture
    def irrd_instance(self):
        irrd_c = IRRDClient(
            irrd_url="rr.example.com"
        )

        return irrd_c

    @pytest.mark.parametrize(
        "irr_name,prefix_num,prefix_list_v4,prefix_list_v6",
        [
            ("AS-WOBCOM", (4, 4), WOBCOM_PREFIX_LIST_MOCK_V4, WOBCOM_PREFIX_LIST_MOCK_V6),
            ("AS208395", (1, 1), WDZ_PREFIX_LIST_MOCK_V4, WDZ_PREFIX_LIST_MOCK_V6),
        ]
    )
    def test_prefix_lists(self, mocker, irrd_instance, irr_name, prefix_num, prefix_list_v4, prefix_list_v6):
        (prefix_num_4, prefix_num_6) = prefix_num

        mocker.patch(
            'wanda.irrd_client.IRRDClient.call_bgpq4_prefix_lists',
            lambda self, irr_name, ip_version: prefix_list_v4 if ip_version == 4 else prefix_list_v6
        )

        prefix_list_4, prefix_list_6 = irrd_instance.generate_prefix_lists(irr_name)
        assert len(prefix_list_4) == prefix_num_4
        assert len(prefix_list_6) == prefix_num_6

        # strict=False allows host_bits to be set.
        assert all(ipaddress.IPv4Network(ip, strict=False) for ip in prefix_list_4)
        assert all(ipaddress.IPv6Network(ip, strict=False) for ip in prefix_list_6)

    @pytest.mark.parametrize(
        "irr_name,asn,as_path_output",
        [
            ("AS-WOBCOM", 9136, AS_PATH_WOBCOM),
            ("AS208395", 208395, AS_PATH_WDZ),
        ]
    )
    def test_input_as_path_access_list(self, mocker, irrd_instance, irr_name, asn, as_path_output):
        mocker.patch(
            'wanda.irrd_client.IRRDClient.call_bgpq4_aspath_access_list',
            return_value=as_path_output
        )

        access_list = irrd_instance.generate_input_aspath_access_list(asn, irr_name)

        # We need to strip some things out of the response.
        assert "policy-options" not in access_list
        assert "replace:" not in access_list

        assert access_list.startswith(f"as-list AS{asn}_NEIGHBOR members {asn};\nas-list-group AS{asn}_ORIGINS {{\n")
        assert access_list.endswith(f"\n}}")

        assert f"as-list a0 members {asn};" in access_list

    def test_invalid_bgpq4_prefix_lists(self, irrd_instance):
        with pytest.raises(Exception):
            irrd_instance.call_bgpq4_prefix_lists("AS-WOBCOM", 5)

