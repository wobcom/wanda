import pathlib
from multiprocessing.pool import Pool

from wanda.as_filter.as_filter import ASFilter
from wanda.autonomous_system.autonomous_system import AutonomousSystem
from wanda.logger import Logger

l = Logger("filter_list_generation.py")


def process_filter_lists_for_as(arg):
    [irrd_client, autonomous_system, customer_as, filter_lists] = arg
    asn = autonomous_system.asn

    extended_filtering = asn in customer_as

    ass = ASFilter(irrd_client, autonomous_system, enable_extended_filters=extended_filtering)
    as_filter_list = ass.get_filter_lists()

    filter_lists[asn] = as_filter_list


def main_customer_filter_lists(
        enlighten_manager,
        sync_manager,
        peering_manager_instance,
        irrd_client,
        hosts=None
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

    for dp in dp_list:
        router_hostname = dp['router']['hostname']

        if hosts and router_hostname not in hosts:
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
        if ixp['is_route_server']:
            continue

        fc = list(filter(lambda c: c['id'] == ixp['ixp_connection']['id'], connections))
        connection = fc[0]

        asn = ixp['autonomous_system']['asn']
        router_hostname = connection['router']['hostname']

        if hosts and router_hostname not in hosts:
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
    n_worker = len(prepared_asns)

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

        config_parts = []

        for asn in as_list:
            if asn in filter_lists:
                config_parts.append(filter_lists[asn])

        pathlib.Path("./generated_vars").mkdir(parents=True, exist_ok=True)
        with open('./generated_vars/filter_groups-' + router_hostname + '.tmpl', 'w') as yaml_file:
            yaml_file.write("\n".join(config_parts))

    return 0
