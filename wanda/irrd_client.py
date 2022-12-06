import subprocess

import requests


class IRRDClient:

    def __init__(self, irrd_url):
        self.data = []
        self.irrdURL = irrd_url
        self.host_params = ['-h', irrd_url]

    def generate_input_aspath_access_list(self, asn, irr_name):
        # bgpq4 AS-TELIANET-V6 -f 1299 -W 100 -J -l AS1299
        command_array = ["bgpq4", *self.host_params, "-f", str(asn), "-W 100", "-J", "-l", f"AS{asn}", irr_name]
        result = subprocess.run(command_array, capture_output=True)
        return result.stdout.decode("utf-8")

    def generate_prefix_lists(self, irr_name):
        result_v4 = subprocess.run(["bgpq4", *self.host_params, "-4", "-F", "%n/%l\n", irr_name], capture_output=True)
        result_v6 = subprocess.run(["bgpq4", *self.host_params, "-6", "-F", "%n/%l\n", irr_name], capture_output=True)

        result_entries_v4 = result_v4.stdout.decode("utf-8").splitlines()
        result_entries_v6 = result_v6.stdout.decode("utf-8").splitlines()

        # Stripping empty lines
        result_entries_v4_cleaned = [x for x in result_entries_v4 if x]
        result_entries_v6_cleaned = [x for x in result_entries_v6 if x]

        return result_entries_v4_cleaned, result_entries_v6_cleaned
