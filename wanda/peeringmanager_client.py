import requests


class PeeringManagerClient:

    def __init__(self, peering_manager_url, peering_manager_api_token):

        if not peering_manager_url:
            raise Exception("peering_manager_url is not defined.")

        if not peering_manager_api_token:
            raise Exception("peering_manager_api_token is not defined.")

        self.data = []
        self.peeringManagerAPIUrl = peering_manager_url
        self.peeringManagerAPIToken = peering_manager_api_token

        self.cached_internet_exchanges = None
        self.cached_routers = None
        self.cached_connections = None
        self.cached_internet_exchange_peerings = None
        self.cached_direct_peerings = None
        self.cached_autonomous_systems = None

    def make_request_list(self, url):
        headers = {
            "authorization": "Token " + self.peeringManagerAPIToken
        }

        fetch_url = self.peeringManagerAPIUrl + url
        needs_another_fetch = True

        results = []

        while needs_another_fetch:
            r = requests.get(fetch_url, headers=headers)
            json = r.json()

            results.extend(json['results'])

            if json['next']:
                fetch_url = json['next']
            else:
                needs_another_fetch = False

        results = sorted(results, key=lambda x: x['id'])

        return results

    def get_internet_exchanges(self):
        if not self.cached_internet_exchanges:
            self.cached_internet_exchanges = self.make_request_list('/api/peering/internet-exchanges/')
        return self.cached_internet_exchanges

    def get_routers(self):
        if not self.cached_routers:
            self.cached_routers = self.make_request_list('/api/peering/routers/')
        return self.cached_routers

    def get_connections(self):
        if not self.cached_connections:
            self.cached_connections = self.make_request_list('/api/net/connections/')
        return self.cached_connections

    def get_internet_exchange_peerings(self):
        if not self.cached_internet_exchange_peerings:
            self.cached_internet_exchange_peerings = self.make_request_list(
                '/api/peering/internet-exchange-peering-sessions/')
        return self.cached_internet_exchange_peerings

    def get_direct_peerings(self):
        if not self.cached_direct_peerings:
            self.cached_direct_peerings = self.make_request_list('/api/peering/direct-peering-sessions/')
        return self.cached_direct_peerings

    def get_autonomous_systems(self):
        if not self.cached_autonomous_systems:
            self.cached_autonomous_systems = self.make_request_list('/api/peering/autonomous-systems/')
        return self.cached_autonomous_systems
