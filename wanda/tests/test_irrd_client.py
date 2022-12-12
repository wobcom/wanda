import ipaddress

import pytest

from wanda.irrd_client import IRRDClient


@pytest.mark.integration
class TestIRRDClient:

    @pytest.fixture
    def irrd_instance(self):
        irrd_c = IRRDClient(
            irrd_url="rr.ntt.net"
        )

        return irrd_c

    @pytest.mark.parametrize(
        "irr_name,min_prefixes",
        [
            ("AS-WOBCOM", (100, 100)),
            ("AS208395", (1, 1)),
        ]
    )
    def test_prefix_lists(self, irrd_instance, irr_name, min_prefixes):
        (min_prefixes_4, min_prefixes_6) = min_prefixes

        prefix_list_4, prefix_list_6 = irrd_instance.generate_prefix_lists(irr_name)
        assert len(prefix_list_4) >= min_prefixes_4
        assert len(prefix_list_6) >= min_prefixes_6

        # strict=False allows host_bits to be set.
        assert all(ipaddress.IPv4Network(ip, strict=False) for ip in prefix_list_4)
        assert all(ipaddress.IPv6Network(ip, strict=False) for ip in prefix_list_6)

    @pytest.mark.parametrize(
        "irr_name,asn",
        [
            ("AS-WOBCOM", 9136),
            ("AS208395", 208395),
        ]
    )
    def test_input_as_path_access_list(self, irrd_instance, irr_name, asn):
        access_list = irrd_instance.generate_input_aspath_access_list(asn, irr_name)

        # We need to strip some things out of the response.
        assert "policy-options" not in access_list
        assert "replace:" not in access_list

        assert access_list.startswith(f"as-path-group AS{asn} {{\n")
        assert access_list.endswith(f"\n}}")

        assert f"as-path a0 \"^{asn}({asn})*$\";" in access_list
