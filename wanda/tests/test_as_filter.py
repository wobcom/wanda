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


AS_PATH_MOCK = """
as-path-group AS9136 {
    as-path a0 "^9136(9136)*$";
    as-path a1 "^9136(.)*(112|248|250)$";
}
"""

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

        file_content = asfilter.get_filter_lists(enable_extended_filters)

        assert len(file_content) > 0

        assert "policy-statement POLICY_AS9136_V4 {" in file_content
        assert "policy-statement POLICY_AS9136_V6 {" in file_content
        assert "as-path-group AS9136;"

        if enable_extended_filters:
            assert WOBCOM_EXPECTED_PREFIX_LIST in file_content
            assert "prefix-list-filter AS9136_V4 orlonger;"
            assert "prefix-list-filter AS9136_V6 orlonger;"
