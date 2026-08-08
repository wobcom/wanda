import re
from functools import cached_property

from wanda.autonomous_system.autonomous_system import AutonomousSystem
from wanda.irrd_client import IRRDClient, InvalidASSETException
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

        irr_v4_set = set()
        irr_v6_set = set()

        irr_names = self.autos.get_irr_names()

        for irr_name in irr_names:
            try:
                result_entries_v4, result_entries_v6 = self.irrd_client.generate_prefix_lists(irr_name)

                irr_v4_set.update(result_entries_v4)
                irr_v6_set.update(result_entries_v6)
            except InvalidASSETException:
                l.warning(f"{irr_name} is not a valid AS-SET, ignoring...")

        enforce_as_based_filtering = len(irr_names) > 0 and len(irr_v4_set) == 0 and len(irr_v6_set) == 0

        if not irr_names or enforce_as_based_filtering:
            # Print a warning to notify the user, that we will filter ASN-based
            if enforce_as_based_filtering:
                l.warning(f"AS {self.autos.asn} has not a single valid AS-SET, falling back to AS-based prefix filter lists...")

            # Using the ASN-based filtering
            result_entries_v4, result_entries_v6 = self.irrd_client.generate_prefix_lists_for_asn(self.autos.asn)

            v4_set.update(result_entries_v4)
            v6_set.update(result_entries_v6)
        else:
            # Using the AS-SET based filtering
            v4_set = irr_v4_set
            v6_set = irr_v6_set

        # If the ASN is a customer, we forbid entirely empty filter lists.
        if len(v4_set) == 0 and len(v6_set) == 0 and self.is_customer:
            raise Exception(f"{self.autos} has neither IPv4, nor IPv6 filter lists. Since AS is our customer, we forbid this for security reasons.")

        return list(v4_set), list(v6_set)

    def get_filter_lists(self, enable_extended_filters=False):

        irr_names = self.autos.get_irr_names()
        filters = {}

        default_origin_asns = [self.autos.asn]

        try:
            if len(irr_names) > 0:
                filters['origin_asns'] = sorted(self.irrd_client.generate_input_aspath_access_list(irr_names[0]))
        except InvalidASSETException:
            l.warning(f"{irr_names[0]} is not a valid AS-SET, falling back to AS-based as-path filter lists..")

        if 'origin_asns' not in filters:
            filters['origin_asns'] = default_origin_asns

        if enable_extended_filters:
            v4_set, v6_set = self.prefix_lists
            filters['v4_prefixes'] = sorted(v4_set)
            filters['v6_prefixes'] = sorted(v6_set)

        return filters
