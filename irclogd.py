#!/usr/bin/env python

from twisted.words.protocols import irc
from twisted.internet import reactor, protocol

import input.udp

class Channel:
    channelTypes = [ 'udp', 'fifo' ]

    def __init__(self, name, key = None):
        self.name = name

        print "Creating channel:", name

    # reply when a user joins this channel
    def join(self, server):
        self.topic(server)
        self.names(server)
        # self.msg(server, "Type help for a list of channel commands!")

    def part(self, server):
        pass

    def mode(self, server):
        server.sendMessage(irc.RPL_CHANNELMODEIS, self.name, "", "")

    def topic(self, server):
        server.sendMessage(irc.RPL_TOPIC, self.name, irc.lowQuote("topic time!"))

    def names(self, server):
        server.sendMessage(irc.RPL_NAMREPLY, self.name, irc.lowQuote(server.nick))
        server.sendMessage(irc.RPL_ENDOFNAMES, self.name, irc.lowQuote("End of /NAMES list"))

    def msg(self, server, msg):
        server.sendMessage('PRIVMSG', irc.lowQuote(msg), frm=self.name)

    def cmd(self, command):
        print 'cmd to chan', command

    def cmd_type(self, command):
        pass

class IrclogdServer(irc.IRC):

    def dataReceived(self, data):
        print data
        irc.IRC.dataReceived(self, data)

    def connectionMade(self):
        irc.IRC.connectionMade(self)
        self.channels = { }

    def sendMessage(self, command, *parameter_list, **kwargs):

        # add nick to param list
        if 'frm' not in kwargs:
            parameter_list = [self.nick] + list(parameter_list)
        else:
            parameter_list = [kwargs['frm']] + list(parameter_list)

        if 'prefix' not in kwargs:
            kwargs['prefix'] = self.hostname

        # prefix last param with a :
        if len(parameter_list) > 0:
            parameter_list[-1] = ":" + parameter_list[-1]

        print command, parameter_list

        # forwad to parent method
        return irc.IRC.sendMessage(self, command, *parameter_list, **kwargs)

    def irc_MODE(self, prefix, params):
        if params[0] not in self.channels:
            self.sendMessage(irc.ERR_NOTONCHANNEL)
            return

        self.channels[params[0]].mode(self)

    def irc_TOPIC(self, prefix, params):
        if params[0] not in self.channels:
            self.sendMessage(irc.ERR_NOTONCHANNEL)
            return

        self.channels[params[0]].topic(self)

    def irc_NAMES(self, prefix, params):
        if params[0] not in self.channels:
            self.sendMessage(irc.ERR_NOTONCHANNEL)
            return

        self.channels[params[0]].names(self)

    def irc_PRIVMSG(self, prefix, params):
        if params[0] not in self.channels:
            self.sendMessage(irc.ERR_CANNOTSENDTOCHAN)
            return

        self.channels[params[0]].cmd(params[1:])

    def irc_USER(self, prefix, params):
        self.user = params
        self.sendMessage(irc.RPL_MOTDSTART, "- irclogd Message of the day -")
        self.sendMessage(irc.RPL_MOTD, "what's up?")
        self.sendMessage(irc.RPL_ENDOFMOTD, "End of /MOTD command")

    def irc_JOIN(self, prefix, params):
        if params[0][0] != "&":
            self.sendMessage(irc.ERR_NOSUCHCHANNEL)
            return

        if params[0] not in self.channels:
            c = Channel(params[0])
            self.channels[params[0]] = c
            c.join(self)

    def irc_PART(self, prefix, params):
        if params[0][0] != "&":
            self.sendMessage(irc.ERR_NOSUCHCHANNEL)
            return

        if params[0] in self.channels:
            self.channels[params[0]].part(self)
            del self.channels[params[0]]

    def irc_PING(self, prefix, params):
        self.sendMessage("PONG", params)

    def irc_PONG(self, prefix, params):
        pass

    def irc_NICK(self, prefix, params):
        self.nick = params[0]

    def irc_QUIT(self, prefix, params):
        self.sendMessage("QUIT", *params)

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
