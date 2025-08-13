import requests
import json
import re

from wanda.logger import Logger

l = Logger("irrd_client.py")


class IRRDClient:

    def __init__(self, irrd_url):
        self.irrdURL = f"https://{irrd_url}/graphql/"

    def fetch_graphql_data(self, query):
        response = requests.post(url=self.irrdURL, json={"query": query})
        response.raise_for_status()
        return response.json()["data"]

    def generate_input_aspath_access_list(self, asn, irr_name):
        body = f"""
          {{
              recursiveSetMembers(setNames: ["{irr_name}"], depth: 8) {{ members }}
          }}
        """
        result = self.fetch_graphql_data(body)

        # return unique members that are ASNs
        members = set(result["recursiveSetMembers"][0]["members"])
        return [int(i[2:]) for i in members if re.match(r"^AS\d+$", i)]

    def generate_prefix_lists_for_asn(self, asn):
        body = f"""
          {{
            v4: asnPrefixes(asns: ["{asn}"], ipVersion: 4) {{ prefixes }}
            v6: asnPrefixes(asns: ["{asn}"], ipVersion: 6) {{ prefixes }}
          }}
       """
        result = self.fetch_graphql_data(body)
        return set(result["v4"][0]["prefixes"]), set(result["v6"][0]["prefixes"])

    def generate_prefix_lists(self, irr_name):
        body = f"""
          {{
            v4: asSetPrefixes(setNames: ["{irr_name}"], ipVersion: 4) {{ prefixes }}
            v6: asSetPrefixes(setNames: ["{irr_name}"], ipVersion: 6) {{ prefixes }}
          }}
        """
        result = self.fetch_graphql_data(body)

        return set(result["v4"][0]["prefixes"]), set(result["v6"][0]["prefixes"])
