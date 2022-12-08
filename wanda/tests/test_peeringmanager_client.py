import ipaddress
import pytest
import os

from ..peeringmanager_client import PeeringManagerClient


class TestPeeringManagerClient:

    @pytest.fixture
    def peeringmanager_instance(self):
        peeringmanager_url = os.environ.get('PEERINGMANAGER_URL')
        peeringmanager_api_token = os.environ.get('PEERINGMANAGER_API_TOKEN')

        if peeringmanager_url is None:
            raise Exception("PEERINGMANAGER_URL is empty.")
        if peeringmanager_api_token is None:
            raise Exception("PEERINGMANAGER_API_TOKEN is empty.")

        peeringmanager_c = PeeringManagerClient(
            peering_manager_url=peeringmanager_url,
            peering_manager_api_token=peeringmanager_api_token,
        )

        return peeringmanager_c

    def test_routers(self, peeringmanager_instance):
        router_list = peeringmanager_instance.get_routers()
        assert isinstance(router_list, list)

    def test_ix(self, peeringmanager_instance):
        ix_list = peeringmanager_instance.get_internet_exchanges()
        assert isinstance(ix_list, list)

    def test_connections(self, peeringmanager_instance):
        connection_list = peeringmanager_instance.get_connections()
        assert isinstance(connection_list, list)

    def test_ix_peerings(self, peeringmanager_instance):
        ix_peering_list = peeringmanager_instance.get_internet_exchange_peerings()
        assert isinstance(ix_peering_list, list)

    def test_direct_peerings(self, peeringmanager_instance):
        direct_peering_list = peeringmanager_instance.get_direct_peerings()
        assert isinstance(direct_peering_list, list)

    def test_as(self, peeringmanager_instance):
        as_list = peeringmanager_instance.get_autonomous_systems()
        assert isinstance(as_list, list)
