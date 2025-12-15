import ipaddress
from subprocess import CalledProcessError

import pytest

from wanda.irrd_client import IRRDClient, InvalidASSETException

FAKE_PREFIX_LIST_MOCK_V4 = [
    "198.51.100.0/25"
]

FAKE_PREFIX_LIST_MOCK_V6 = [
    "2001:db8::23/32"
]


WDZ_PREFIX_LIST_MOCK_V4 = [
    "198.51.100.128/25"
]

WDZ_PREFIX_LIST_MOCK_V6 = [
    "2001:db8::42/32"
]

WOBCOM_PREFIX_LIST_MOCK_V4 = [
    "203.0.113.0/26",
    "203.0.113.64/26",
    "203.0.113.128/26",
    "203.0.113.192/26",
]

WOBCOM_PREFIX_LIST_MOCK_V6 = [
    "2001:db8::a/32",
    "2001:db8::c/32",
    "2001:db8::1/32",
    "2001:db8::5/32",
]

AS_PATH_WOBCOM = [
    "AS112",
    "AS12654",
    "AS12748",
    "AS13020",
    "AS13130",
    "AS197532",
    "AS198824",
    "AS199522",
    "AS200490",
    "AS201173",
    "AS201567",
    "AS201701",
    "AS202329",
    "AS202955",
    "AS203822",
    "AS204082",
    "AS204867",
    "AS20488",
    "AS204911",
    "AS20495",
    "AS205597",
    "AS205726",
    "AS205740",
    "AS205839",
    "AS206236",
    "AS206313",
    "AS206356",
    "AS206506",
    "AS206554",
    "AS206618",
    "AS206740",
    "AS206813",
    "AS206946",
    "AS207180",
    "AS207592",
    "AS207871",
    "AS207921",
    "AS207943",
    "AS208135",
    "AS208183",
    "AS208395",
    "AS208633",
    "AS208727",
    "AS208772",
    "AS208893",
    "AS209347",
    "AS209530",
    "AS209792",
    "AS209894",
    "AS210122",
    "AS210909",
    "AS210916",
    "AS211286",
    "AS211479",
    "AS21158",
    "AS211623",
    "AS211939",
    "AS212322",
    "AS212488",
    "AS212520",
    "AS212989",
    "AS213027",
    "AS213097",
    "AS213106",
    "AS213341",
    "AS213346",
    "AS213674",
    "AS213997",
    "AS214844",
    "AS215236",
    "AS215250",
    "AS215877",
    "AS216188",
    "AS216351",
    "AS216355",
    "AS216441",
    "AS24679",
    "AS248",
    "AS24956",
    "AS250",
    "AS29670",
    "AS30870",
    "AS31451",
    "AS33940",
    "AS34219",
    "AS3573",
    "AS3624",
    "AS396507",
    "AS39788",
    "AS41955",
    "AS42585",
    "AS44194",
    "AS44780",
    "AS47496",
    "AS48387",
    "AS48777",
    "AS49009",
    "AS49225",
    "AS49745",
    "AS49933",
    "AS50017",
    "AS50472",
    "AS57685",
    "AS59568",
    "AS59645",
    "AS60729",
    "AS60802",
    "AS62028",
    "AS62078",
    "AS64404",
    "AS64475",
    "AS6766",
    "AS9136"
]

AS_PATH_WDZ = [
    "AS208395"
]

AS_PATH_FAKE = [
    "AS64496"
]

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
            ("RIPE::AS64496:AS-FAKE", (1, 1), FAKE_PREFIX_LIST_MOCK_V4, FAKE_PREFIX_LIST_MOCK_V6),
            ("AS-WOBCOM", (4, 4), WOBCOM_PREFIX_LIST_MOCK_V4, WOBCOM_PREFIX_LIST_MOCK_V6),
            ("AS208395", (1, 1), WDZ_PREFIX_LIST_MOCK_V4, WDZ_PREFIX_LIST_MOCK_V6),
        ]
    )
    def test_prefix_lists(self, mocker, irrd_instance, irr_name, prefix_num, prefix_list_v4, prefix_list_v6):
        (prefix_num_4, prefix_num_6) = prefix_num

        mocker.patch(
            'wanda.irrd_client.IRRDClient.fetch_graphql_data',
            return_value={
                "v4": [
                    {
                        "prefixes": prefix_list_v4
                    }
                ],
                "v6": [
                    {
                        "prefixes": prefix_list_v6
                    }
                ]
            }
        )

        prefix_list_4, prefix_list_6 = irrd_instance.generate_prefix_lists(irr_name)
        assert len(prefix_list_4) == prefix_num_4
        assert len(prefix_list_6) == prefix_num_6

        # strict=False allows host_bits to be set.
        assert all(ipaddress.IPv4Network(ip, strict=False) for ip in prefix_list_4)
        assert all(ipaddress.IPv6Network(ip, strict=False) for ip in prefix_list_6)

    @pytest.mark.parametrize(
        "irr_name,",
        [
            ("RIPE::AS64496:AS-FAKE",),
        ]
    )
    def test_invalid_prefix_lists(self, mocker, irrd_instance, irr_name, ):
        mocker.patch(
            'wanda.irrd_client.IRRDClient.fetch_graphql_data',
            return_value={
                "v4": [],
                "v6": []
            }
        )

        with pytest.raises(InvalidASSETException):
            irrd_instance.generate_prefix_lists(irr_name)

    @pytest.mark.parametrize(
        "irr_name,asn,as_path_output",
        [
            ("RIPE::AS64496:AS-FAKE", 64496, AS_PATH_FAKE),
            ("AS-WOBCOM", 9136, AS_PATH_WOBCOM),
            ("AS208395", 208395, AS_PATH_WDZ),
        ]
    )
    def test_input_as_path_access_list(self, mocker, irrd_instance, irr_name, asn, as_path_output):
        mocker.patch(
            'wanda.irrd_client.IRRDClient.fetch_graphql_data',
            return_value={
                "recursiveSetMembers": [
                    {
                        "members": as_path_output
                    }
                ],
            }
        )

        access_list = irrd_instance.generate_input_aspath_access_list(irr_name)

        assert asn in access_list
        assert all([isinstance(x, int) for x in access_list])

    @pytest.mark.parametrize(
        "irr_name",
        [
            ("RIPE::AS64497:AS-FAKE",),
        ]
    )
    def test_input_invalid_as_path_access_list(self, mocker, irrd_instance, irr_name):
        mocker.patch(
            'wanda.irrd_client.IRRDClient.fetch_graphql_data',
            return_value={
                "recursiveSetMembers": [],
            }
        )

        with pytest.raises(InvalidASSETException):
            irrd_instance.generate_input_aspath_access_list(irr_name)


    def test_invalid_bgpq4_prefix_lists(self, irrd_instance):
        with pytest.raises(Exception):
            irrd_instance.call_bgpq4_prefix_lists("AS-WOBCOM", 5)
