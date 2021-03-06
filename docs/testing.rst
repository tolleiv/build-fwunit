Writing Tests
=============

Flow tests are just like software unit tests: they make assertions about the state of the system under test.
In the case of flow tests, that means asserting that traffic can, or cannot, flow between particular systems.

Here's how to write flow tests.

Example
-------

The following might be in a file named `test_puppet.py`.

.. code-block:: python

    from fwunit import TestContext
    from fwunit import IP, IPSet

    tc = TestContext('my-network')

    # hosts

    internal_network = IPSet([IP('192.168.1.0/24'), IP('192.168.13.0/24')])
    external_network = IPSet([IP('0.0.0.0/0')]) - internal_network
    puppetmasters = IPSet([IP(ip) for ip in
        '192.168.13.45',
        '192.168.13.50',
    ])

    # tests

    """
    Puppetmasters serve puppet catalogs and data to clients over 'puppet',
    'http', and 'https'.  All hosts in the internal network should have access.
    """

    def test_puppetmaster_access():
        """The entire internal_network can access the puppet masters."""
        for app in 'puppet', 'http', 'https':
            tc.assertPermits(internal_network, puppetmasters, app)

    def test_puppetmaster_no_other_apps():
        """Access to puppetmasters is limited to puppet, http, and https"""
        tc.assertAllApps(IPSet([IP('0.0.0.0/0')]), puppetmasters,
                          ['puppet', 'http', 'https'])

    def test_puppetmaster_limited():
        """The exteernal networks cannot access the puppet masters."""
        for app in 'puppet', 'http', 'https':
            tc.assertDenies(external_network, puppetmasters, app)

Running this test is as simple as

.. code-block:: none
    
    $ nosetests test_puppet.py

Loading Rules
-------------

Before you can test anything, you'll need to load the rules created with the ``fwunit`` command into memory.
It's safe to do this individually in each test script, as the results are cached.

.. code-block:: python

    from fwunit import TestContext

    tc = TestContext('source-name')

The :py:class:`~fwunit.analysis.testcontext.TestContext` class uses ``fwunit.yaml`` in the current directory to look up the proper source file for the given source name.

IPs and IPSets
--------------

The ``IP`` and ``IPSet`` classes come from `IPy <https://pypi.python.org/pypi/IPy/>`_, with minor changes.

The ``IP`` class represents a single IP or CIDR range::

    from fwunit import IP
    server = IP('10.11.12.33')
    subnet = IP('10.11.12.0/23')

When you need to reason about a non-contiguous set of addresses, you need an ``IPSet``.
This is really just a list of ``IP`` instances, but it will remove duplicates, collapse adjacent IPs, and so on. ::

    from fwunit import IP, IPSet
    db_subnets = IPSet([IP('10.11.12.0/23'), IP('10.12.12.0/23')])

In general, tests expeect ``IPSet``\s, but you can pass ``IP`` instances or even bare strings and they will be converted appropriately.

Tests
-----

Once you have the rules loaded, you can start writing test methods::

    internal_network = IPSet([IP('192.168.1.0/24'), IP('192.168.13.0/24')])

    puppetmasters = IPSet([IP(ip) for ip in
        '192.168.13.45',
        '192.168.13.50',
    ])

    def test_puppetmaster_access():
        for app in 'puppet', 'http', 'https':
            tc.assertPermits(internal_network, puppetmasters, app)

Utility Methods
---------------

The :class:`~fwunit.analysis.testcontext.TestContext` class provides a number of useful functions for testing.
Each method logs verbosely, so test failures should have plenty of data for debugging.

.. py:class:: funit.analysis.testcontext.TestContext(source_name)

    :param source_name: fwunit source from which to load rules

    .. py:method:: assertDenies(src, dst, app)

        :param src: source IPs
        :param dst: destination IPs
        :param apps: application names
        :type apps: list or string

        Assert that traffic is denied from any given source IP to any given destination IP for all given applications.

    .. py:method:: assertPermits(src, dst, apps)

        :param src: source IPs
        :param dst: destination IPs
        :param apps: application names
        :type apps: list or string

        Assert that all given applications are allowed from any given source IP to any given destination IP.

    Note that ``assertDenies`` and ``assertPermits`` are not quite opposites:
    if application traffic is allowed between some IP pairs, but denied between others, then both methods will raise ``AssertionError``.

    .. py:method:: sourcesFor(dst, app, ignore_sources=None)

        :param dst: destination IPs
        :param app: application
        :param ignore_sources: source IPs to ignore

        Return an IPSet with all sources for traffic to any IP in dst on
        application app, ignoring flows from ignore_sources.

        This is useful for assertions of the form "access to X is only allowed from Y and Z".

    .. py:method:: allApps(src, dst, debug=False)

        :param src: source IPs
        :param dst: destination IPs
        :param debug: if True, log the full list of matching flows
        
        Return a set of applications with access form src to dst.

        This is useful for verifying that access between two sets of hosts is limited to a short list of applications.

        Note that if *any* application is allowed from ``src`` to ``dst``, this method will return ``set(['any'])`` rather than enumerating the (infinite) set of allowed applications.

    .. py:method:: assertAllApps(src, dst, apps, debug=False)

        :param src source IPs
        :param dst: destination IPs
        :param apps: expected list of applications
        :param debug: if True, log the full list of matching flows

        Verify that the set of applications with access from any host in ``src`` to any host in ``dst`` is ``apps``.

        This is useful for verifying that other tests have covered all of the open applications.
        The same warning as for :py:meth:`allApps` applies here for rules allowing any application.
