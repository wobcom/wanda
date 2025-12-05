import ipaddress
import os.path
import pathlib
import re
import sys
from multiprocessing import Pool

import yaml
import json

from wanda.bgp_device_group.bgp_device_group import BGPDeviceGroup
from wanda.logger import Logger
from wanda.peeringmanager_helpers import get_config_name_from_as, get_bgp_infos_from_tags

l = Logger("bgp_dg_generation.py")


def check_for_consistency(bgp_device_groups, filter_groups):
    for bgp_device_group in bgp_device_groups:
        dynamic_filter_policies = bgp_device_group.get_dynamic_filter_policies()
        for dfp in dynamic_filter_policies:
            regex_res = re.match(r'POLICY_(AS\d+)_V\d', dfp)

            as_name = regex_res.group(1)
            if as_name not in filter_groups:
                return False
    return True


def enrich_routing_policies(group_policies, routing_policies):
    enriched_policies = []
    for pol in group_policies:
        for i in routing_policies:
            if i['id'] == pol['id']:
                enriched_policies.append(i)
    return enriched_policies


def build_bgp_device_groups_for_ix_peerings(ix_peerings, connections, as_list, routing_policies):
    bgp_device_groups = []
    for connection in connections:
      for ix in ix_peerings:

          if ix['ixp_connection']['id'] is not connection['id']:
              continue

          if ix['status']['value'] != 'enabled':
              l.info(f'Skipping Internet Exchange Peering Session with id={ix["id"]}, because is not enabled.')
              continue

          if connection['id'] == 22:
              l.info(f'id 22 !!! {ix}')

          asn = ix['autonomous_system']['asn']
          peer_ip = str(ix["ip_address"]).split("/")[0]
          authentication_key = None
          if "password" in ix:
              authentication_key = ix["password"]

          parsed_peer_ip = ipaddress.ip_address(peer_ip)
          ip_version = parsed_peer_ip.version

          max_prefixes = 0
          own_ip = None
          if ip_version == 4:
              max_prefixes = ix['autonomous_system']['ipv4_max_prefixes']
              own_ip = str(ix['ixp_connection']['ipv4_address']).split("/")[0]
          elif ip_version == 6:
              max_prefixes = ix['autonomous_system']['ipv6_max_prefixes']
              own_ip = str(ix['ixp_connection']['ipv6_address']).split("/")[0]

          existing_bgp_device_groups = list(
              filter(lambda x: x.asn == asn and x.ip_version == ip_version and x.ix_id == connection['internet_exchange_point']['id'], bgp_device_groups))

          if len(existing_bgp_device_groups) > 1:
              raise Exception("Invalid BGP Device Groupings")

          existing_bgp_device_group = next(iter(existing_bgp_device_groups), None)

          if existing_bgp_device_group:
              existing_bgp_device_group.append_neighbor(peer_ip, own_ip)
          else:

              ix_slug = str.upper(connection['internet_exchange_point']['slug'])
              as_name = get_config_name_from_as(ix['autonomous_system']['name'])

              ip_suffix = ""
              if ip_version == 4:
                  ip_suffix = "V4"
              elif ip_version == 6:
                  ip_suffix = "V6"

              group_name = str.join("_", ["PEERING", ix_slug, as_name, ip_suffix])

              tag_list = map(lambda x: x['name'], ix['tags'])
              is_customer = "customer" in tag_list

              policy_type = "peering"
              if is_customer:
                  policy_type = "customer"

              bfd_infos = get_bgp_infos_from_tags("IX", ix['id'], ix['tags'])

              bdg = BGPDeviceGroup(
                  name=group_name,
                  asn=asn,
                  ip_version=ip_version,
                  max_prefixes=max_prefixes,
                  policy_type=policy_type,
                  import_routing_policies=enrich_routing_policies(ix['import_routing_policies'], routing_policies),
                  export_routing_policies=enrich_routing_policies(ix['export_routing_policies'], routing_policies),
                  authentication_key=authentication_key,
                  bfd_infos=bfd_infos,
                  is_route_server=ix['is_route_server'],
                  ix_id=connection['internet_exchange_point']['id'],
              )

              bdg.append_neighbor(peer_ip, own_ip)
              bgp_device_groups.append(bdg)

    return bgp_device_groups



