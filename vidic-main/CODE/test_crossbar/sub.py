from os import environ

import os
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks

from autobahn.twisted.wamp import ApplicationSession, ApplicationRunner


class ClientSession(ApplicationSession):
    """
    An application component that subscribes and receives events, and
    stop after having received 5 events.
    """

    @inlineCallbacks
    def onJoin(self, details):
        print("session attached")
        sub = yield self.subscribe(self.on_event, '1111.1234')
        print("Subscribed to com.myapp.hello with {}".format(sub.id))

    def on_event(self, i):
        print("Got event: {}".format(i))
        # self.config.extra for configuration, etc. (see [A])
        self.publish('1111.1234', 'Hello, world!')


    def onDisconnect(self):
        print("disconnected")
        if reactor.running:
            reactor.stop()


if __name__ == '__main__':
    url = os.environ.get('CBURL', 'ws://192.168.1.52:8080/ws')
    realm = os.environ.get('CBREALM', 'realm1')

    # any extra info we want to forward to our ClientSession (in self.config.extra)
    extra=dict(
        max_events=5,  # [A] pass in additional configuration
    )
    runner = ApplicationRunner(url=url, realm=realm, extra=extra)
    runner.run(ClientSession, auto_reconnect=True)