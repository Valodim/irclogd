# You can run this .tac file directly with:
#    twistd -ny irclogd.tac

from twisted.application import service, internet
from twisted.internet import protocol
from irclogd import irclogd

port = 6700
debug = False

def getService():

    # create a resource to serve static files
    factory = protocol.Factory()
    factory.protocol = irclogd.IrclogdServer
    factory.debug = debug
    return internet.TCPServer(port, factory)

# this is the core part of any tac file, the creation of the root-level
# application object
application = service.Application("irclogd")

# attach the service to its parent application
service = getService()
service.setServiceParent(application)
