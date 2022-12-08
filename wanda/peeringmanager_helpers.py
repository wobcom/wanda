import re

from wanda.logger import Logger

l = Logger("peeringmanager_helpers.py")

def get_bgp_infos_from_tags(type, id, tag_list):
    t_bfd_multiplier = next(filter(lambda x: x['name'].startswith("bfd_multiplier:"), tag_list), None)
    t_bfd_min_interval = next(filter(lambda x: x['name'].startswith("bfd_min_interval:"), tag_list), None)

    # This is a valid case, bfd is not defined.
    if not t_bfd_multiplier and not t_bfd_min_interval:
        return None

    # If one of both is defined, which should never happen
    if bool(t_bfd_multiplier) != bool(t_bfd_min_interval):
        l.warning(f'Invalid bfd configuration in {type} {id}, because there is one tag missing.')
        return None

    bfd_multiplier = str(t_bfd_multiplier['name']).split(":")[1]
    bfd_min_interval = str(t_bfd_min_interval['name']).split(":")[1]

    if not bfd_multiplier or not bfd_min_interval:
        l.warning(f'Invalid bfd configuration in {type} {id}, because we could not find the configured values.')
        return None

    return {
        "min_interval": int(bfd_min_interval),
        "multiplier": int(bfd_multiplier),
    }


def get_config_name_from_as(display_name):
    m = re.search(r'[^(]+', display_name)
    base_name = str.strip(m[0]).upper()
    base_name = re.sub("[^A-Za-z0-9 ]", "", base_name)
    base_name = re.sub(" ", "-", base_name)
    return base_name


