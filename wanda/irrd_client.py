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

    def generate_input_aspath_access_list(self, asn, irr_tuple):
        (irr_source, irr_name) = irr_tuple
        source_addition = f"sources: [\"{irr_source}\"]" if irr_source else ""
        body = f"""
          {{
              recursiveSetMembers(setNames: ["{irr_name}"], depth: 8, {source_addition}) {{ members }}
          }}
        """
        result = self.fetch_graphql_data(body)

        if len(result['recursiveSetMembers']) == 0:
            l.info(f"AS-SET {irr_name} (AS {asn}) did not resolve, probably invalid AS-SET..")
            return []

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

    def generate_prefix_lists(self, irr_tuple):
        (irr_source, irr_name) = irr_tuple
        source_addition = f"sources: [\"{irr_source}\"]" if irr_source else ""
        body = f"""
          {{
            v4: asSetPrefixes(setNames: ["{irr_name}"], ipVersion: 4, {source_addition}) {{ prefixes }}
            v6: asSetPrefixes(setNames: ["{irr_name}"], ipVersion: 6, {source_addition}) {{ prefixes }}
          }}
        """
        result = self.fetch_graphql_data(body)
        
        if len(result['v4']) == 0 and len(result['v6']) == 0:
          l.info(f"AS-SET {irr_name} did not resolve, probably invalid AS-SET..")
          return set(), set()

        return set(result["v4"][0]["prefixes"]), set(result["v6"][0]["prefixes"])
