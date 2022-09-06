# from autobahn.twisted.wamp import ApplicationSession
from multiprocessing import Process
import time
from autobahn.asyncio.wamp import ApplicationSession, ApplicationRunner
import os


class SocketCrossbar(ApplicationSession):

    def onJoin(self, details):

        # 1. subscribe to a topic so we receive events
        def on_event(msg):
            print("Got event: {}".format(msg))

        self.subscribe(on_event, '1111.1234')

        # 2. publish an event to a topic
        self.publish('1111.1234', 'Hello, world!')

        # # 3. register a procedure for remote calling
        # def add2(x, y):
        #     return x + y

        # self.register(add2, 'com.myapp.add2')

        # 4. call a remote procedure
        # res = yield self.call('com.myapp.add2', 2, 3)
        # print("Got result: {}".format(res))

def printear():
    while True:
        print('prueba')
        time.sleep(2)

if __name__ == '__main__':
    url = os.environ.get('CBURL', 'ws://192.168.1.52:8080/ws')
    realm = os.environ.get('CBREALM', 'realm1')

    # any extra info we want to forward to our ClientSession (in self.config.extra)
    extra=dict(
        max_events=5,  # [A] pass in additional configuration
    )
    p = Process(target=printear)
    p.start()
    runner = ApplicationRunner(url=url, realm=realm, extra=extra)
    runner.run(SocketCrossbar)