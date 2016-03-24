import unittest
import socket
import sys
from multiprocessing import Process
import multiprocessing as multiprocessing
import time
import os
import threading
import signal
from gbpservice.nfp.proxy_agent.proxy import proxy as proxy
from oslo_log import log as logging

LOG = logging.getLogger(__name__)

count = 0
rxcount = 0
txcount = 0
connection_count = 0
threadLock = threading.Lock()
threads = []

"""
class to start TCP server based on testcase needs
"""


class TcpServer(object):

    def __init__(self, server_address):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_address = server_address
        print >> sys.stderr, '[TCP]starting up the TCP server on %s port %s' % (
            self.server_address)
        self.sock.bind(self.server_address)
        self.count = 0

    def test_one_start(self):
        """
        TCP server for ideal_max_timeout check
        """
        self.sock.listen(1)
        print >> sys.stderr, '[TCP] Waiting for a connection'
        self.count = 0
        timer = 0
        connection, client_address = self.sock.accept()
        while True:
            try:
                self.count += 1
                data = connection.recv(16)
                print>> sys.stderr, '[TCP] Received %s from %s"' % (
                    data, client_address)
                if data:
                    print >> sys.stderr, '[TCP] sending back to the Unix client'
                    connection.sendall(data)
                else:
                    time.sleep(30)
                    timer += 1
                if timer:
                    connection.shutdown(socket.SHUT_RDWR)
                    connection.close()
                    sys.exit(0)
            except socket.error, msg:
                print>> sys.stderr, msg
        connection.close()

    def test_two_start(self):
        """
        TCP server for single connection with multiple messages
        Server is down after receiving 20 messages
        """
        self.sock.listen(1)
        print >> sys.stderr, '[TCP] Waiting for a connection'
        self.count = 0
        connection, client_address = self.sock.accept()

        while self.count < 20:
            try:
                self.count += 1
                data = connection.recv(16)
                print>> sys.stderr, '[TCP] Received %s from %s"' % (
                    data, client_address)
                if data:
                    print >> sys.stderr, '[TCP] sending back to the Unix client'
                    connection.sendall(data)
            except socket.error, msg:
                print>> sys.stderr, msg
                connection.close()
                sys.exit(0)
        connection.close()

    def test_three_start(self):
        """
        TCP server for multiple connections check
        """
        self.sock.listen(100)
        print >>sys.stderr, '[TCP]waiting for a connection'

        while True:
            connection, client_address = self.sock.accept()
            self.count += 1
            try:

                data = connection.recv(16)
                print>> sys.stderr, '[TCP]Received "%s on %s "' % (
                    data, client_address)
                if data:
                    print >> sys.stderr, '[TCP]sending back to the Unix client'
                    connection.sendall(data)
            except socket.error, msg:
                print>> sys.stderr, msg
                connection.close()
        connection.close()


"""
Class to create Unix client based on test case
"""


class UnixClient(object):

    def __init__(self):
        pass

    def single_unix_client(self):
        """
        method to start the single client and send two
        messages with ideal_max_timeout difference.
        """
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_address = '/tmp/uds_socket'
        try:
            sock.connect(server_address)
            print'Connected to proxy'
        except socket.error, msg:
            print >> sys.stderr, msg
            return 0
        try:
            count = 0
            while True:
                count += 1
                if count == 2:
                    # send the second message after some time so
                    # proxy can destroy the connection object
                    time.sleep(40)
                message = "Hi count " + str(count)
                print "[Unix]Sending Message %s" % message
                sock.sendall(message)
                data = sock.recv(100)
                print"[Unix] Received message from TCP : %s" % data
        except socket.error, msg:
            print>> sys.stderr, msg
            return 1
        finally:
            print "[Unix]closing %s socket" % sock
            sock.close()

    def unix_client_msg_flooding(self):
        """
        method to start single unix client and send multiple messages
        """
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_address = '/tmp/uds_socket'
        try:
            sock.connect(server_address)
            print'[Unix]Connected to proxy'
        except socket.error, msg:
            print >> sys.stderr, msg
            return 0
        try:
            count = 0
            while True:
                count += 1
                time.sleep(.1)
                message = "Hi count " + str(count)
                print "[Unix]Sending Message %s" % message
                sock.sendall(message)
                data = sock.recv(100)
                print"[Unix] Received message from TCP : %s" % data
        except socket.error, msg:
            print>> sys.stderr, msg
            return 1
        finally:
            print "[Unix]closing %s socket" % sock
            sock.close()

    def multiple_unix_connections(self):
        """
        method to start the multiple unix clients
        Each connection is started as separate thread
        """
        threadLock.acquire()
        global connection_count
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        # Connect the socket to the port where the server is listening
        server_address = '/tmp/uds_socket'
        try:
            sock.connect(server_address)
            print '[Unix]Connected to proxy'
            connection_count += 1
        except socket.error, msg:
            print >> sys.stderr, msg
            print'[Unix] closing Connection'
            connection_count -= 1
            sock.close()
            threadLock.release()
            return

        count = 0
        while True:
            global txcount
            txcount += 1
            message = 'Hi'
            print '[Unix]Sending message: %s' % message
            try:
                count = +1
                sock.sendall(message)
            except socket.error, msg:
                print >> sys.stderr, msg
                print'[Unix] closing Connection'
                connection_count -= 1
                sock.close()
                threadLock.release()
                return

            try:
                data = sock.recv(50)
                global rxcount
                rxcount += 1
                print '[Unix] Received message %s' % data
            except socket.error, msg:
                print >> sys.stderr, msg
                print'[Unix] closing Connection'
                connection_count -= 1
                sock.close()
                threadLock.release()
                return
                threadLock.release()
                time.sleep(.2)

        print"[Thread %d] Closing " % self.t_id
        connection_count -= 1
        threadLock.release()
        return

