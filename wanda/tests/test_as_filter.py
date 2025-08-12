import pytest

from wanda.as_filter.as_filter import ASFilter
from wanda.autonomous_system.autonomous_system import AutonomousSystem
from wanda.irrd_client import IRRDClient


def get_asfilter(**kwargs):
    autos = AutonomousSystem(
        asn=9136,
        name="WOBCOM",
        irr_as_set="AS-WOBCOM"
    )

    irrd_client = IRRDClient(
        irrd_url="rr.example.com"
    )

    return ASFilter(
        irrd_client=irrd_client,
        autos=autos,
        **kwargs
    )


AS_PATH_MOCK = [
    "9136"
]

WOBCOM_PREFIX_LIST_MOCK_V4 = [
    "203.0.113.0/26",
    "203.0.113.32/26"
]

WOBCOM_PREFIX_LIST_MOCK_V6 = [
    "2001:db8::a/32"
]

WOBCOM_EXPECTED_PREFIX_LIST = """
prefix-list AS9136_V4 {
    203.0.113.0/26;
    203.0.113.32/26
}

prefix-list AS9136_V6 {
    2001:db8::a/32
}
"""


@pytest.mark.unit
class TestASFilter:

    @pytest.mark.parametrize(
        "enable_extended_filters",
        [
            (True),
            (False)
        ]
    )
    def test_prefix_lists(self, mocker, enable_extended_filters):
        asfilter = get_asfilter()

        mocker.patch(
            'wanda.irrd_client.IRRDClient.generate_prefix_lists',
            return_value=(WOBCOM_PREFIX_LIST_MOCK_V4, WOBCOM_PREFIX_LIST_MOCK_V6)
        )

        mocker.patch(
            'wanda.irrd_client.IRRDClient.generate_input_aspath_access_list',
            return_value=AS_PATH_MOCK
        )

        filter_content = asfilter.get_filter_lists(enable_extended_filters)

        assert "origin_asns" in filter_content
        assert "9136" in filter_content['origin_asns']

        if enable_extended_filters:
            assert "v4_prefixes" in filter_content
            assert "v6_prefixes" in filter_content

            assert filter_content["v4_prefixes"] == WOBCOM_PREFIX_LIST_MOCK_V4
            assert filter_content["v6_prefixes"] == WOBCOM_PREFIX_LIST_MOCK_V6

        else:
            assert "v4_prefixes" not in filter_content
            assert "v6_prefixes" not in filter_content