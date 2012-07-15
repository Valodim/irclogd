
from twisted.internet import reactor, protocol

class UdpInput(protocol.DatagramProtocol):
    name = "udp"

    def __init__(self, user, port, params):
        self.user = user
        self.port = port
        self.acceptedHosts = None

        if len(params) > 0:
            self.acceptedHosts = params

    def startProtocol(self):
        self.user.notice("Started listening on UDP: " + str(self.port))
        if self.acceptedHosts is not None:
            self.user.notice("Accepted hosts: " + ', '.join(self.acceptedHosts))

    def stopProtocol(self):
        self.user.notice("Stopped listening on UDP: " + str(self.port))

    def datagramReceived(self, data, (host, port)):
        if host not in self.acceptedHosts:
            return

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
        raise Exception("Udp input requires one numeric port argument")
    else:
        proto = UdpInput(channel, port, params[1:])
        reactor.listenUDP(port, proto)
        return proto
