import stat
import os

from twisted.internet import reactor, protocol

import lib.fifo

class FifoInput(protocol.Protocol):
    name = "fifo"

    def __init__(self, user, path, params):
        self.user = user
        self.path = path

    def connectionMade(self):
        self.user.notice("Reading from fifo: " + self.path)

    def dataReceived(self, data):
        lines = data.split("\n")
        for l in lines:
            if len(l) > 0:
                self.user.msg(l)

    def destroy(self):
        self.transport.loseConnection()

def FifoInputFactory(user, params):

    # need exactly one argument
    if len(params) != 1:
        raise Exception("Fifo input requires exactly one path argument, which must be a valid fifo!")
    path = params[0]

    # does it exist?
    if not os.path.exists(path):
        raise Exception("Path argument does not exist!")
    # is it a fifo?
    if not stat.S_ISFIFO(os.stat(path).st_mode):
        raise Exception("Path argument is not a valid fifo!")

    # ok then, set everything up to read from it
    proto = FifoInput(user, path, params[1:])
    lib.fifo.readFromFIFO(reactor, path, proto)
    return proto
