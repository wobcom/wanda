import re
from functools import cached_property

from wanda.autonomous_system.autonomous_system import AutonomousSystem
from wanda.irrd_client import IRRDClient
from wanda.logger import Logger

l = Logger("as_filter.py")


class ASFilter:

    def __init__(self, irrd_client: IRRDClient, autos: AutonomousSystem, is_customer=True):
        self.irrd_client = irrd_client
        self.autos = autos
        self.is_customer = is_customer

    @cached_property
    def prefix_lists(self):

        v4_set = set()
        v6_set = set()

        irr_names = self.autos.get_irr_names()

        for irr_name in irr_names:
            result_entries_v4, result_entries_v6 = self.irrd_client.generate_prefix_lists(irr_name)

            v4_set.update(result_entries_v4)
            v6_set.update(result_entries_v6)

        if len(v4_set) == 0 and len(v6_set) == 0 and self.is_customer:
            raise Exception(
                f"{self.autos} has neither IPv4, nor IPv6 filter lists. Since AS is our customer, we forbid this for security reasons.")

        return list(v4_set), list(v6_set)

    def get_filter_lists(self, enable_extended_filters=False):

        irr_names = self.autos.get_irr_names()
        filters = {}
        filters['origin_asns'] = self.irrd_client.generate_input_aspath_access_list(self.autos.asn, irr_names[0])

        if enable_extended_filters:
            v4_set, v6_set = self.prefix_lists
            filters['v4_prefixes'] = v4_set
            filters['v6_prefixes'] = v6_set

        return filters
