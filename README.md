Unit Tests for your Network
===========================

Any developer worth their salt tests their software.  The benefits are many:

 * Exercise the code

 * Reduce ambiguity by stating the desired behaviors twice (in the
   implementation, in the tests, and maybe even a third time in the
   documentation)

 * Enable code refactoring without changing expected behavior

With `fwunit`, you can do the same for security policies on your network.

Principle of Operation
----------------------

Testing policies is a two-part operation: first fetch and process the data from
all of the applicable devices, constructing a set of *rules*.  Then run the
tests against the rules.

This package handles the first part entirely, and provides a set of utility
functions you can use in your tests.  You can write tests using whatever Python
testing framework you like.  We recommend [nose](http://nose.readthedocs.org/).

Supported Policy Types
======================

`fwunit` can read policies from:

 * [`srx`] Juniper SRXes, using manually downloaded XML files
 * [`aws`] Amazon EC2 security groups and VPC subnets

Installation
============

To install, set up a [Python virtualenv](https://virtualenv.pypa.io/) and then run

    pip install fwunit[srx,aws]

where the bit in brackets lists the systems you'd like to process, from the section above.

Processing Policies
===================

The `fwunit` command processes a YAML-formatted configuration file describing a
set of "sources" of rule data.  Each top-level key describes a source, and must
have a `type` field giving the type of data to be read -- see "Supported
Systems", above.  Each must also have an `output` field giving the filename to
write the generated rules to (relative to the configuration file).

The source may optionally have a `require` field giving a list of other sources
which should be processed first.

Any additional fields are passed to the policy-type plugin.

Example:

```
fw1_releng:
    type: srx
    output: fw1_releng.pkl
    security-policies-xml: fw1_releng_scl3_show_security_policies.xml
    route-xml: fw1_releng_scl3_show_route.xml
    configuration-security-zones-xml: fw1_releng_scl3_show_configuration_security_zones.xml

aws_releng:
    type: aws
    output: aws_releng.pkl
    dynamic_subnets: [build, test, try, build.servo, bb]
    regions: [us-east-1, us-west-1, us-west-2]
```

You can pass one or more source names to `fwunit` to only process those sources.

Application Maps
----------------

Each policy type comes with its own way of naming applications: strings,
protocol/port numbers, etc.

An "application map" is used to map these type-specific names to common names.
This is invaluable if you are combining policies from multiple types, e.g., AWS
and SRX.

To set this up, add an `application-map` key to the source configuration, with
a mapping from type name to common name.  For example:

```
mysource:
    ...
    application-map:
        junos-ssh: ssh
        junos-http: http
        junos-https: https
```

Note that you *cannot* combine multiple applications into one using an
application map, as this might result in overlapping rules.

Juniper SRX
-----------

This source type uses SSH with a username and password to connect to a Juniper SRX firewall.
It only runs 'show' commands, so read-only access is adequate.

The configuration looks like this:

```
myfirewall:
    type: srx
    output: myfirewall.pkl
    firewall: fw1.releng.scl3.mozilla.com
    ssh_username: fwunit
    ssh_password: sekr!t
```

The `firewall` config gives a hostname (or IP) of the firewall that accepts SSH connections.
`ssh_username` and `ssh_password` are the credentials for the account.

The process of downloading and processing policies can be very slow, depending on the complexity of your policies.

### Assumptions ###

This processing makes the following assumptions about your network

  * Rule IPs are limited by the to- and from-zones of the original policy, so
    given a "from any" policy with from-zone ABC, the resulting rule's `src`
    will be ABC's IP space, not 0.0.0.0/0.  Zone spaces are determined from the
    route table, and thus assume symmetrical forwarding.

  * All directly-connected networks are considered to permit all traffic within
    those networks, on the assumption that the network is an open L2 subnet.

  * Policies allowing application "any" are expanded to include every
    application mentioned in any policy.

Amazon EC2 Security Groups
--------------------------

Set up your `~/.boto` with an account that has access to EC2 and VPC
administrative information.

In your source configuration, include `dynamic_subnets` listing the names or
id's of all dynamic subnets (see below).  Also include a `regions` field
listing the regions in which you have hosts.

You can include the credentials for an IAM user in the configuration.  If this
is omitted, boto's normal credential search process will apply, including
searching `~/.boto` and instance role credentials.

Example:
```
my_aws_stuff:
    type: aws
    output: my_aws_stuff.pkl
    dynamic_subnets: [workers]
    regions: [us-east-1, us-west-1]
    credentials:
        access_key: "ACCESS KEY"
        secret_key: "SECRET KEY"
```

### Security Policy ###

The user accessing Amazon should have the following security policy:

    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "ec2:DescribeInstances",
                    "ec2:DescribeSubnets",
                    "ec2:DescribeSecurityGroups"
                ],
                "Resource": "*"
            }
        ]
    }

