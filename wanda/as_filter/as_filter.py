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
            result_entries_v4_cleaned, result_entries_v6_cleaned = self.irrd_client.generate_prefix_lists(irr_name)

            v4_set.update(result_entries_v4_cleaned)
            v6_set.update(result_entries_v6_cleaned)

        if len(v4_set) == 0 and len(v6_set) == 0 and self.is_customer:
            raise Exception(
                f"{self.autos} has neither IPv4, nor IPv6 filter lists. Since AS is our customer, we forbid this for security reasons.")

        return v4_set, v6_set

    def get_filter_lists(self, enable_extended_filters=False):

        irr_names = self.autos.get_irr_names()
        file_content = self.irrd_client.generate_input_aspath_access_list(self.autos.asn, irr_names[0])

        if file_content is None:
            l.warning(f"{self.autos} could not generate as-path access-lists, this breaks configuration syntax..")
            return ""

        if enable_extended_filters:
            v4_set, v6_set = self.prefix_lists

            v4_tmpl = ';\n    '.join(sorted(v4_set))
            v6_tmpl = ';\n    '.join(sorted(v6_set))

            file_content += f"""
prefix-list AS{self.autos.asn}_V4 {{
    {v4_tmpl}
}}

prefix-list AS{self.autos.asn}_V6 {{
    {v6_tmpl}
}}

policy-statement POLICY_AS{self.autos.asn}_V4 {{
    term FILTER_LISTS {{
        from {{
            as-path-neighbors as-list AS{self.autos.asn}_NEIGHBOR;
            as-path-origins as-list-group AS{self.autos.asn}_ORIGINS;
            prefix-list-filter AS{self.autos.asn}_V4 orlonger;
        }}
        then next policy;
    }}
    then reject;
}}

policy-statement POLICY_AS{self.autos.asn}_V6 {{
    term FILTER_LISTS {{
        from {{
            as-path-neighbors as-list AS{self.autos.asn}_NEIGHBOR;
            as-path-origins as-list-group AS{self.autos.asn}_ORIGINS;
            prefix-list-filter AS{self.autos.asn}_V6 orlonger;
        }}
        then next policy;
    }}
    then reject;
}}
                """
        else:
            file_content += f"""
policy-statement POLICY_AS{self.autos.asn}_V4 {{
    term IMPORT_AS_PATHS {{
        from {{
            as-path-neighbors as-list AS{self.autos.asn}_NEIGHBOR;
            as-path-origins as-list-group AS{self.autos.asn}_ORIGINS;
        }}
        then next policy;
    }}
    then reject;
}}

policy-statement POLICY_AS{self.autos.asn}_V6 {{
    term IMPORT_AS_PATHS {{
        from {{
            as-path-neighbors as-list AS{self.autos.asn}_NEIGHBOR;
            as-path-origins as-list-group AS{self.autos.asn}_ORIGINS;
        }}
        then next policy;
    }}
    then reject;
}}
                """

        return file_content
