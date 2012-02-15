# -*- coding: utf-8 -*-
"""
The *AMQPClientService* is responsible for connecting the *client* to the AMQP
bus, registers the required queues, listens for commands on that queues
and dispatches incoming commands to the :class:`clacks.client.command.CommandRegistry`.

**Queues**

In contrast to the clacks agent, every client only has a single queue. It is
constructed of these components::

    {domain}.client.{uuid}

For external calls it makes use of the
:class:`clacks.common.components.amqp_proxy.AMQPServiceProxy`, so it will
construct additional temporary reply queues as needed.

**Events**

The clacks client produces a **ClientAnnounce** event on startup which tells
interested agents about the client capabilities (commands it provides) and
some hardware information.

This information is re-send when the client receives a **ClientPoll** event,
which is generated by an agent node which is not able to get client information
from other agent nodes (i.e. if it's the only one).

On client shutdown, a **ClientLeave** is emitted to tell the agents that
the client has passed away.
"""
import sys
import netifaces
import traceback
import logging
import random
import time
from threading import Timer
from netaddr import IPNetwork
from zope.interface import implements
from qpid.messaging import Message
from qpid.messaging.exceptions import NotFound
from clacks.common.gjson import loads, dumps
from clacks.common.components.jsonrpc_utils import ServiceRequestNotTranslatable, BadServiceRequest
from clacks.common.handler import IInterfaceHandler
from clacks.common.components.registry import PluginRegistry
from clacks.common.components.amqp import AMQPWorker, EventConsumer
from clacks.common.event import EventMaker
from clacks.common import Environment


