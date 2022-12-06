import pathlib
import multiprocessing
import subprocess
import re
from multiprocessing import Manager
from multiprocessing.managers import BaseManager, SyncManager
from multiprocessing.pool import Pool

from wanda.irrd_client import IRRDClient
from wanda.logger import Logger
from wanda.peeringmanager_helpers import get_irr_names

l = Logger("filter_list_generation.py")


def process_filter_lists_for_as(arg):
    [irrd_client, ase, allowed_as, customer_as, filter_lists] = arg
    asname = ase["name"]
    asn = ase["asn"]

    if asn not in allowed_as:
        l.info(f"Omitting {asname} ({asn}), because transit provider or no active peering. This is probably fine.")
        return

    if asn in allowed_as:
        file_content = as_path_for_as(irrd_client, ase)

        if asn in customer_as:
            v4_set, v6_set = filter_lists_for_as(irrd_client, ase)

            v4_tmpl = ';\n    '.join(sorted(v4_set))
            v6_tmpl = ';\n    '.join(sorted(v6_set))

            file_content += f"""
prefix-list AS{asn}_V4 {{
    {v4_tmpl}
}}

prefix-list AS{asn}_V6 {{
    {v6_tmpl}
}}

policy-statement POLICY_AS{asn}_V4 {{
    term FILTER_LISTS {{
        from {{
            as-path-group AS{asn};
            prefix-list-filter AS{asn}_V4 orlonger;
        }}
        then next policy;
    }}
    then reject;
}}

policy-statement POLICY_AS{asn}_V6 {{
    term FILTER_LISTS {{
        from {{
            as-path-group AS{asn};
            prefix-list-filter AS{asn}_V6 orlonger;
        }}
        then next policy;
    }}
    then reject;
}}
                """
        else:
            file_content += f"""
policy-statement POLICY_AS{asn}_V4 {{
    term IMPORT_AS_PATHS {{
        from as-path-group AS{asn};
        then next policy;
    }}
    then reject;
}}

policy-statement POLICY_AS{asn}_V6 {{
    term IMPORT_AS_PATHS {{
        from as-path-group AS{asn};
        then next policy;
    }}
    then reject;
}}
                """

        filter_lists[asn] = file_content


def as_path_for_as(irrd_client, ase):
    asn = ase["asn"]
    irr_as_set = ase["irr_as_set"]
    irr_names = [f"AS{asn}"]

    if irr_as_set:
        irr_names = get_irr_names(irr_as_set, asn)

    result_str = irrd_client.generate_input_aspath_access_list(asn, irr_names[0])

    m = re.search(r'.*as-path-group.*{(.|\n)*?}', result_str)

    if m:
        # Technically, returning m[0] would work, but we do some cleaning for better quality of the generated configuration

        lines = m[0].split("\n")
        new_lines = list()
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

    l.warning(f"AS {asn} could not generate as-path access-lists.")
    l.warning(f"AS {asn} request returned the following result:")
    l.warning(result_str)

    return ""


def filter_lists_for_as(irrd_client, ase):
    asname = ase["name"]
    asn = ase["asn"]
    irr_as_set = ase["irr_as_set"]

    irr_names = [f"AS{asn}"]

    v4_set = set()
    v6_set = set()

    if irr_as_set:
        irr_names = get_irr_names(irr_as_set, asn)

    for irr_name in irr_names:
        result_entries_v4_cleaned, result_entries_v6_cleaned = irrd_client.generate_prefix_lists(irr_name)

        v4_set.update(result_entries_v4_cleaned)
        v6_set.update(result_entries_v6_cleaned)

    if len(v4_set) == 0 and len(v6_set) == 0:
        l.error(f"AS {asn} has no v4 filter lists.")
        raise Exception(
            f"AS {asn} has no v6 filter lists. Since AS {asn} is our customer, we forbid this for security reasons.")

    return v4_set, v6_set


def main_customer_filter_lists(enlighten_manager, sync_manager, peering_manager_instance, irrd_client, hosts=None) -> int:
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
    customer_as = set()
    enabled_asn = set()
    for dp in dp_list:
        router_hostname = dp['router']['hostname']

        if hosts and router_hostname not in hosts:
            continue

        asn = dp['autonomous_system']['asn']

        enabled_asn.add(asn)

        if dp['relationship']['slug'] == "customer":
            customer_as.add(asn)

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
            customer_as.add(asn)

        if router_hostname in router_per_as:
            router_per_as[router_hostname].add(asn)
        else:
            router_per_as[router_hostname] = {asn}

    allowed_as = set()

    for dp in dp_list:
        if dp["relationship"]['slug'] == "transit-provider":
            continue

        asn = dp['autonomous_system']['asn']
        allowed_as.add(asn)

    for ixp in ixp_list:
        asn = ixp['autonomous_system']['asn']
        allowed_as.add(asn)

    filter_lists = sync_manager.dict()

    needed_as = list(
        filter(
            lambda ase: ase['asn'] in enabled_asn,
            as_list
        )
    )

    e_as = enlighten_manager.counter(total=len(needed_as), desc='Generating Filter Lists for ASes', unit='AS')

    n_worker = len(needed_as)
    pool = Pool(n_worker)
    for _ in pool.imap_unordered(process_filter_lists_for_as,
                                 [(irrd_client, ase, allowed_as, customer_as, filter_lists) for ase in needed_as]):
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
