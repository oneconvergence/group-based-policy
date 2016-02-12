from wsme import types as wtypes
from wsmeext import pecan as wsme_pecan
from pecan import rest

from pecan import expose

import firewall


class V1Controller(rest.RestController):

    fw = firewall.FwaasController()

    @wsme_pecan.wsexpose(wtypes.text)
    def get(self):
        # TODO(blogan): decide what exactly should be here, if anything
        return {'versions': [{'status': 'CURRENT',
                              'updated': '2014-12-11T00:00:00Z',
                              'id': 'v1'}]}