def build_bgp_device_groups_for_direct_peerings(direct_peerings, router, routing_policies):
    bgp_device_groups = []
    for dp in direct_peerings:

        if not dp['router']:
            l.info(f'Skipping Direct Peering Session with id={dp["id"]}, because there is no router attached.')
            continue

        if dp['router']['id'] is not router['id']:
            continue

        if dp['status']['value'] != 'enabled':
            l.info(f'Skipping Direct Peering Session with id={dp["id"]}, because is not enabled.')
            continue

        asn = dp['autonomous_system']['asn']
        peer_ip = str(dp["ip_address"]).split("/")[0]
        own_ip = str(dp["local_ip_address"]).split("/")[0]
        authentication_key = None
        if "password" in dp:
            authentication_key = dp["password"]

        parsed_peer_ip = ipaddress.ip_address(peer_ip)
        ip_version = parsed_peer_ip.version

        max_prefixes = 0
        if ip_version == 4:
            max_prefixes = dp['autonomous_system']['ipv4_max_prefixes']
        elif ip_version == 6:
            max_prefixes = dp['autonomous_system']['ipv6_max_prefixes']

        existing_bgp_device_groups = list(
            filter(lambda x: x.asn == asn and x.ip_version == ip_version, bgp_device_groups))

        if len(existing_bgp_device_groups) > 1:
            raise Exception("Invalid BGP Device Groupings")

        existing_bgp_device_group = next(iter(existing_bgp_device_groups), None)

        if existing_bgp_device_group:
            existing_bgp_device_group.append_neighbor(peer_ip, own_ip)

        else:

            prefix = ""
            policy_type = "peering"

            if dp['relationship']['slug'] == "transit-provider":
                prefix = "TRANSIT"
                policy_type = "transit"
            elif dp['relationship']['slug'] == "private-peering":
                prefix = "PEERING_PNI"
                policy_type = "pni"
            elif dp['relationship']['slug'] == "customer":
                prefix = "CUSTOMER"
                policy_type = "customer"
            else:
                print(dp)
                raise Exception(f"Invalid relationship detected in direct peering {dp['id']}")

            as_name = get_config_name_from_as(dp['autonomous_system']['name'])

            ip_suffix = ""
            if ip_version == 4:
                ip_suffix = "V4"
            elif ip_version == 6:
                ip_suffix = "V6"

            bfd_infos = get_bgp_infos_from_tags("DP", dp['id'], dp['tags'])

            group_name = str.join("_", [prefix, as_name, ip_suffix])
            bdg = BGPDeviceGroup(
                name=group_name,
                asn=asn,
                ip_version=ip_version,
                max_prefixes=max_prefixes,
                authentication_key=authentication_key,
                policy_type=policy_type,
                import_routing_policies=enrich_routing_policies(dp['import_routing_policies'], routing_policies),
                export_routing_policies=enrich_routing_policies(dp['export_routing_policies'], routing_policies),
                bfd_infos=bfd_infos,
                is_route_server=False,
            )

            bdg.append_neighbor(peer_ip, own_ip)
            bgp_device_groups.append(bdg)

    return bgp_device_groups


def write_junos(router, e_routers, bgp_device_groups):
    junos_bgp_device_groups = list(map(lambda g: g.to_junos(), bgp_device_groups))

    e = {
        "junos__generated_device_bgp_groups": {bdg['name']: bdg for index, bdg in
                                               enumerate(junos_bgp_device_groups)}
    }

    def noop(self, *args, **kw):
        pass

    yaml.emitter.Emitter.process_tag = noop
    pathlib.Path("./generated_vars").mkdir(parents=True, exist_ok=True)

    # wanda might have been called without the filter generation portion.
    # So, we load the existing file here and check, if everything is consistent. If not, we abort before changing anything.
    with open(f"./generated_vars/filter_groups-{router['hostname']}.yml", 'r') as yml_filter_file:
        filter_content = yaml.safe_load(yml_filter_file)
        is_consistent = check_for_consistency(bgp_device_groups, filter_content)
        if not is_consistent:
            l.error(f"Inconsistency within filter groups for {router['hostname']}, need to regenerate filter groups")
            sys.exit(42)

    with open('./generated_vars/bgp_device_groups-' + router['hostname'] + '.yml', 'w') as yaml_file:
        yaml.dump(e, yaml_file, default_flow_style=False)
        e_routers.update()