class AMQPClientService(object):
    """
    Internal class to serve all available queues and commands to
    the AMQP broker.
    """
    implements(IInterfaceHandler)
    _priority_ = 10

    def __init__(self):
        env = Environment.getInstance()
        self.log = logging.getLogger(__name__)
        self.log.debug("initializing AMQP service provider")
        self.env = env
        self.__cr = None
        self.__cmdWorker = None

    def serve(self):
        """ Start AMQP service for this clacks service provider. """
        # Load AMQP and Command registry instances
        amqp = PluginRegistry.getInstance('AMQPClientHandler')
        self.__cr = PluginRegistry.getInstance('ClientCommandRegistry')

        # Add private processor for client queue
        # pylint: disable=E1101
        self.__cmdWorker = AMQPWorker(self.env, connection=amqp.getConnection(),
                r_address="""%s.client.%s; {
                    create:always,
                    node:{
                        type:queue,
                        durable: False,
                        x-declare: {
                            exclusive: True,
                            auto-delete: True },
                        x-bindings:[ {
                                exchange:"amq.direct",
                                queue:"%s.client.%s" } ]
                        }
                    }""" % (self.env.domain, self.env.uuid, self.env.domain, self.env.uuid),
            workers=self.env.config.get('amqp.command-worker', default=1),
            callback=self.commandReceived)

        # Add event processor
        try:
            EventConsumer(self.env,
                amqp.getConnection(),
                xquery="""
                    declare namespace f='http://www.gonicus.de/Events';
                    let $e := ./f:Event
                    return $e/f:ClientPoll
                """,
                callback=self.__handleClientPoll)

            # Gather interface information
            self.__announce(True)

        except NotFound as e:
            self.env.log.critical("queue gone: %s" % str(e))

        # Send a ping on a regular base
        uuid = self.env.uuid
        timeout = float(self.env.config.get('client.ping-interval', default=600))
        def ping():
            while self.env.active:
                e = EventMaker()
                amqp = PluginRegistry.getInstance('AMQPClientHandler')
                info = e.Event(e.ClientPing(e.Id(uuid)))
                amqp.sendEvent(info)
                time.sleep(timeout)

        pinger = Timer(10.0, ping)
        pinger.start()
        self.env.threads.append(pinger)

    def reAnnounce(self):
        if self.__cr:
            self.__announce(False)

    def commandReceived(self, ssn, message):
        """
        Process incoming commands, coming in with session and message
        information.

        ================= ==========================
        Parameter         Description
        ================= ==========================
        ssn               AMQP session object
        message           Received AMQP message
        ================= ==========================

        Incoming messages are coming from an
        :class:`clacks.common.components.amqp_proxy.AMQPServiceProxy` which
        is providing a *reply to* queue as a return channel. The command
        result is written to that queue.
        """
        err = None
        res = None
        id_ = ''

        # Check for id
        if not message.user_id:
            raise Exception("incoming message without user_id")

        # Check for reply_to
        if not message.reply_to:
            raise Exception("incoming message without reply_to")

        try:
            req = loads(message.content)
        except ServiceRequestNotTranslatable, e:
            err = str(e)
            req = {'id': id_}

        if err == None:
            try:
                id_ = req['id']
                name = req['method']
                args = req['params']

            except KeyError:
                err = str(BadServiceRequest(message.content))

        self.log.debug("received call [%s] for %s: %s(%s)" % (id_, message.user_id, name, args))

        # Try to execute
        if err == None:
            try:
                res = self.__cr.dispatch(name, *args)
            except Exception as e:
                err = str(e)

                # Write exception to log
                exc_type, exc_value, exc_traceback = sys.exc_info()
                self.log.error(traceback.format_exception(exc_type, exc_value, exc_traceback))

        self.log.debug("returning call [%s]: %s / %s" % (id_, res, err))

        response = dumps({"result": res, "id": id_, "error": err})
        ssn.acknowledge()

        # Talk to client generated reply queue
        sender = ssn.sender(message.reply_to)

        # Get rid of it...
        sender.send(Message(response))

    def __handleClientPoll(self, data):
        delay = random.randint(0, 30)
        self.log.debug("received client poll - will answer in %d seconds" % delay)
        time.sleep(delay)
        self.__announce(True)

    def __announce(self, initial=False):
        amqp = PluginRegistry.getInstance('AMQPClientHandler')
        e = EventMaker()

        # Assemble network information
        more = []
        netinfo = []
        for interface in netifaces.interfaces():
            i_info = netifaces.ifaddresses(interface)

            # Skip lo interfaces
            if i_info[netifaces.AF_LINK][0]['addr'] == '00:00:00:00:00:00':
                continue

            # Skip lo interfaces
            if not netifaces.AF_INET in i_info:
                continue

            # Assemble ipv6 information
            ip6 = ""
            if netifaces.AF_INET6 in i_info:
                ip = IPNetwork("%s/%s" % (i_info[netifaces.AF_INET6][0]['addr'].split("%",1)[0],
                                        i_info[netifaces.AF_INET6][0]['netmask']))
                ip6 = str(ip)

            netinfo.append(
                e.NetworkDevice(
                    e.Name(interface),
                    e.IPAddress(i_info[netifaces.AF_INET][0]['addr']),
                    e.IPv6Address(ip6),
                    e.MAC(i_info[netifaces.AF_LINK][0]['addr']),
                    e.Netmask(i_info[netifaces.AF_INET][0]['netmask']),
                    e.Broadcast(i_info[netifaces.AF_INET][0]['broadcast'])))

        more.append(e.NetworkInformation(*netinfo))

        # Build event
        if initial:
            info = e.Event(
                e.ClientAnnounce(
                    e.Id(self.env.uuid),
                    e.Name(self.env.id),
                    *more))

            amqp.sendEvent(info)

        # Assemble capabilities
        more = []
        caps = []
        for command, dsc in self.__cr.commands.iteritems():
            caps.append(
                e.ClientMethod(
                e.Name(command),
                e.Path(dsc['path']),
                e.Signature(','.join(dsc['sig'])),
                e.Documentation(dsc['doc'])))
        more.append(e.ClientCapabilities(*caps))

        info = e.Event(
            e.ClientSignature(
                e.Id(self.env.uuid),
                e.Name(self.env.id),
                *more))

        amqp.sendEvent(info)

        if not initial:
            try:
                sk = PluginRegistry.getInstance('SessionKeeper')
                sk.sendSessionNotification()
            except:
                pass