### Assumptions ###

This processing makes some assumptions about your EC2 layout.  These worked for
us in Mozilla Releng, but may not work for you.

 * Network ACLs are not in use

 * All traffic is contained in subnets in one or more VPCs.

 * Each subnet is either *per-host* or *dynamic*, as described below.

 * All traffic from unoccupied IPs in per-host subnets is implicitly permitted.

 * Subnets with the same name are configured identically.  Such subnets are
   often configured to achieve AZ/region separation.

The Release Engineering AWS environment contains two types of instances, which
always appear in different subnets.  Long-lived instances sit at a single IP
for a long time, acting like traditional servers.  The subnets holding such
instances are considered "per-host" subnets, and the destination IPs for
`fwunit` rules are determined by examining the IP addresses and security groups
of the instances in the subnets.  All traffic to IPs not assigned to an
instance is implicitly denied.

The instances that perform build, test, and release tasks are transient,
created and destroyed as economics and load warrant.  Subnets containing such
instances are considered "dynamic", and a security group that applies to any
instance in the subnet is assumed to apply to the subnet's entire CIDR block.
This means that these subnets must contain at least one active host.

Policy Combiner
---------------

A large organization will have multiple policy sources, perhaps in different
regions or of different types.  Before you can write tests and reason about the
overall flows, these must be combined into a single rule set.

In most cases, each policy source has a set of IP addresses for which it is
responsible for controlling access.  It controls both incoming and outgoing
traffic in this space, but does not see traffic between addresses *not* in this
space.

To combine policy sources, create a `combine` source, requiring the sources it
combines.  Give the IP space for each source, and specify an output file:

```
enterprise:
    type: combine
    require: [dca, nyc, ord]
    address_spaces:
        dca: [10.10.0.0/16, 10.15.0.0/14]
        ord: 192.168.0.0/24
        nyc: 172.16.1.0/24
```

### Assumptions ###

* Traffic is only filtered at the source and destination

* Any traffic beteween IPs not in any defined address space is forbidden (more
  likely, such traffic is not interesting)

Writing Tests
=============

*To Be Written* - see tests.py for now.  Example:

```python
from fwunit.ip import IP, IPSet
from fwunit.tests import Rules

fw1 = Rules('rules.pkl')

internal_network = IPSet([IP('192.168.1.0/24'), IP('192.168.13.0/24')])

puppetmasters = IPSet([IP(ip) for ip in
    '192.168.13.45',
    '192.168.13.50',
])

def test_puppetmaster_access():
    for app in 'puppet', 'junos-http', 'junos-https':
        fw1.assertPermits(internal_network, puppetmasters, app)
```

Querying
========

Aside from writing unit tests, you can query against a rule source with
`fwunit-query`.

For example:

```
fwunit-query enterprise permitted 10.10.1.1 192.168.1.1 ssh
Flow permitted
```

See the script's `--help` for more detail.

Implementation Notes
====================

IP Objects
----------

This tool uses [IPy](https://pypi.python.org/pypi/IPy/) to handle IP addresses,
ranges, and sets.  However, it extends that functionality to include some
additional methods for `IPSet`\s as well as an `IPPairs` class to efficiently
represent sets of IP pairs.

All of these classes can be imported from ``fwunit.ip``.

Rules
-----

The output of the processing step is a pickled list of Rule objects.

A Rule has `src` and `dst` attributes, IPSets consisting of the source and
destination addresses to which it applies, and `app`, the name of the traffic
type allowed.  It also has a `name` attribute indicating where it came from
(e.g., the SRX policy name).

The rules are normalized as follows (and this is what consumes most of the time in processing):

  * For a given source and destination IP and application, exactly 0 or 1 rules
    match; stated differently, there's no need to consider rules in order.

  * If traffic matches a rule, it is permitted.  If no rule matches, it is denied.
