import ipaddress

from .junos_secret import juniper_encrypt


class BGPDeviceGroup:

    def __init__(self, name, asn, ip_version, max_prefixes, policy_type=None, authentication_key=None,
                 import_routing_policies=None, export_routing_policies=None, bfd_infos=None, is_route_server=False, ix_id=0):

        self.name = name
        self.asn = asn
        self.ip_version = ip_version
        self.max_prefixes = max_prefixes
        self.authentication_key = authentication_key
        self.import_routing_policies = import_routing_policies or []
        self.export_routing_policies = export_routing_policies or []
        self.policy_type = policy_type
        self.bfd_infos = bfd_infos
        self.is_route_server = is_route_server
        self.ix_id = ix_id
        self.ips = []

    def append_ip(self, ip_address):

        # We need to split the ip_address at "/" to remove the CIDR.
        raw_ip = str(ip_address).split("/")[0]
        # Making sure, this is still a valid IP address.
        parsed_ip = ipaddress.ip_address(raw_ip)

        self.ips.append(str(parsed_ip))

    def get_template_params(self):
        ip_suffix = ""
        if self.ip_version == 4:
            ip_suffix = "V4"
        elif self.ip_version == 6:
            ip_suffix = "V6"

        policy_prefix = "PEERING"

        if self.policy_type == "customer":
            policy_prefix = "CUSTOMER"

        if self.policy_type == "transit":
            policy_prefix = "UPSTREAM"

        if self.policy_type == "pni":
            policy_prefix = "PNI"

        return policy_prefix, ip_suffix

    def get_export_policies(self):

        policy_prefix, ip_suffix = self.get_template_params()

        return [
            *map(lambda x: x['name'], self.export_routing_policies),
            f"{policy_prefix}_EXPORT_{ip_suffix}"
        ]

    def get_import_policies(self):

        policy_prefix, ip_suffix = self.get_template_params()

        tier1_filter = []
        scrub_communities = []
        import_filter = self.get_dynamic_filter_policies()

        if self.policy_type != "transit":
            tier1_filter.append("TIER1_FILTERING")

        if self.policy_type != "customer":
            scrub_communities.append("SCRUB_COMMUNITIES")

        pre_policies = [policy['name'] for policy in self.import_routing_policies if policy['weight'] >= 1000]
        custom_policies = [policy['name'] for policy in self.import_routing_policies if policy['weight'] < 1000]

        return [
            *pre_policies,
            f"FILTER_BOGONS_{ip_suffix}",
            f"FILTER_OWN_{ip_suffix}",
            f"BOGON_ASN_FILTERING",
            *scrub_communities,
            *tier1_filter,
            "RPKI_FILTERING",
            *custom_policies,
            *import_filter,
            f"{policy_prefix}_IMPORT_{ip_suffix}",
        ]

    def get_dynamic_filter_policies(self):
        import_filter = []
        _, ip_suffix = self.get_template_params()

        if self.policy_type != "transit" and not self.is_route_server:
            import_filter.append(f"POLICY_AS{self.asn}_{ip_suffix}")

        return import_filter

    def to_junos(self):

        export_policies = self.get_export_policies()
        import_policies = self.get_import_policies()

        # name contains an ip version suffix every time.

        shorted_name = self.name
        if len(self.name) > 32:
            as_len = len(str(self.asn))
            cap = 29 - as_len - 1
            shorted_name = f'{self.name[0:-3][:cap]}_{str(self.asn)}{self.name[-3:]}'

        junos_elem = {
            "name": shorted_name,
            "peer_as": self.asn,
            "type": "external",
            "remove_private": True,
            "export": export_policies,
            "import": import_policies,
            "family": {},
            "neighbors": list(
                map(
                    lambda ip: {
                        "peer": ip
                    },
                    self.ips
                )
            ),
        }

        if self.bfd_infos:
            junos_elem['bfd'] = {
                "min_interval": self.bfd_infos['min_interval'],
                "multiplier": self.bfd_infos['multiplier'],
            }

        if self.ip_version == 4 and self.policy_type != "transit":
            junos_elem["family"]["ipv4_unicast"] = {}
            junos_elem["family"]["ipv4_unicast"]["max_prefixes"] = self.max_prefixes
        elif self.ip_version == 6 and self.policy_type != "transit":
            junos_elem["family"]["ipv6_unicast"] = {}
            junos_elem["family"]["ipv6_unicast"]["max_prefixes"] = self.max_prefixes

        if self.authentication_key:
            junos_elem["authentication_key"] = juniper_encrypt(self.authentication_key, 'm')

        return junos_elem
