import pathlib
import platform
from collections import defaultdict
from multiprocessing.pool import Pool
import json
import yaml

from wanda.as_filter.as_filter import ASFilter
from wanda.autonomous_system.autonomous_system import AutonomousSystem
from wanda.logger import Logger

l = Logger("filter_list_generation.py")


def process_filter_lists_for_as(arg):
    [irrd_client, autonomous_system, customer_as, filter_lists] = arg
    asn = autonomous_system.asn
    is_customer = asn in customer_as

    ass = ASFilter(irrd_client, autonomous_system, is_customer=is_customer)
    v4_set, v6_set = ass.prefix_lists
    extended_filtering = is_customer or len(v4_set) + len(v6_set) < 5000
    as_filter_list = ass.get_filter_lists(enable_extended_filters=extended_filtering)

    filter_lists[asn] = as_filter_list


def main_customer_filter_lists(
        enlighten_manager,
        sync_manager,
        peering_manager_instance,
        irrd_client,
        wanda_configuration,
        hosts=None,
        max_threads=-1,
) -> int:
    l.hint(f"Fetching ASes, make sure VPN is enabled on your system.")

    e_targets = enlighten_manager.counter(total=5, desc='Fetching Data', unit='Targets')

    with Pool(processes=5) as fetch_pool:
        routers_res = fetch_pool.apply_async(peering_manager_instance.get_routers, ())
        as_list_res = fetch_pool.apply_async(peering_manager_instance.get_autonomous_systems, ())
        dp_list_res = fetch_pool.apply_async(peering_manager_instance.get_direct_peerings, ())
        ixp_list_res = fetch_pool.apply_async(peering_manager_instance.get_internet_exchange_peerings, ())
        connections_res = fetch_pool.apply_async(peering_manager_instance.get_connections, ())

        routers = routers_res.get()
        e_targets.update()
        as_list = as_list_res.get()
        e_targets.update()
        dp_list = dp_list_res.get()
        e_targets.update()
        ixp_list = ixp_list_res.get()
        e_targets.update()
        connections = connections_res.get()
        e_targets.update()

    e_targets.close()

    if hosts:
        router_list = list(map(lambda r: r['hostname'], routers))
        for host in hosts:
            if host not in router_list:
                l.warning(f"{host} is not a known host, ignoring...")

    router_per_as = {}
    enabled_asn = set()
    extended_filtering_as = set()
    config_hosts = wanda_configuration.get('devices', [])

    for dp in dp_list:
        router_hostname = dp['router']['hostname']

        if (hosts and router_hostname not in hosts) or router_hostname not in config_hosts:
            continue

        asn = dp['autonomous_system']['asn']
        asname = dp['autonomous_system']['name']

        # We do not filter any transit provider
        if dp["relationship"]['slug'] == "transit-provider":
            l.info(f"Omitting {asname} ({asn}) at {router_hostname}, they are our transit provider. This is probably fine.")
        else:
            enabled_asn.add(asn)

        if dp['relationship']['slug'] == "customer":
            extended_filtering_as.add(asn)

        if router_hostname in router_per_as:
            router_per_as[router_hostname].add(asn)
        else:
            router_per_as[router_hostname] = {asn}

    for ixp in ixp_list:
        fc = list(filter(lambda c: c['id'] == ixp['ixp_connection']['id'], connections))
        connection = fc[0]

        asn = ixp['autonomous_system']['asn']
        router_hostname = connection['router']['hostname']

        if (hosts and router_hostname not in hosts) or router_hostname not in config_hosts:
            continue

        if ixp['is_route_server']:
            if router_hostname not in router_per_as:
                router_per_as[router_hostname] = set()
            continue

        enabled_asn.add(asn)

        tag_list = map(lambda x: x['name'], ixp['tags'])
        is_customer = "customer" in tag_list

        if is_customer:
            extended_filtering_as.add(asn)

        if router_hostname in router_per_as:
            router_per_as[router_hostname].add(asn)
        else:
            router_per_as[router_hostname] = {asn}

    filter_lists = sync_manager.dict()

    prepared_asns = [
        (
            irrd_client,
            AutonomousSystem(asn=ase['asn'], name=ase['name'], irr_as_set=ase['irr_as_set']),
            extended_filtering_as,
            filter_lists
        ) for ase in as_list if ase['asn'] in enabled_asn
    ]

    e_as = enlighten_manager.counter(total=len(prepared_asns), desc='Generating Filter Lists for ASes', unit='AS')

    # We want to use as many processes as possible for speeds.
    # Currently, macOS does funky things if you spawn too many threads, therefore we limit those on 8 threads.
    # Linux's users can use the maximum amount of threads.
    # We do not have any Windows user, but we may also want to limit them.
    system_platform = platform.system()
    if max_threads != -1:
        n_worker = max_threads
        l.warning(f"Running with a limited amount of threads, n_worker={max_threads}")
    elif system_platform == "Linux":
        n_worker = max(len(prepared_asns), 1)
    else:
        l.warning("Running with a limited amount of threads due to OS limitations...")
        n_worker = 8

    with Pool(processes=n_worker) as fetch_pool:
        for _ in fetch_pool.imap_unordered(process_filter_lists_for_as, prepared_asns):
            e_as.update()

        e_as.close()

    for router_hostname in router_per_as:
        as_list = router_per_as[router_hostname]

        router = next(filter(lambda r: r['hostname'] == router_hostname, routers), None)
        automated_tag = next(filter(lambda t: t['name'] == "automated", router['tags']), None)
        if not automated_tag:
            l.info(f"Skipping {router['hostname']}, because there is no 'automated' tag. ")
            continue

        config_parts = {}

        for asn in as_list:
            if asn in filter_lists:
                config_parts[f"AS{asn}"] = filter_lists[asn]

        short_router_hostname = router_hostname.split(".")[0]

        match wanda_configuration.get('mode', 'junos'):
            case 'junos':
                destination_path = f"./generated_vars/"
                pathlib.Path(destination_path).mkdir(parents=True, exist_ok=True)
                destination_file = f"{destination_path}/filter_groups-{router_hostname}.yml"
                with open(destination_file, 'w') as yaml_file:
                    dump = yaml.dump(config_parts, default_flow_style=False)
                    yaml_file.write(dump)
            case 'rtbrick':
                destination_path = f"./machines/{short_router_hostname}"
                pathlib.Path(destination_path).mkdir(parents=True, exist_ok=True)
                destination_file = f"{destination_path}/generated-wanda-filters.json"
                with open(destination_file, 'w') as json_file:
                    json.dump(config_parts, json_file, indent=2)

    return 0
