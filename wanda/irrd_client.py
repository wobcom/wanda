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
      if response.status_code == 200:
          return json.loads(response.content)["data"]

      return None

    def generate_input_aspath_access_list(self, asn, irr_name):
        if re.match(r"^AS\d+$", irr_name):
            return [ irr_name[2:] ]

        body = f"""
          {{
              recursiveSetMembers(setNames: ["{irr_name}"], depth: 5) {{ members }}
          }}
        """
        result = self.fetch_graphql_data(body)

        # return unique members that are ASNs
        members = set(result["recursiveSetMembers"][0]["members"])
        return [int(i[2:]) for i in members if re.match(r"^AS\d+$", i)]


    def generate_prefix_lists(self, irr_name):
        if re.match(r"^AS\d+$", irr_name):
            # ASNs
            body = f"""
              {{
                v4: asnPrefixes(asns: ["{irr_name[2:]}"], ipVersion: 4) {{ prefixes }}
                v6: asnPrefixes(asns: ["{irr_name[2:]}"], ipVersion: 6) {{ prefixes }}
              }}
            """
        else:
            # AS-Set
            body = f"""
              {{
                v4: asSetPrefixes(setNames: ["{irr_name}"], ipVersion: 4) {{ prefixes }}
                v6: asSetPrefixes(setNames: ["{irr_name}"], ipVersion: 6) {{ prefixes }}
              }}
            """
        result = self.fetch_graphql_data(body)

        return set(result["v4"][0]["prefixes"]), set(result["v6"][0]["prefixes"])
