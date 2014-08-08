# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from . import aws
import bisect
from fwunit.ip import IP, IPSet
import logging
from fwunit.types import Rule
from fwunit.common import simplify_rules
from collections import namedtuple

logger = logging.getLogger(__name__)

Subnet = namedtuple('Subnet', ['cidr_block', 'name', 'dynamic'])
SecurityGroupId = namedtuple('SecurityGroupId', ['id', 'region'])


def get_rules(regions, dynamic_subnets):
    if not regions:
        logger.info("Getting all regions")
        regions = aws.all_regions()

    logger.info("collecting subnets")
    subnets = []
    for id, subnet in aws.get_all_subnets(regions).iteritems():
        name = subnet.tags.get('Name', id)
        dynamic = name in dynamic_subnets or id in dynamic_subnets
        subnet = Subnet(
            cidr_block=IP(subnet.cidr_block), name=name, dynamic=dynamic)
        subnets.append(subnet)

    logger.info("collecting dynamic subnet IP ranges")
    dynamic_ipsets = {}
    for subnet in subnets:
        if subnet.dynamic:
            ipset = dynamic_ipsets.get(subnet.name, IPSet([]))
            ipset += IPSet([subnet.cidr_block])
            dynamic_ipsets[subnet.name] = ipset

    # sort by IP subnet, so we can use a binary search
    logger.info("sorting subnets by IP")
    subnets.sort(key=lambda s: s.cidr_block)
    _subnet_blocks = [s.cidr_block for s in subnets]

    def subnet_by_ip(ip):
        i = bisect.bisect_right(_subnet_blocks, ip)
        if i and ip in _subnet_blocks[i - 1]:
            return subnets[i - 1]

    logger.info("examining instances")
    sgs_by_dynamic_subnet = {}
    sgs_by_instance = {}
    for id, instance in aws.get_all_instances(regions).iteritems():
        if instance.state == 'terminated':
            continue  # who cares
        if not instance.private_ip_address:
            logger.debug(
                "ignoring instance with no private_ip_address: %s, tags %r",
                instance.id, instance.tags)
            continue
        ip = IP(instance.private_ip_address)
        subnet = subnet_by_ip(ip)
        if not subnet:
            logger.debug(
                "ignoring instance with no matching subnet for %s: %s, tags %r",
                ip, instance.id, instance.tags)
            continue
        if subnet.dynamic:
            sgs = sgs_by_dynamic_subnet.setdefault(subnet.name, set())
        else:
            inst_name = instance.tags.get('Name', instance.id)
            sgs = set()
            sgs_by_instance[inst_name] = [ip, sgs]
        sgs.update(SecurityGroupId(g.id, instance.region.name)
                   for g in instance.groups)

    rules = []

    def make_rules(name, sgid, dst):
        sg = aws.get_security_group(sgid)
        if not sg:
            logger.warning(
                "No such security group %s in %s", sgid.sgid, sgid.region)
            return
        for sgrule in sg.rules:
            for grant in sgrule.grants:
                if not grant.cidr_ip:
                    # TODO: change this
                    logger.warning(
                        "fwunit does not support grants to other SGs (found in %s)", sg.id)
                    continue
                src = IPSet([IP(grant.cidr_ip)])
                rules.append(Rule(
                    src=src, dst=dst, app=str(sgrule),
                    name="{}/sg={}".format(name, sg.name)))

    logger.info("writing rules for dynamic subnets")
    for subnet_name, sgids in sgs_by_dynamic_subnet.iteritems():
        dst = dynamic_ipsets[subnet_name]
        logger.debug(" subnet %s, %s", subnet_name, dst)
        for sgid in sgids:
            make_rules('subnet=' + subnet_name, sgid, dst)

    logger.info("writing rules for instance in per-host subnets")
    for inst_name, info in sgs_by_instance.iteritems():
        ip, sgids = info
        logger.debug(" instance %s at %s", inst_name, ip)
        dst = IPSet([ip])
        for sgid in sgids:
            make_rules('per-host', sgid, dst)

    rules = simplify_rules(rules)
    return rules
