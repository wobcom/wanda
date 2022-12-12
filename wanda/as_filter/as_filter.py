import re

from wanda.autonomous_system.autonomous_system import AutonomousSystem
from wanda.irrd_client import IRRDClient
from wanda.logger import Logger

l = Logger("as_filter.py")


class ASFilter:

    def __init__(self, irrd_client: IRRDClient, autos: AutonomousSystem, enable_extended_filters=False):
        self.irrd_client = irrd_client
        self.autos = autos
        self.enable_extended_filters = enable_extended_filters

    def get_prefix_lists(self):

        v4_set = set()
        v6_set = set()

        irr_names = self.autos.get_irr_names()

        for irr_name in irr_names:
            result_entries_v4_cleaned, result_entries_v6_cleaned = self.irrd_client.generate_prefix_lists(irr_name)

            v4_set.update(result_entries_v4_cleaned)
            v6_set.update(result_entries_v6_cleaned)

        if len(v4_set) == 0 and len(v6_set) == 0:
            l.error(f"{self.autos} has no v4 filter lists.")
            raise Exception(
                f"{self.autos} has no v6 filter lists. Since AS is our customer, we forbid this for security reasons.")

        return v4_set, v6_set

    def get_filter_lists(self):

        irr_names = self.autos.get_irr_names()
        file_content = self.irrd_client.generate_input_aspath_access_list(self.autos.asn, irr_names[0])

        if file_content is None:
            l.warning(f"{self.autos} could not generate as-path access-lists, this breaks configuration syntax..")
            return ""

        if self.enable_extended_filters:
            v4_set, v6_set = self.get_prefix_lists()

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
            as-path-group AS{self.autos.asn};
            prefix-list-filter AS{self.autos.asn}_V4 orlonger;
        }}
        then next policy;
    }}
    then reject;
}}

policy-statement POLICY_AS{self.autos.asn}_V6 {{
    term FILTER_LISTS {{
        from {{
            as-path-group AS{self.autos.asn};
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
        from as-path-group AS{self.autos.asn};
        then next policy;
    }}
    then reject;
}}

policy-statement POLICY_AS{self.autos.asn}_V6 {{
    term IMPORT_AS_PATHS {{
        from as-path-group AS{self.autos.asn};
        then next policy;
    }}
    then reject;
}}
                """

        return file_content
