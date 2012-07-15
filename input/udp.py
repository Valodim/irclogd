from twisted.internet import reactor, protocol

class UdpInput(protocol.DatagramProtocol):

    def __init__(self, channel, port, params):
        self.channel = channel
        self.port = port

    def startProtocol(self):
        self.channel.msg("Started listening on UDP: " + str(self.port))

    def stopProtocol(self):
        self.channel.msg("Stopped listening on UDP: " + str(self.port))

    def datagramReceived(self, data, (host, port)):
        lines = data.split("\n")
        for l in lines:
            if len(l) > 0:
                self.channel.content(l)

def UdpInputFactory(channel, params):
    port = int(params[0])
    proto = UdpInput(channel, port, params[1:])
    reactor.listenUDP(port, proto)
    return proto
