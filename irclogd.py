#!/usr/bin/env python

import sys
from datetime import datetime

from twisted.words.protocols import irc
from twisted.internet import reactor, protocol

from User import InputUser

debug = False

port = 6669

motd = """
This is irclogd, started at {starttime}, listening on {port}.

Usage:
    JOIN a channel, INVITE a virtual user to it, and send them an input
    directive to start listening on some source. You can arbitrarily name
    virtual users, and invite them to multiple channels.
    To get rid of a virtual user, KICK them from all channels they are
    currently in, or send them the "die" command.

    Example session:
        /join &mychan

        /invite udpsource1 &mychan
        /msg udpsource1 input udp 12345

        /invite fifosource1 &mychan
        /msg fifosource1 input fifo /path/to/fifo
""".format(starttime=datetime.now(), port=port)

class Channel:

    def __init__(self, server, name, key = None):
        self.name = name
        self.server = server
        self.pusers = { }

    # channel interfacing methods

    def msg(self, msg, prefix = None):
        self.server.sendMessage('PRIVMSG', irc.lowQuote(msg), frm=self.name, prefix=prefix if prefix is not None else self.server.hostname)

    def notice(self, msg, prefix):
        self.server.sendMessage('NOTICE', irc.lowQuote(msg), frm=self.name, prefix=prefix)

    # user management

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

    # channel information callbacks

    def join(self):
        self.topic()
        self.names()

    def part(self):
        for u in self.pusers:
            u.leave(self)

    def mode(self):
        self.server.sendMessage(irc.RPL_CHANNELMODEIS, self.name, "", "")

    def topic(self):
        self.server.sendMessage(irc.RPL_TOPIC, self.name, irc.lowQuote("dummy topic (maybe put some info here?)"))

    def names(self):
        self.server.sendMessage(irc.RPL_NAMREPLY, self.name, irc.lowQuote(','.join([self.server.nick] + self.pusers.keys() )))
        self.server.sendMessage(irc.RPL_ENDOFNAMES, self.name, irc.lowQuote("End of /NAMES list"))

    # command callbacks

    def cmd(self, line):
        line = line.split(None, 1)

        # colon at the end indicates msg to a user
        if line[0][-1] == ":":
            if line[0][0:-1] not in self.pusers:
                print >> sys.stderr, "Msg to nonexitant user: ", line[0][0:-1]
                return
            self.pusers[line[0][0:-1]].cmd(line[1])
            return

        # otherwise - is it a method?
        method = getattr(self, "cmd_%s" % line[0], None)
        if method is not None:
            method(line[1])
            return

    def cmd_help(self, params):
        self.notice("Halp!")

class IrclogdServer(irc.IRC):
    """
        This is one log server connection. It maintains a number of Channels
        and PseudoUsers, which most of the commands will be forwarded to.
    """

    def dataReceived(self, data):
        if debug:
            print data
        irc.IRC.dataReceived(self, data)

    def connectionMade(self):
        irc.IRC.connectionMade(self)
        self.channels = { }
        self.pusers = { }

    def sendMessage(self, command, *parameter_list, **kwargs):
        """
            This is a generic method for sending messages. It mostly wraps
            IRC.sendMessage, adding a thin convenience layer:
                - If no prefix kwarg is given, the server's hostname will be
                  used as prefix.
                - If no frm kwarg is given, the user's nick will be inserted as
                  first argument.
                - The last argument is prefixed with a colon.
        """

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

        if debug:
            print kwargs['prefix'], command, parameter_list

        # forwad to parent method
        return irc.IRC.sendMessage(self, command, *parameter_list, **kwargs)

    # Channel management callbacks

    def irc_JOIN(self, prefix, params):
        for chan in params[0].split(','):
            if chan[0] != "&" and chan[0] != "#":
                self.sendMessage(irc.ERR_NOSUCHCHANNEL)
                return

            if chan not in self.channels:
                c = Channel(self, chan)
                self.channels[chan] = c
                c.join()

    def irc_PART(self, prefix, params):
        for chan in params[0].split(','):
            if (chan[0] != "&" and chan[0] != "#") or chan not in self.channels:
                self.sendMessage(irc.ERR_NOSUCHCHANNEL)
                return

            if chan in self.channels:
                self.channels[chan].part()
                del self.channels[chan]

    def irc_MODE(self, prefix, params):
        for chan in params[0].split(','):
            if chan not in self.channels:
                self.sendMessage(irc.ERR_NOTONCHANNEL)
                return

            self.channels[chan].mode()

    def irc_TOPIC(self, prefix, params):
        for chan in params[0].split(','):
            if chan not in self.channels:
                self.sendMessage(irc.ERR_NOTONCHANNEL)
                return

            self.channels[chan].topic()

    def irc_NAMES(self, prefix, params):
        for chan in params[0].split(','):
            if chan not in self.channels:
                self.sendMessage(irc.ERR_NOTONCHANNEL)
                return

            self.channels[chan].names()

    # PseudoUser management callbacks

    def irc_WHO(self, prefix, params):
        if params[0] in self.pusers:
            self.pusers[params[0]].who()
            return

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

    # Other and generic callbacks

    def irc_PRIVMSG(self, prefix, params):
        """
            Callback for PRIVMSG. These are either forwarded as commands to
            channels, or users.
        """
        # missing RFC: multicast

        # send to channel?
        if params[0] in self.channels:
            self.channels[params[0]].cmd(params[-1])
            return

        # send to user?
        if params[0] in self.pusers:
            self.pusers[params[0]].cmd(params[-1])
            return

        # didn't send anything? give an error
        self.sendMessage(irc.ERR_NORECIPIENT)

    def irc_PING(self, prefix, params):
        self.sendMessage("PONG", params)

    def irc_PONG(self, prefix, params):
        pass

    def irc_USER(self, prefix, params):
        self.user = params
        self.sendMessage(irc.RPL_MOTDSTART, "- irclogd Message of the day -")
        for l in motd.split("\n"):
            self.sendMessage(irc.RPL_MOTD, l)
        self.sendMessage(irc.RPL_ENDOFMOTD, "End of /MOTD command")

    def irc_NICK(self, prefix, params):
        self.nick = params[0]

    def irc_QUIT(self, prefix, params):
        self.sendMessage("QUIT", *params)
        self.transport.loseConnection()

    def irc_unknown(self, prefix, command, params):
        print >> sys.stderr, "unkown msg", prefix, command, params

if __name__ == "__main__":
    factory = protocol.Factory()
    factory.protocol = IrclogdServer

    reactor.listenTCP(port, factory, interface='localhost')
    reactor.run()
