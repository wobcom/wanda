import subprocess
import re

from wanda.logger import Logger

l = Logger("irrd_client.py")


class IRRDClient:

    POSSIBLE_RETRIES = 3

    def __init__(self, irrd_url):
        self.data = []
        self.irrdURL = irrd_url
        self.host_params = ['-h', irrd_url]

    def call_subprocess(self, command_array):

        current_try = 1

        while current_try <= self.POSSIBLE_RETRIES:
            result = subprocess.run(command_array, capture_output=True)
            if result.returncode == 0:
                result_str = result.stdout.decode("utf-8")
                return result_str

            current_try += 1

        l.error(f"Failed to execute command: {' '.join(command_array)}")
        raise Exception("bgpq4 could not be called successfully, this may be an programming error or a bad internet connection.")

    def call_bgpq4_aspath_access_list(self, asn, irr_name):
        command_array = ["bgpq4", *self.host_params, "-H", str(asn), "-W 100", "-J", "-l", f"AS{asn}_ORIGINS", irr_name]
        return self.call_subprocess(command_array)

    def generate_input_aspath_access_list(self, asn, irr_name):
        # bgpq4 AS-TELIANET-V6 -H 1299 -W 100 -J -l AS1299_ORIGINS
        result_str = self.call_bgpq4_aspath_access_list(asn, irr_name)
        m = re.search(r'.*as-list-group.*{(.|\n)*?}', result_str)

        if m:
            # Technically, only adding the AS..._NEIGHBOR list would work, but we do some cleaning for better quality of the generated configuration

            lines = m[0].split("\n")
            new_lines = list()
            new_lines.append(f"as-list AS{asn}_NEIGHBOR members {asn};")
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
        command_array = ["bgpq4", *self.host_params, f"-{ip_version}", "-F", "%n/%l\n", irr_name]
        return self.call_subprocess(command_array)

    def generate_prefix_lists(self, irr_name):
        result_v4 = self.call_bgpq4_prefix_lists(irr_name, 4)
        result_v6 = self.call_bgpq4_prefix_lists(irr_name, 6)

        result_entries_v4 = result_v4.splitlines()
        result_entries_v6 = result_v6.splitlines()

        # Stripping empty lines
        result_entries_v4_cleaned = [x for x in result_entries_v4 if x]
        result_entries_v6_cleaned = [x for x in result_entries_v6 if x]

        return result_entries_v4_cleaned, result_entries_v6_cleaned
