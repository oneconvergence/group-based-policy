import unittest
import socket
import sys
from multiprocessing import Process
from multiprocessing import Queue
import multiprocessing as multiprocessing
import time
import eventlet
eventlet.monkey_patch()
from eventlet import event
from eventlet import greenpool
from eventlet import greenthread
import os
import threading
import signal

import proxy


count = 0
rxcount = 0
txcount = 0
connection_count = 0


class TcpServer():

    def __init__(self, server_address):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_address = server_address
        print >>sys.stderr, 'starting up the TCP server on %s port %s' % self.server_address
        self.sock.bind(self.server_address)

    # ideal_max_timeout Test
    def test_one_start(self):
        self.sock.listen(1)
        print >>sys.stderr, '[TCP_Server] Waiting for a connection'
        count = 0
        timer = 0
        connection, client_address = self.sock.accept()
        while True:
            #        while count<50:
            try:
                count += 1
                data = connection.recv(16)
                print>> sys.stderr, '[TCP] Received %s on TCP SERVER from %s"' % (
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
                print>>sys.stderr, msg
        connection.close()

    # ideal_max_timeout Test
    def test_two_start(self):
        self.sock.listen(1)
        print >>sys.stderr, '[TCP_Server] Waiting for a connection'
        count = 0
        connection, client_address = self.sock.accept()

        while count < 20:
            try:
                count += 1
                data = connection.recv(16)
                print>> sys.stderr, '[TCP] Received %s on TCP SERVER from %s"' % (
                    data, client_address)
                if data:
                    print >> sys.stderr, '[TCP] sending back to the Unix client'
                    connection.sendall(data)
            except socket.error, msg:
                print>>sys.stderr, msg
                cinnection.close()
                sys.exit(0)

        connection.close()

    # def mutiple connection test
    def test_three_start(self):
        self.sock.listen(1)
        print >>sys.stderr, '[TCP]waiting for a connection'
        count = 0

        while True:
            connection, client_address = self.sock.accept()
            count += 1
            try:
                data = connection.recv(16)
                print>> sys.stderr, '[TCP]Received "%s "' % data
                if data:
                    print >> sys.stderr, '[TCP]sending back to the Unix client'
                    connection.sendall(data)
                # Shutting Down the TCP server after 100 connection accepted
                if count == 10:
                    break
            except socket.error, msg:
                print>>sys.stderr, msg
                connection.close()
        connection.close()


# Class to start the Config Proxy
class ConfProxy():

    def proxyStart():
        conf = proxy.Configuration('proxy.ini')
        proxy.Proxy(conf).start()


# Class to create Unix Cliets
class UnixClient():

    def single_unix_client(self):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_address = '/tmp/uds_socket'
        try:
            sock.connect(server_address)
            print'Connected socekt %s to server %s' % (sock, server_address)
        except socket.error, msg:
            print >>sys.stderr, msg
            return 0
        try:
            count = 0
            while True:
                count += 1
                if count == 2:
                    time.sleep(40)
                message = "Hi count " + str(count)
                print "[Unix]Sending Message %s to %s" % (message, sock)
                sock.sendall(message)
                data = sock.recv(100)
                print"[Unix] Received mesage from TCP : %s from %s" % (data, sock)
        except socket.error, msg:
            print>>sys.stderr, msg
            return 1
        finally:
            print "closing %s socket" % sock
            sock.close()

    def unix_client_msg_flooding(self):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server_address = '/tmp/uds_socket'
        try:
            sock.connect(server_address)
            print'Connected socekt %s to server %s' % (sock, server_address)
        except socket.error, msg:
            print >>sys.stderr, msg
            return 0
        try:
            while True:
                time.sleep(.1)
                message = "Hi count " + str(count)
                print "[Unix]Sending Message %s to %s" % (message, sock)
                sock.sendall(message)
                data = sock.recv(100)
                print"[Unix] Received mesage from TCP : %s from %s" % (data, sock)
        except socket.error, msg:
            print>>sys.stderr, msg
            return 1
        finally:
            print "closing %s socket" % sock
            sock.close()

    def multiple_unix_connections(self, arg, **kwargs):
        # Create a UDS socket
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        # Connect the socket to the port where the server is listening
        server_address = '/tmp/uds_socket'
        global connection_count
        try:
            sock.connect(server_address)
            print '[Unix]Connected socket (%s) to (%s)' % (sock, server_address)
            connection_count += 1
            print '[Unix] Incremeted connection cout %s' % (connection_count)
        except socket.error, msg:
            print >>sys.stderr, msg
            sys.exit(1)
        try:
            # Send data
            global txcount
            txcount += 1
            message = 'Hi'
            # print >>sys.stderr, 'sending "%s"' % message
            print '[Unix]Sending message (%s) to (%s) count (%d)' % (
                message, sock, txcount)
            sock.sendall(message)

            amount_received = 0
            amount_expected = len(message)

            recvd = ""
            while amount_received < amount_expected:
                data = sock.recv(50)
                amount_received += len(data)
                recvd += data
            global rxcount
            rxcount += 1
            print '[Unix]Recieved message (%s) from (%s) count (%d)' % (
                message, sock, rxcount)
        except socket.error, msg:
            print>>sys.stderr, msg
            connection_count -= 1
            print'[Unix] Decremented Connection Count %s' % (connection_count)
            sock.close()

            # print >>sys.stderr, 'closing socket'
        print '[Unix]Closing socket (%s)' % (sock)
        print'[Unix] Decremented Connection Count %s' % (connection_count)
        connection_count -= 1
        sock.close()


# to start mutiple clients with mmutiple treading
def _thread_done(gt, *args, **kwargs):
    kwargs['pool'].thread_done(kwargs['thread'])


class Thread(object):

    def __init__(self, thread, pool):
        self.thread = thread
        self.thread.link(_thread_done, pool=pool, thread=self)

    def stop(self):
        self.thread.kill()

    def wait(self):
        return self.thread.wait()

    def link(self, func, *args, **kwargs):
        self.thread.link(func, *args, **kwargs)


class ThreadPool(object):

    def __init__(self, thread_pool_size=10):
        self.pool = greenpool.GreenPool(thread_pool_size)
        self.threads = []

    def dispatch(self, callback, *args, **kwargs):
        gt = self.pool.spawn(callback, *args, **kwargs)
        th = Thread(gt, self)
        self.threads.append(th)
        return th

    def thread_done(self, thread):
        self.threads.remove(thread)

    def stop(self):
        current = greenthread.getcurrent()
        # Iterate over a copy of self.threads so thread_done doesn't
        # modify the list while we're iterating
        for x in self.threads[:]:
            if x is current:
                # don't kill the current thread.
                continue
            try:
                x.stop()
            except Exception as ex:
                print ex

    def wait(self):
        current = greenthread.getcurrent()

        # Iterate over a copy of self.threads so thread_done doesn't
        # modify the list while we're iterating
        for x in self.threads[:]:
            if x is current:
                continue
            try:
                x.wait()
            except eventlet.greenlet.GreenletExit:
                pass
            except Exception as ex:
                print ex

# method to start mutiple connections


def mutilpe_unix_client_start():
    tpool = ThreadPool(10)
    for i in range(200):
        tpool.dispatch(UnixClient().multiple_unix_connections, None)
        time.sleep(0.2)

# class to start conf proxy


class ProxyStart():

    def __init__(self):
        self.conf = proxy.Configuration('proxy.ini')

    def run(self, server):
        self.conf.rest_server_port = server
        proxy.Proxy(self.conf).start()


class TestConfProxy(unittest.TestCase):

    def test_ideal_max_timeout(self):
        return_val = 0
        server_address = ('0.0.0.0', 5674)
        tcp_process = Process(target=TcpServer(server_address).test_one_start)
        tcp_process.demon = True
        tcp_process.start()
        time.sleep(2)

        proxy_obj = Process(target=ProxyStart().run, args=(server_address[1],))
        proxy_obj.start()
        time.sleep(5)

        return_val = UnixClient().single_unix_client()

        tcp_process.join()
        os.kill(proxy_obj.pid, signal.SIGKILL)

        self.assertEqual(return_val, 1)

    def test_connection_broken(self):
        return_val = 0
        server_address = ('0.0.0.0', 5675)
        tcp_process = Process(target=TcpServer(server_address).test_two_start)
        tcp_process.demon = True
        tcp_process.start()
        time.sleep(2)

        proxy_obj = Process(target=ProxyStart().run, args=(server_address[1],))
        proxy_obj.start()
        time.sleep(5)

        return_val = UnixClient().unix_client_msg_flooding()

        tcp_process.join()
        os.kill(proxy_obj.pid, signal.SIGKILL)

        self.assertEqual(return_val, 1)

    """
    def test_mutliple_connections(self):
        server_address = ('0.0.0.0', 5676)
        tcp_process = Process(target=TcpServer(
            server_address).test_three_start)
        tcp_process.demon = True
        tcp_process.start()
        time.sleep(1)

        proxy_obj = Process(target=ProxyStart().run, args=(server_address[1],))
        proxy_obj.start()
        time.sleep(5)

        return_val = mutilpe_unix_client_start()
        tcp_process.join()
        os.kill(proxy_obj.pid, signal.SIGKILL)

        self.assertEqual(connection_count, 0)
    """


if __name__ == '__main__':
    unittest.main()
