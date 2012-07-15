#!/usr/bin/env python

import sys

from twisted.words.protocols import irc
from twisted.internet import reactor, protocol

from User import InputUser

class Channel:

    def __init__(self, server, name, key = None):
        self.name = name
        self.server = server
        self.pusers = { }

        print "Creating channel:", name

    # reply when a user joins this channel
    def join(self):
        self.topic()
        self.names()
        # self.msg(server, "Type help for a list of channel commands!")

    def part(self):
        pass

    def mode(self):
        self.server.sendMessage(irc.RPL_CHANNELMODEIS, self.name, "", "")

    def topic(self):
        self.server.sendMessage(irc.RPL_TOPIC, self.name, irc.lowQuote("topic time!"))

    def names(self):
        self.server.sendMessage(irc.RPL_NAMREPLY, self.name, irc.lowQuote(','.join([self.server.nick] + self.pusers.keys() )))
        self.server.sendMessage(irc.RPL_ENDOFNAMES, self.name, irc.lowQuote("End of /NAMES list"))

    def registerUser(self, user):
        if user.name not in self.pusers:
            self.pusers[user.name] = user
            self.server.sendMessage("JOIN", self.name, frm="", prefix=user.fullname())

    def unregisterUser(self, user, kick=False):
        if user.name in self.pusers:
            if kick:
                self.server.sendMessage("KICK", user.name, '', frm=self.name)
            else:
                self.server.sendMessage("PART", self.name, frm="", prefix=user.fullname())
            del self.pusers[user.name]

    def msg(self, msg, prefix = None):
        self.server.sendMessage('PRIVMSG', irc.lowQuote(msg), frm=self.name, prefix=prefix if prefix is not None else self.server.hostname)

    def notice(self, msg, prefix):
        self.server.sendMessage('NOTICE', irc.lowQuote(msg), frm=self.name, prefix=prefix)

    def cmd(self, line):
        line = line.split(None, 1)

        # colon at the end indicates msg to a user
        if line[0][-1] == ":":
            if line[0][0:-1] not in self.pusers:
                print >> sys.stderr, "Msg to nonexitant user: ", line[0][0:-1]
                return
            self.pusers[line[0][0:-1]].command(line[1])
            return

        # otherwise - is it a method?
        method = getattr(self, "cmd_%s" % line[0], None)
        if method is not None:
            method(line[1])
            return

        print 'cmd to chan', line

    def cmd_help(self, params):
        self.notice("Halp!")

class IrclogdServer(irc.IRC):

    def dataReceived(self, data):
        print data
        irc.IRC.dataReceived(self, data)

    def connectionMade(self):
        irc.IRC.connectionMade(self)
        self.channels = { }
        self.pusers = { }

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

        print kwargs['prefix'], command, parameter_list

        # forwad to parent method
        return irc.IRC.sendMessage(self, command, *parameter_list, **kwargs)

    def irc_MODE(self, prefix, params):
        if params[0] not in self.channels:
            self.sendMessage(irc.ERR_NOTONCHANNEL)
            return

        self.channels[params[0]].mode()

    def irc_TOPIC(self, prefix, params):
        if params[0] not in self.channels:
            self.sendMessage(irc.ERR_NOTONCHANNEL)
            return

        self.channels[params[0]].topic()

    def irc_NAMES(self, prefix, params):
        if params[0] not in self.channels:
            self.sendMessage(irc.ERR_NOTONCHANNEL)
            return

        self.channels[params[0]].names()

    def irc_WHO(self, prefix, params):
        if params[0] in self.pusers:
            self.pusers[params[0]].who()
            return

    def irc_PRIVMSG(self, prefix, params):
        if params[0] not in self.channels:
            self.sendMessage(irc.ERR_CANNOTSENDTOCHAN)
            return

        self.channels[params[0]].cmd(params[-1])

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
            c = Channel(self, params[0])
            self.channels[params[0]] = c
            c.join()

    def irc_PART(self, prefix, params):
        if params[0][0] != "&":
            self.sendMessage(irc.ERR_NOSUCHCHANNEL)
            return

        if params[0] in self.channels:
            self.channels[params[0]].part()
            del self.channels[params[0]]

    def irc_PING(self, prefix, params):
        self.sendMessage("PONG", params)

    def irc_PONG(self, prefix, params):
        pass

    def irc_NICK(self, prefix, params):
        self.nick = params[0]

    def irc_QUIT(self, prefix, params):
        self.sendMessage("QUIT", *params)
        self.transport.loseConnection()

    def irc_INVITE(self, prefix, params):
        # not enough parameters?
        if len(params) < 2:
            self.sendMessage(irc.ERR_NEEDMOREPARAMS)
            return

        # channel doesn't exist? (NOT RFC COMPLICANT)
        if params[1] not in self.channels:
            self.sendMessage(irc.ERR_NOSUCHCHANNEL)
            return

        # already in the channel?
        if params[0] in self.pusers and params[1] in self.pusers[params[0]].channels:
            self.sendMessage(irc.ERR_USERONCHANNEL)
            return

        # at this point, there should be no reason why the user can't join the channel.

        # does the pseudouser exist? if not, create him
        if params[0] not in self.pusers:
            self.pusers[params[0]] = InputUser(self, params[0])

        # invite him over
        self.pusers[params[0]].invite(self.channels[params[1]])
        # send an ok
        self.sendMessage(irc.RPL_INVITING)

    def irc_KICK(self, prefix, params):
        # not enough parameters?
        if len(params) < 2:
            self.sendMessage(irc.ERR_NEEDMOREPARAMS)
            return

        # channel doesn't exist?
        if params[0] not in self.channels:
            self.sendMessage(irc.ERR_NOSUCHCHANNEL)
            return

        # not even in the channel?
        if params[1] not in self.pusers or params[0] not in self.pusers[params[1]].channels:
            self.sendMessage(irc.ERR_NOTONCHANNEL)
            return

        # at this point, there should be no reason why the user can't be kicked from the channel.

        # kick him out!
        self.pusers[params[1]].leave(self.channels[params[0]], True)

    def irc_unknown(self, prefix, command, params):
        print >> sys.stderr, "unkown msg", prefix, command, params

if __name__ == "__main__":
    factory = protocol.Factory()
    factory.protocol = IrclogdServer

    reactor.listenTCP(6667, factory, interface='localhost')
    reactor.run()
