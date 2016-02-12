from oslo_config import cfg

OPTS = [
    cfg.IntOpt(
        'workers',
        default=1,
        help=_('#of workers to create.')
    ),
    cfg.StrOpt(
        'RpcLoadBalancer',
        default='StickyRoundRobin',
        choices=['RoundRobin', 'StickyRoundRobin'],
        help=_('Check sc/core/lb.py for supported rpc lb algos')
    ),
    cfg.StrOpt(
        'modules_dir',
        default='gbpservice.neutron.nsf.core.test',
        help=_('Modules path to import ')
    ),
    cfg.IntOpt(
        'periodic_interval',
        default=10,
        help=_('Seconds between periodic task runs')
    ),
    cfg.IntOpt(
        'reportstate_interval',
        default=10,
        help=_('Seconds between periodic task runs')
    )
]