"""
Descriptor class for Thread
"""


class TreadStart(threading.Thread):

    def __init__(self, t_id):
        self.t_id = t_id
        threading.Thread.__init__(self)

    def run(self):
        """
        method to create new unix client as with thread
        """
        UnixClient().multiple_unix_connections()


"""
Class to Initiate the Configurator Proxy
"""


class ProxyStart():

    def __init__(self):
        # Need to change with absolute path
        self.path = os.getcwd() + '/proxy.ini'
        self.conf = proxy.Configuration(self.path)

    def run(self, server):
        """
        method to run the proxy server with configurations paramter
        :param server: port address
        """
        self.conf.rest_server_address = server[0]
        self.conf.rest_server_port = server[1]
        proxy.Proxy(self.conf).start()


"""
Unit test class
"""


class TestConfProxy(unittest.TestCase):
    
    def test_ideal_max_timeout(self):
        """
        method to test the ideal_max_timeout is expired of connection
        """
        return_val = 0
        server_address = ('0.0.0.0', 5674)
        tcp_process = Process(target=TcpServer(server_address).test_one_start)
        tcp_process.demon = True
        tcp_process.start()
        time.sleep(2)

        proxy_obj = Process(target=ProxyStart().run, args=(server_address,))
        proxy_obj.start()
        time.sleep(5)

        return_val = UnixClient().single_unix_client()

        tcp_process.join()
        os.kill(proxy_obj.pid, signal.SIGKILL)

        self.assertEqual(return_val, 1)
    
    
    def test_connection_broken(self):
        """
        method to test single connection keep sending messages and
        tcp server is down after recivin some messages
        """

        return_val = 0
        server_address = ('0.0.0.0', 5675)
        tcp_process = Process(target=TcpServer(server_address).test_two_start)
        tcp_process.demon = True
        tcp_process.start()
        time.sleep(2)

        proxy_obj = Process(target=ProxyStart().run, args=(server_address,))
        proxy_obj.start()
        time.sleep(5)

        return_val = UnixClient().unix_client_msg_flooding()

        tcp_process.join()
        os.kill(proxy_obj.pid, signal.SIGKILL)

        self.assertEqual(return_val, 1)

    
    def test_multiple_connections(self):
        """   
        method to test multiple proxy connections
        """
        try:
            server_address = ('0.0.0.0', 5676)
            tcp_process = Process(target=TcpServer(
                server_address).test_three_start)
            tcp_process.demon = True
            tcp_process.start()
            time.sleep(5)

            proxy_obj = Process(target=ProxyStart().run,
                                args=(server_address,))
            proxy_obj.start()
            time.sleep(5)
        except multiprocessing.ProcessError, msg:
            print>> sys.stderr, msg

        for i in range(2):
            t = TreadStart(i)
            threads.append(t)
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        print"Exiting from main thread"

        time.sleep(5)
        os.kill(tcp_process.pid, signal.SIGKILL)
        os.kill(proxy_obj.pid, signal.SIGKILL)

        self.assertEqual(connection_count, 0)
    
    
if __name__ == '__main__':
    unittest.main()
