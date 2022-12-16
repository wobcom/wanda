import subprocess
import re
import requests


class IRRDClient:

    def __init__(self, irrd_url):
        self.data = []
        self.irrdURL = irrd_url
        self.host_params = ['-h', irrd_url]

    def call_bgpq4_aspath_access_list(self, asn, irr_name):
        command_array = ["bgpq4", *self.host_params, "-f", str(asn), "-W 100", "-J", "-l", f"AS{asn}", irr_name]
        result = subprocess.run(command_array, capture_output=True, check=True)
        result_str = result.stdout.decode("utf-8")
        return result_str

    def generate_input_aspath_access_list(self, asn, irr_name):
        # bgpq4 AS-TELIANET-V6 -f 1299 -W 100 -J -l AS1299
        result_str = self.call_bgpq4_aspath_access_list(asn, irr_name)
        m = re.search(r'.*as-path-group.*{(.|\n)*?}', result_str)

        if m:
            # Technically, returning m[0] would work, but we do some cleaning for better quality of the generated configuration

            lines = m[0].split("\n")
            new_lines = list()
            indent_count = 0

            for line in lines:
                line_without_prefixed_spaces = line.lstrip()

                if '}' in line_without_prefixed_spaces:
                    indent_count -= 1

                spaces = [" " for _ in range(indent_count * 4)]
                new_lines.append("".join(spaces) + line_without_prefixed_spaces)

                if '{' in line_without_prefixed_spaces:
                    indent_count += 1

            return "\n".join(new_lines)

        return None

    def call_bgpq4_prefix_lists(self, irr_name, ip_version):
        result = subprocess.run(
            ["bgpq4", *self.host_params, f"-{ip_version}", "-F", "%n/%l\n", irr_name],
            capture_output=True,
            check=True
        )
        result_str = result.stdout.decode("utf-8")
        return result_str

    def generate_prefix_lists(self, irr_name):
        result_v4 = self.call_bgpq4_prefix_lists(irr_name, 4)
        result_v6 = self.call_bgpq4_prefix_lists(irr_name, 6)

        result_entries_v4 = result_v4.splitlines()
        result_entries_v6 = result_v6.splitlines()

        # Stripping empty lines
        result_entries_v4_cleaned = [x for x in result_entries_v4 if x]
        result_entries_v6_cleaned = [x for x in result_entries_v6 if x]

        return result_entries_v4_cleaned, result_entries_v6_cleaned
