import sys

from twisted.words.protocols import irc

import input.udp, input.fifo

class PseudoUser:
    """
        Instances of this class are virtual users on the server.

        This is a base class providing only basic functionality, allowing the
        user to summon and dismiss virtual users on the fly by using INVITEs
        and KICKs.
    """

    def __init__(self, server, name):
        name = name.split()[0]

        self.server = server
        self.name = name
        self.channels = { }

    def cmd(self, line, type = 0):
        """
            Called when a message is sent to the virtual user. This calls the
            according cmd_subcommand, where subcommand is the first word of the
            received line.

            The type parameter specifies the kind of message received:
                0: public msg in a channel
                1: notice
                2: privmsg
            The cmd should try to reply the same way.

        """
        line = line.split()

        # otherwise - is it a method?
        method = getattr(self, "cmd_%s" % line[0], None)
        if method is not None:
            method(line[1:])
            return

        self.notice("Unknown command: " + line[0])

    def cmd_die(self, params):
        """
            Removes a user from all channels and frees its resources.
        """
        self.notice("Dying..")

        while len(self.channels) > 0:
            self.leave(self.channels.values()[0])

    def invite(self, channel):
        self.channels[channel.name] = channel
        channel.registerUser(self)

    def leave(self, channel, kick=False):
        """
            Called when the virtual user should leave a channel. This usually
            happens when it is KICKed by the user, or the user PARTed from the
            channel.

            This method should make sure that if the virtual user is no longer
            on any channel, the destroy() method is called.
        """
        if channel.name not in self.channels:
            return
        del self.channels[channel.name]
        channel.unregisterUser(self, kick)

        # no channels left? destwoy ourself!
        if len(self.channels) is 0:
            self.destroy()

    def msg(self, msg, channel = None):
        """
            This method multicasts a msg to all channels the user is in.
        """
        if channel is None:
            for name in self.channels:
                self.channels[name].msg(msg, self.fullname())
            return

        # sanity check!
        if channel.name not in self.channels:
            print >> sys.stderr, "printing on a chan we're not in??"
        channel.msg(msg, self.fullname())

    def notice(self, msg, channel = None):
        """
            This method multicasts a notice to all channels the user is in.
        """
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
            This method is called when the user is no longer on any channels.

            It should be overwritten to do cleanup work, most importantly
            remove any reactor callbacks.
        """

        # delete ourself from the pusers reference here
        del self.server.pusers[self.name]

class InputUser(PseudoUser):
    """
        A specialized type of PseudoUser, which supports input from external
        sources.

        Using the input command, an InputUser can be associated with some kind
        of external source, reporting all messages from this source as
        PRIVMSGSs to all channels the user is in.

        At this point, supported input calls are:
            > input udp port [addr,..]
            Listens for messages on the specified udp port. If the optional
            addr argument is given, all input from hosts not in this
            comma-seperated list is dropped.

            > input fifo fifopath
            Listens on a fifo, which must already exist.
    """

    knownInputs = {
            'udp' : input.udp.UdpInputFactory,
            'fifo' : input.fifo.FifoInputFactory,
        }

    def __init__(self, server, name):
        PseudoUser.__init__(self, server, name)

        # no input at the beginning
        self.input = None

    def cmd_input(self, params):
        """
            Associates this virtual user with an input, using the constructors
            from the knonwnInputs static variable.

            If an input is already set, an error is returned.
        """
        if self.input is not None:
            self.notice("This user already has an input! Use `reset' to reset it.")
            return

        if params[0] not in InputUser.knownInputs or InputUser.knownInputs[params[0]] is None:
            self.notice("Unknown or unsupported input: " + params[0])
            return

        self.notice("Setting user input to " + params[0])
        try:
            proto = InputUser.knownInputs[params[0]](self, params[1:])
        except Exception as e:
            self.notice("Failed setting input!")
            self.notice("Exception: " + str(e))
        else:
            self.input = proto

    def cmd_reset(self, params):
        """
            Resets the input, cleaning up all listening resources - if there is one.
        """
        if self.input is None:
            self.notice("There is no input to reset.")
            return

        # make sure this is destroyed
        self.input.destroy()
        self.notice("Removed {} input..".format(self.input.name))
        self.input = None

    def who(self):
        self.server.sendMessage(irc.RPL_WHOREPLY, self.channels.keys()[0], "input/none" if self.input is None else "input/{}".format(self.input.name), self.server.hostname, self.server.hostname, self.name, "H", "1 {}".format("InputUser"))
        self.server.sendMessage(irc.RPL_ENDOFWHO)

    def fullname(self):
        return "{}!{}@{}".format(self.name, "input/none" if self.input is None else "input/{}".format(self.input.name), self.server.hostname)

    def destroy(self):
        """
           Overriding this to forward the destroy() call to a potential input.
        """

        if self.input is not None:
            self.input.destroy()

        PseudoUser.destroy(self)

