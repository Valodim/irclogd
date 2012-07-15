from twisted.internet import reactor, protocol

class UdpInput(protocol.DatagramProtocol):
    name = "udp"

    def __init__(self, user, port, params):
        self.user = user
        self.port = port

    def startProtocol(self):
        self.user.notice("Started listening on UDP: " + str(self.port))

    def stopProtocol(self):
        self.user.notice("Stopped listening on UDP: " + str(self.port))

    def datagramReceived(self, data, (host, port)):
        lines = data.split("\n")
        for l in lines:
            if len(l) > 0:
                self.user.msg(l)

    def destroy(self):
        self.transport.loseConnection()

def UdpInputFactory(channel, params):
    try:
        port = int(params[0])
    except:
        raise Exception("Udp input requires exactly one numeric port argument")
    else:
        proto = UdpInput(channel, port, params[1:])
        reactor.listenUDP(port, proto)
        return proto
