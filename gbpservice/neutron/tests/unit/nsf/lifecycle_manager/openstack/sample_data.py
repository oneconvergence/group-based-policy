import unittest


class SampleData(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(SampleData, self).__init__(*args, **kwargs)
        self.AUTH_TOKEN = '6db9dfa4d29d442eb2b23811ad4b3a6d'
        self.AUTH_URL = 'http://localhost:5000/v2.0/'
        self.ENDPOINT_URL = 'http://localhost:9696/'
        self.FLAVOR_NAME = 'm1.tiny'
        self.IMAGE_NAME = 'cirros-0.3.4-x86_64-uec'
        self.IMAGE_ID = '7022c5a4-ef0c-4f7e-a2c8-b7f5b36c9086'
        self.INSTANCE_ID = '60c7ebc4-aa70-4ee6-aad6-41e99d27ceec'
        self.PASSWORD = 'admin_pass'
        self.PORT_ID = '16fa0e95-3c7a-4dd6-87bd-c76b14f9eac2'
        self.TENANT_ID = '384757095ca4495683c7f34ae077f8c0'
        self.TENANT_NAME = 'admin'
        self.USERNAME = 'admin'
