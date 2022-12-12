import os
import sys
from multiprocessing.managers import SyncManager

import enlighten
import argparse

from wanda.bgp_dg_generation import main_bgp
from wanda.filter_list_generation import main_customer_filter_lists
from wanda.irrd_client import IRRDClient
from wanda.peeringmanager_client import PeeringManagerClient

from wanda.logger import Logger

l = Logger("main.py")


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Automagically generate filter lists and BGP sessions for WAN-Core network')
    parser.add_argument('--fast', action='store_true', help='Skips filter list generation')
    parser.add_argument('--limit', default=[], metavar="STRING", action="append", help='List of hosts to generate configurations')

    args = parser.parse_args()

    mode = "fast" if args.fast else "full"
    if len(args.limit) > 1:
        hosts = args.limit
    elif len(args.limit) == 1 and args.limit[0] != "ci":
        hosts = args.limit[0].split(',')
    else:
        hosts = None

    irrd_url = os.environ.get('IRRD_URL', 'rr.ntt.net')

    peeringmanager_url = os.environ.get('PEERINGMANAGER_URL')
    peeringmanager_api_token = os.environ.get('PEERINGMANAGER_API_TOKEN')

    enlighten_manager = enlighten.get_manager()

    if peeringmanager_url is None:
        raise Exception("PEERINGMANAGER_URL is empty.")
    if peeringmanager_api_token is None:
        raise Exception("PEERINGMANAGER_API_TOKEN is empty.")

    SyncManager.register("IRRDClient", IRRDClient)
    SyncManager.register("PeeringManagerClient", PeeringManagerClient)
    manager = SyncManager()
    manager.start()
    irrd_client = manager.IRRDClient(irrd_url=irrd_url)
    peering_manager_instance = manager.PeeringManagerClient(peeringmanager_url, peeringmanager_api_token)

    if mode == "full":
        return_code1 = main_customer_filter_lists(enlighten_manager, manager, peering_manager_instance, irrd_client, hosts=hosts)
    else:
        return_code1 = 0
    return_code2 = main_bgp(enlighten_manager, manager, peering_manager_instance, hosts=hosts)
    return_code = return_code1 + return_code2

    enlighten_manager.stop()
    return return_code


if __name__ == '__main__':
    sys.exit(main())
