import mock
import unittest

from gbpservice.nfp.lib import transport as common
from neutron import context as ctx
from neutron.common import rpc as n_rpc
import requests as requests
import json as json

class Map(dict):
    """
    Example:
    m = Map({'first_name': 'Eduardo'}, last_name='Pool', age=24, sports=['Soccer'])
    """
    def __init__(self, *args, **kwargs):
        super(Map, self).__init__(*args, **kwargs)
        for arg in args:
            if isinstance(arg, dict):
                for k, v in arg.iteritems():
                    self[k] = v

        if kwargs:
            for k, v in kwargs.iteritems():
                self[k] = v

    def __getattr__(self, attr):
        return self.get(attr)

    def __setattr__(self, key, value):
        self.__setitem__(key, value)

    def __setitem__(self, key, value):
        super(Map, self).__setitem__(key, value)
        self.__dict__.update({key: value})

    def __delattr__(self, item):
        self.__delitem__(item)

    def __delitem__(self, key):
        super(Map, self).__delitem__(key)
        del self.__dict__[key]




class TestContext:

    def get_context(self):
        try:
            return ctx.Context('some_user', 'some_tenant')
        except:
            return ctx.Context('some_user', 'some_tenant')
    
    def get_test_context(self):
        variables = {}
        variables['context'] = self.get_context()
        variables['body'] = {'config':[{'kwargs':{} }]}
        variables['method_type'] = 'CREATE'
        variables['device_config'] = True
        return variables

class CommonLibarayTest(unittest.TestCase):
        

    def _cast(self, context, method, **kwargs):
            #print("cast method:Success")
            return

    def _call(self, context, method, **kwargs):
            #print("call method:Success")
            return []
    
    def _get(self, path):
        print("Get Method :Success")
        class MockResponse(object):
            def __init__(self):
                self.content = {'success' : '200'}
        return MockResponse()

    def _post(self, path, body, method_type):
        #print("Post Method : Success")
        return (200, '')


    def test_rpc_send_request_to_configurator(self):
        with mock.patch('oslo_messaging.rpc.client._CallContext.cast') as cast:
            cast.side_effect = self._cast

            test_context = TestContext().get_test_context()
            conf = Map( backend='rpc' , RPC=Map(topic='topic'))

            common.send_request_to_configurator(conf,
                                                test_context['context'],
                                                test_context['body'],
                                                test_context['method_type'],
                                                test_context['device_config'])
        

    def test_rpc_get_response_from_configurator(self):
        with mock.patch('oslo_messaging.rpc.client._CallContext.call') as call:
            call.side_effect = self._call

            test_context = TestContext().get_test_context()
            conf = Map( backend='rpc' , RPC=Map(topic='topic'))

            resp = common.get_response_from_configurator(conf)
    

    
    def test_rest_send_request_to_configurator(self):
        
        with mock.patch.object(common.RestApi, 'post') as mock_post:
            mock_post.side_effect = self._post

            test_context = TestContext().get_test_context()
            conf = mp =  Map(backend='rest', RPC = Map(topic='topic'),
                             REST = Map(rest_server_ip='0.0.0.0', rest_server_port=5672))

            common.send_request_to_configurator(conf,
                                                test_context['context'],
                                                test_context['body'],
                                                test_context['method_type'],
                                                test_context['device_config'])
   
    def test_rest_get_response_from_configurator(self):
        
        with mock.patch.object(common.RestApi, 'get') as mock_get,\
        mock.patch.object(json, 'loads') as mock_loads:
            mock_get.side_effect = self._get
            mock_loads.return_value = True
        

            test_context = TestContext().get_test_context()
            conf = mp =  Map(backend='rest', RPC = Map(topic='topic'),
                             REST = Map(rest_server_ip='0.0.0.0', rest_server_port=5672))

            resp = common.get_response_from_configurator(conf)

if __name__ == '__main__':
     unittest.main()
