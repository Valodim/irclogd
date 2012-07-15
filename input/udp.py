
from twisted.internet import reactor, protocol

class UdpInput(protocol.DatagramProtocol):
    """
        This input class listens on a given udp port, reporting all received
        messages.

        If a list of hosts is given as optional parameter, all messages from
        hosts not on this list will be ignored.
    """
    name = "udp"

    def __init__(self, user, port, params):
        self.user = user
        self.port = port
        self.acceptedHosts = None

        if len(params) > 0:
            self.acceptedHosts = params

    def startProtocol(self):
        self.user.notice("Started listening on UDP port " + str(self.port))
        if self.acceptedHosts is not None:
            self.user.notice("Accepted hosts: " + ', '.join(self.acceptedHosts))

    def stopProtocol(self):
        self.user.notice("Stopped listening on UDP port " + str(self.port))

    def datagramReceived(self, data, (host, port)):
        if self.acceptedHosts is not None and host not in self.acceptedHosts:
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