def write_rtbrick(router, e_routers, bgp_device_groups):
    rtbrick_bgp_device_groups = list(map(lambda g: g.to_rtbrick(), bgp_device_groups))

    e = {
        "routing_instances": {
            "default": {
                "protocols": {
                    "bgp": {
                        "groups": {bdg.pop('name'): bdg for index, bdg in
                                   enumerate(rtbrick_bgp_device_groups)}
                    }
                }
            }
        }
    }

    path = f"./machines/{router['name'].lower()}"
    pathlib.Path(path).mkdir(parents=True, exist_ok=True)

    # wanda might have been called without the filter generation portion.
    # So, we load the existing file here and check, if everything is consistent. If not, we abort before changing anything.
    with open(path + '/generated-wanda-filters.json', 'r') as json_filter_file:
        filter_content = json.load(json_filter_file)
        is_consistent = check_for_consistency(bgp_device_groups, filter_content)
        if not is_consistent:
            l.error(f"Inconsistency within filter groups for {router['hostname']}, need to regenerate filter groups")
            sys.exit(42)

    with open(path + '/generated-wanda.json', 'w') as json_file:
        json.dump(e, json_file, indent=4)
        e_routers.update()


def main_bgp(enlighten_manager, sync_manager, peering_manager_instance, wanda_configuration, hosts=None) -> int:
    l.hint(f"Fetching needed data from PeeringManager, make sure VPN is enabled on your system.")

    e_targets = enlighten_manager.counter(total=5, desc='Fetching Data', unit='Targets')

    with Pool(processes=6) as fetch_pool:
        ix_peerings_res = fetch_pool.apply_async(peering_manager_instance.get_internet_exchange_peerings, ())
        direct_peerings_res = fetch_pool.apply_async(peering_manager_instance.get_direct_peerings, ())
        routers_res = fetch_pool.apply_async(peering_manager_instance.get_routers, ())
        connections_res = fetch_pool.apply_async(peering_manager_instance.get_connections, ())
        as_list_res = fetch_pool.apply_async(peering_manager_instance.get_autonomous_systems, ())
        routing_policies_res = fetch_pool.apply_async(peering_manager_instance.get_routing_policies, ())

        ix_peerings = ix_peerings_res.get()
        e_targets.update()
        direct_peerings = direct_peerings_res.get()
        e_targets.update()
        routers = routers_res.get()
        e_targets.update()
        connections = connections_res.get()
        e_targets.update()
        as_list = as_list_res.get()
        e_targets.update()
        routing_policies = routing_policies_res.get()
        e_targets.update()

    e_targets.close()

    if hosts:
        router_list = list(map(lambda r: r['hostname'], routers))
        for host in hosts:
            if host not in router_list:
                l.warning(f"{host} is not a known host, ignoring...")

    wanda_mode = wanda_configuration.get('mode', 'junos')
    if wanda_mode not in ['junos', 'rtbrick']:
        l.error(f"{wanda_mode} is not a known mode, not able to generate configuration")
        sys.exit(32)

    config_hosts = wanda_configuration.get('devices', [])

    enabled_routers = list(
        filter (
            lambda r: ((not hosts) or (r['hostname'] in hosts)) and ((not config_hosts) or (r['hostname'] in config_hosts)),
            routers
        )
    )
    e_routers = enlighten_manager.counter(total=len(enabled_routers), desc='Generating Configurations', unit='Router')

    for router in enabled_routers:
        automated_tag = next(filter(lambda t: t['name'] == "automated", router['tags']), None)
        if not automated_tag:
            e_routers.update()
            l.info(f"Skipping {router['hostname']}, because there is no 'automated' tag. ")
            continue

        router_connections = list(filter(lambda c: c['router'] and c['router']['id'] == router['id'], connections))

        bgp_device_groups = build_bgp_device_groups_for_ix_peerings(ix_peerings, router_connections, as_list,
                                                                    routing_policies)

        y = build_bgp_device_groups_for_direct_peerings(direct_peerings, router, routing_policies)
        bgp_device_groups.extend(y)

        match wanda_configuration.get('mode', 'junos'):
            case 'junos':
                write_junos(router, e_routers, bgp_device_groups)
            case 'rtbrick':
                write_rtbrick(router, e_routers, bgp_device_groups)

    e_routers.close()
    return 0
