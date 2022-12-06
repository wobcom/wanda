# Wanda - WAN Data Aggregator

Wanda is the fairly odd fairy that configures BGP sessions and generates filters.
The output is quiet specific to our setup and automation stack, so consider it not a solution, more an inspiration.


## Architecture

The tooling connects to the [Peering-Manager](https://peering-manager.net/) API to fetch BGP sessions.
Then it generates filters for those sessions using the tool bgpq4 that fetches data from an IRR server as data source.

We're not only using this to manage peering sessions, but *all* eBGP sessions, so transit and downstream as well.

Other tooling, not in this repo, that integrates to this is an ansible-based config generator/provisioner and a sophisticated CI pipeline that deploys new sessions and updates filters every night.


## Output

Output for every router is written to the directory `generated_vars` which contains two files per device:


### BGP device groups
A yaml format specific to our automation stack to generate BGP sessions

Example:
```yaml
junos__generated_device_bgp_groups:
  PEERING_PNI_FASTLY-INC_V4:
    export:
    - PNI_EXPORT_V4
    family:
      ipv4_unicast:
        max_prefixes: 1000
    import:
    - FILTER_BOGONS_V4
    - FILTER_OWN_V4
    - BOGON_ASN_FILTERING
    - SCRUB_COMMUNITIES
    - TIER1_FILTERING
    - RPKI_FILTERING
    - POLICY_AS54113_V4
    - PNI_IMPORT_V4
    name: PEERING_PNI_FASTLY-INC_V4
    neighbors:
    - peer: 199.27.73.150
    peer_as: 54113
    type: external
  PEERING_PNI_FASTLY-INC_V6:
    export:
    - PNI_EXPORT_V6
    family:
      ipv6_unicast:
        max_prefixes: 1000
    import:
    - FILTER_BOGONS_V6
    - FILTER_OWN_V6
    - BOGON_ASN_FILTERING
    - SCRUB_COMMUNITIES
    - TIER1_FILTERING
    - RPKI_FILTERING
    - POLICY_AS54113_V6
    - PNI_IMPORT_V6
    name: PEERING_PNI_FASTLY-INC_V6
    neighbors:
    - peer: '2620:11a:c000:75:fa57::'
    peer_as: 54113
    type: external
```


### Filter Groups

Generated filters in JunOS syntax

```
prefix-list AS64404_V4 {
    204.2.64.0/20;
    94.45.224.0/19;
}

prefix-list AS64404_V6 {
    2001:678:814::/48;
    2a05:2d01::/32;
}

policy-statement POLICY_AS64404_V4 {
    term FILTER_LISTS {
        from {
            as-path-group AS64404;
            prefix-list-filter AS64404_V4 orlonger;
        }
        then next policy;
    }
    then reject;
}

policy-statement POLICY_AS64404_V6 {
    term FILTER_LISTS {
        from {
            as-path-group AS64404;
            prefix-list-filter AS64404_V6 orlonger;
        }
        then next policy;
    }
    then reject;
}
```


## Getting started

### Setup
If you are using Nix as a package manager you can can start right away using the included `flake.nix` file.

For everyone else:
- Install Python3 packages listed in `requirements.txt`
  - `pip3 install -r requirements.txt`
- bgpq4
  - `apt install bgpq4`


### Usage

#### Environment Variables

You need to specify the PeeringManager instance, which should be used. Also, you need to provide an API token.
Make sure, that this API token is only eligible to read from the PeeringManager, we do not need write access.
An API token can be obtained in your peering manager instance: `https://$URL/user/api-tokens/`


```shell
export PEERINGMANAGER_URL=https://your-peering-manager.example.com
export PEERINGMANAGER_API_TOKEN=abc123
```

#### Generating filter

Wanda can be used by simply calling the following command to regenerate all files in `generated_vars`.
**It will only consider routers that have the tag `automated`**

```shell
$ wanda

Fetching Data 100%|██████████████████████████████████| 5/5 [00:21<00:00, 0.24 Targets/s]
Generating Filter Lists for ASes 100%|███████████████| 138/138 [00:11<00:00, 12.25 AS/s]
Fetching Data 100%|█████████████████████████████████| 5/5 [00:00<00:00, 94.44 Targets/s]
Generating Configurations 100%|████████████████████| 16/16 [00:01<00:00, 10.73 Router/s]

```

#### IRRd Instance

We can select the used IRRd instance. Currently, the standard instance is `rr.ntt.net`. You can override this via the `IRRD_URL` environment variable.
```shell
IRRD_URL=rr.ntt.net wanda
```

#### Fast Mode

For small, fast needed changes (e.g. rejecting a session), we can use the `fast` mode.
This won't update the AS filter lists, but validates them. If a fast generation would break the generated configration, an error occures and `fast` mode cannot be used.

```shell
wanda --fast
```

### Limit Mode

We are also able to regenerate sessions/filters for one router only. This can be used, if no full rollout is neccessary. (for example when rolling out a single new session)
You can add a list of hosts that should be generated, calling `--limit` multiple times or adding multiple hostnames split by comma.
If this list ist omitted, the full config is generated.
This flag can be combined with fast mode.

```shell
wanda --fast --limit=router1.example.com,router2.example.com
```

### Additional Settings

#### Relationships

We have three types of special BGP relationships:
- private-peering
- transit-provider
- customer

These differ in applied and generated filters.

#### Magic tags
Sadly Peering-Manager doesn't support custom fields. So we use a few tags to configure certain things on sessions.

- Customer
  - `customer` Treat sessions on an IXP as a downstream
- BFD
  - `bfd_min_interval:300` enable bfd and set the `min_interval` to `300`
  - `bfd_multiplier:3` enable bfd and set the `multiplier` to `3`

## Authors

- Johann Wagner
- Fiona Weber
- Ember Keske

## License

See `LICENSE.md`

This license does not apply to `wanda/junos_secret.py`, refer to the header of that file. 
