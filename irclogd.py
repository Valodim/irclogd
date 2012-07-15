#!/usr/bin/env python

from twisted.words.protocols import irc
from twisted.internet import reactor, protocol

# import input.udp

class IrclogdServer(irc.IRC):

    # def dataReceived(self, data):
        # print data
        # irc.IRC.dataReceived(self, data)

    def sendMessage(self, command, *parameter_list, **prefix):

        # add nick to param list
        parameter_list = [self.nick] + list(parameter_list)

        if 'prefix' not in prefix:
            prefix['prefix'] = self.hostname

        # forwad to parent method
        return irc.IRC.sendMessage(self, command, *parameter_list, **prefix)

    def irc_USER(self, prefix, params):
        self.user = params
        self.sendMessage(irc.RPL_MOTDSTART, "- irclogd Message of the day -")
        self.sendMessage(irc.RPL_MOTD, "what's up?")
        self.sendMessage(irc.RPL_ENDOFMOTD, "End of /MOTD command")

    def irc_PING(self, prefix, params):
        self.sendMessage("PONG", params)

    def irc_PONG(self, prefix, params):
        pass

    def irc_NICK(self, prefix, params):
        self.nick = params[0]

    def irc_QUIT(self, prefix, params):
        self.sendMessage("QUIT", "")

    def irc_unknown(self, prefix, command, params):
        print "unkown msg", prefix, command, params

if __name__ == "__main__":
    factory = protocol.Factory()
    factory.protocol = IrclogdServer

    # All incoming clients share the same connections dict
    factory.connections = {}

    reactor.listenTCP(6667, factory)
    reactor.run()

### The End ###
