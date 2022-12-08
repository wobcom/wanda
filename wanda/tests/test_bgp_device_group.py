import ipaddress
import re
from ipaddress import IPv4Network, IPv6Network

import pytest

from ..bgp_device_group import BGPDeviceGroup


def get_bgp_device_group_4(**kwargs):
    group = BGPDeviceGroup(
        name="TEST",
        asn=1234,
        ip_version=4,
        max_prefixes=69,
        **kwargs
    )

    group.append_ip(
        "203.0.113.42/24"
    )
    group.append_ip(
        "203.0.113.69/24"
    )

    return group


def get_bgp_device_group_6(**kwargs):
    group = BGPDeviceGroup(
        name="TEST",
        asn=1234,
        ip_version=6,
        max_prefixes=69,
        **kwargs
    )

    group.append_ip(
        "2001:db8::42/64"
    )
    group.append_ip(
        "2001:db8::69/64"
    )

    return group


class TestBGPDeviceGroup:

    @pytest.mark.parametrize(
        "bdg,ip_version",
        [
            (get_bgp_device_group_4(), 4),
            (get_bgp_device_group_6(), 6)
        ]
    )
    def test_junos_closure(self, bdg, ip_version):
        junos_closure = bdg.to_junos()

        assert junos_closure['name'] is "TEST"
        assert junos_closure['peer_as'] is 1234
        assert isinstance(junos_closure['export'], list)
        assert isinstance(junos_closure['import'], list)
        assert junos_closure["family"][f"ipv{ip_version}_unicast"]["max_prefixes"] == 69
        assert isinstance(junos_closure['neighbors'], list)

        assert "bfd" not in junos_closure
        assert "authentication_key" not in junos_closure

    @pytest.mark.parametrize(
        "bdg",
        [
            (get_bgp_device_group_4()),
        ]
    )
    def test_neighbors_4(self, bdg):
        junos_closure = bdg.to_junos()

        assert len(junos_closure['neighbors']) == 2
        assert all(IPv4Network(n['peer'], strict=False) for n in junos_closure['neighbors'])
        assert any(n['peer'] == "203.0.113.42" for n in junos_closure['neighbors'])
        assert any(n['peer'] == "203.0.113.69" for n in junos_closure['neighbors'])

    @pytest.mark.parametrize(
        "bdg",
        [
            (get_bgp_device_group_6()),
        ]
    )
    def test_neighbors_6(self, bdg):
        junos_closure = bdg.to_junos()

        assert len(junos_closure['neighbors']) == 2
        assert all(IPv6Network(n['peer'], strict=False) for n in junos_closure['neighbors'])
        assert any(n['peer'] == "2001:db8::42" for n in junos_closure['neighbors'])
        assert any(n['peer'] == "2001:db8::69" for n in junos_closure['neighbors'])

    @pytest.mark.parametrize(
        "bdg,policy_prefix,ip_version",
        [
            (get_bgp_device_group_4(), "PEERING", 4),
            (get_bgp_device_group_4(policy_type="customer"), "CUSTOMER", 4),
            (get_bgp_device_group_4(policy_type="transit"), "UPSTREAM", 4),
            (get_bgp_device_group_4(policy_type="pni"), "PNI", 4),
            (get_bgp_device_group_6(), "PEERING", 6),
            (get_bgp_device_group_6(policy_type="customer"), "CUSTOMER", 6),
            (get_bgp_device_group_6(policy_type="transit"), "UPSTREAM", 6),
            (get_bgp_device_group_6(policy_type="pni"), "PNI", 6),
        ]
    )
    def test_basic_export_policies(self, bdg, policy_prefix, ip_version):
        export_policies = bdg.get_export_policies()

        assert len(export_policies) == 1

        m = re.match(r'(\w+)_EXPORT_(V\d)', export_policies[0])
        assert m is not None
        assert m.group(1) == policy_prefix
        assert m.group(2) == f"V{ip_version}"

    @pytest.mark.parametrize(
        "bdg,expected_export_policy",
        [
            (get_bgp_device_group_4(export_routing_policies=[{"name": "EXPORT_LUMEN_42"}]), "EXPORT_LUMEN_42"),
            (get_bgp_device_group_6(export_routing_policies=[{"name": "EXPORT_LUMEN_42"}]), "EXPORT_LUMEN_42"),
        ]
    )
    def test_additional_export_policies(self, bdg, expected_export_policy):
        export_policies = bdg.get_export_policies()

        assert len(export_policies) == 2
        assert export_policies[0] == expected_export_policy

    @pytest.mark.parametrize(
        "bdg,expected_policies",
        [
            (get_bgp_device_group_4(),
             ['FILTER_BOGONS_V4', 'FILTER_OWN_V4', 'BOGON_ASN_FILTERING', 'SCRUB_COMMUNITIES', 'TIER1_FILTERING',
              'RPKI_FILTERING', 'POLICY_AS1234_V4', 'PEERING_IMPORT_V4']),
            (get_bgp_device_group_4(is_route_server=True),
             ['FILTER_BOGONS_V4', 'FILTER_OWN_V4', 'BOGON_ASN_FILTERING', 'SCRUB_COMMUNITIES', 'TIER1_FILTERING',
              'RPKI_FILTERING', 'PEERING_IMPORT_V4']),
            (get_bgp_device_group_4(policy_type="customer"),
             ['FILTER_BOGONS_V4', 'FILTER_OWN_V4', 'BOGON_ASN_FILTERING', 'TIER1_FILTERING', 'RPKI_FILTERING',
              'POLICY_AS1234_V4', 'CUSTOMER_IMPORT_V4']),
            (get_bgp_device_group_4(policy_type="transit"),
             ['FILTER_BOGONS_V4', 'FILTER_OWN_V4', 'BOGON_ASN_FILTERING', 'SCRUB_COMMUNITIES', 'RPKI_FILTERING',
              'UPSTREAM_IMPORT_V4']),
            (get_bgp_device_group_4(policy_type="pni"),
             ['FILTER_BOGONS_V4', 'FILTER_OWN_V4', 'BOGON_ASN_FILTERING', 'SCRUB_COMMUNITIES', 'TIER1_FILTERING',
              'RPKI_FILTERING', 'POLICY_AS1234_V4', 'PNI_IMPORT_V4']),
            (get_bgp_device_group_6(),
             ['FILTER_BOGONS_V6', 'FILTER_OWN_V6', 'BOGON_ASN_FILTERING', 'SCRUB_COMMUNITIES', 'TIER1_FILTERING',
              'RPKI_FILTERING', 'POLICY_AS1234_V6', 'PEERING_IMPORT_V6']),
            (get_bgp_device_group_6(is_route_server=True),
             ['FILTER_BOGONS_V6', 'FILTER_OWN_V6', 'BOGON_ASN_FILTERING', 'SCRUB_COMMUNITIES', 'TIER1_FILTERING',
              'RPKI_FILTERING', 'PEERING_IMPORT_V6']),
            (get_bgp_device_group_6(policy_type="customer"),
             ['FILTER_BOGONS_V6', 'FILTER_OWN_V6', 'BOGON_ASN_FILTERING', 'TIER1_FILTERING', 'RPKI_FILTERING',
              'POLICY_AS1234_V6', 'CUSTOMER_IMPORT_V6']),
            (get_bgp_device_group_6(policy_type="transit"),
             ['FILTER_BOGONS_V6', 'FILTER_OWN_V6', 'BOGON_ASN_FILTERING', 'SCRUB_COMMUNITIES', 'RPKI_FILTERING',
              'UPSTREAM_IMPORT_V6']),
            (get_bgp_device_group_6(policy_type="pni"),
             ['FILTER_BOGONS_V6', 'FILTER_OWN_V6', 'BOGON_ASN_FILTERING', 'SCRUB_COMMUNITIES', 'TIER1_FILTERING',
              'RPKI_FILTERING', 'POLICY_AS1234_V6', 'PNI_IMPORT_V6']),
        ]
    )
    def test_basic_import_policies(self, bdg, expected_policies):
        import_policies = bdg.get_import_policies()

        assert import_policies == expected_policies

    @pytest.mark.parametrize(
        "bdg,expected_import_policy",
        [
            (get_bgp_device_group_4(import_routing_policies=[{"name": "IMPORT_LUMEN_42"}]), "IMPORT_LUMEN_42"),
            (get_bgp_device_group_6(import_routing_policies=[{"name": "IMPORT_LUMEN_42"}]), "IMPORT_LUMEN_42"),
        ]
    )
    def test_additional_import_policies(self, bdg, expected_import_policy):
        export_policies = bdg.get_import_policies()

        assert len(export_policies) == 9
        assert export_policies[6] == expected_import_policy

    @pytest.mark.parametrize(
        "bdg,min_interval,multiplier",
        [
            (get_bgp_device_group_4(bfd_infos={"min_interval": "123", "multiplier": "5"}), "123", "5"),
            (get_bgp_device_group_6(bfd_infos={"min_interval": "321", "multiplier": "1"}), "321", "1"),
        ]
    )
    def test_bfd(self, bdg, min_interval, multiplier):
        junos_closure = bdg.to_junos()

        assert "bfd" in junos_closure
        assert junos_closure['bfd']['min_interval'] == min_interval
        assert junos_closure['bfd']['multiplier'] == multiplier

    @pytest.mark.parametrize(
        "bdg",
        [
            (get_bgp_device_group_4(authentication_key="axahv3rohreethi8Eif8sohweiPhahx4")),
        ]
    )
    def test_authentication_key(self, bdg):
        junos_closure = bdg.to_junos()

        assert "authentication_key" in junos_closure
        assert len(junos_closure['authentication_key']) > 0
