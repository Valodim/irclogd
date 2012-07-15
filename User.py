
from twisted.words.protocols import irc

import input.udp, input.fifo

class PseudoUser:

    def __init__(self, server, name):
        name = name.split()[0]

        self.server = server
        self.name = name
        self.channels = { }

    def command(self, line):
        line = line.split(None, 1)

        # otherwise - is it a method?
        method = getattr(self, "cmd_%s" % line[0], None)
        if method is not None:
            method(line[1])
            return

        self.notice("Unknown command: " + line[0])

    def invite(self, channel):
        self.channels[channel.name] = channel
        channel.registerUser(self)

    def leave(self, channel, kick=False):
        if channel.name not in self.channels:
            return
        del self.channels[channel.name]
        channel.unregisterUser(self, kick)

        # no channels left? destwoy ourself!
        if len(self.channels) is 0:
            self.destroy()

    def msg(self, msg, channel = None):
        if channel is None:
            for name in self.channels:
                self.channels[name].msg(msg, self.fullname())
            return

        # sanity check!
        if channel.name not in self.channels:
            print >> sys.stderr, "printing on a chan we're not in??"
        channel.msg(msg, self.fullname())

    def notice(self, msg, channel = None):
        if channel is None:
            for name in self.channels:
                self.channels[name].notice(msg, self.fullname())
            return

        # sanity check!
        if channel.name not in self.channels:
            print >> sys.stderr, "printing on a chan we're not in??"
        channel.notice(msg, self.fullname())

    def who(self):
        self.server.sendMessage(irc.RPL_WHOREPLY, self.channels.keys()[0], "pseudo", self.server.hostname, self.server.hostname, self.name, "H", "1 {}".format("PseudoUser"))
        self.server.sendMessage(irc.RPL_ENDOFWHO)

    def fullname(self):
        return "{}!{}@{}".format(self.name, "pseudo", self.server.hostname)

    def destroy(self):
        """
            This method is called when the user is no longer on any channels,
            and should be overwritten to do cleanup work, most importantly
            remove it from the reactor.
        """

        # delete ourself from the pusers reference here
        del self.server.pusers[self.name]

class InputUser(PseudoUser):
    knownInputs = {
            'udp' : input.udp.UdpInputFactory,
            'fifo' : input.fifo.FifoInputFactory,
        }

    def __init__(self, server, name):
        PseudoUser.__init__(self, server, name)

        # no input at the beginning
        self.input = None

    def cmd_input(self, line):
        params = line.split()
        if self.input is not None:
            self.notice("This user already has an input! Use `reset' to reset it.")
            return

        if params[0] not in InputUser.knownInputs or InputUser.knownInputs[params[0]] is None:
            self.notice("Unknown or unsupported input: " + params[0])
            return

        self.notice("Switching user input to " + params[0])
        try:
            proto = InputUser.knownInputs[params[0]](self, params[1:])
        except Exception as e:
            self.notice("Failed switching input!")
            self.notice("Exception: " + str(e))
        else:
            self.input = proto

    def who(self):
        self.server.sendMessage(irc.RPL_WHOREPLY, self.channels.keys()[0], "input/none" if self.input is None else "input/{}".format(self.input.name), self.server.hostname, self.server.hostname, self.name, "H", "1 {}".format("InputUser"))
        self.server.sendMessage(irc.RPL_ENDOFWHO)

    def fullname(self):
        return "{}!{}@{}".format(self.name, "input/none" if self.input is None else "input/{}".format(self.input.name), self.server.hostname)

    def destroy(self):
        if self.input is not None:
            self.input.destroy()

        PseudoUser.destroy(self)

