#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import StringIO
import logging
from dbxml import *
from bsddb3.db import *
from lxml import etree, objectify
from gosa.common import Environment
from gosa.common.components import AMQPEventConsumer


class InventoryException(Exception):
    """
    Inventory exception class
    """
    pass


class InventoryDBXml(object):
    """
    GOsa client-inventory database based on DBXML
    """

    dbpath = None
    manager = None
    updateContext = None
    queryContext = None
    container = None

    def __init__(self, dbpath):
        """
        Creates and establishes a dbxml container connection.
        """

        # Ensure that the given dbpath is accessible
        if not os.path.exists(os.path.dirname(dbpath)):
            os.makedirs(os.path.dirname(dbpath))

        # External access is required to validate against a given xml-schema
        self.manager = XmlManager(DBXML_ALLOW_EXTERNAL_ACCESS)

        # Open (create) the database container
        self.container = self.manager.openContainer(dbpath, DB_CREATE|DBXML_ALLOW_VALIDATION)
        self.dbpath = "dbxml:///%s" % (dbpath,)

        # Create the update context, it is required to query and manipulate data later.
        self.updateContext = self.manager.createUpdateContext()

        # Create query context and set namespaces
        self.queryContext = self.manager.createQueryContext()
        self.queryContext.setNamespace("", "http://www.gonicus.de/Events")
        self.queryContext.setNamespace("gosa", "http://www.gonicus.de/Events")
        self.queryContext.setNamespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")

    def uuidExists(self, uuid):
        """
        Checks whether an inventory exists for the given client ID or not.
        """
        results = self.manager.query("collection('%s')/Event/Inventory[ClientUUID='%s']/ClientUUID/string()" % (
            self.dbpath, uuid), self.queryContext)

        # Walk through results if there are any and return True in that case.
        results.reset()
        for value in results:
            return True
        return False

    def getChecksumByUuid(self, uuid):
        """
        Returns the checksum of a specific entry.
        """
        results = self.manager.query("collection('%s')/Event/Inventory[ClientUUID='%s']/GOsaChecksum/string()" % (
            self.dbpath, uuid), self.queryContext)

        # Walk through results and return the found checksum
        results.reset()
        for value in results:
            return value.asString()
        return None

    def addClientInventoryData(self, uuid, data):
        """
        Adds client inventory data to the database.
        """
        self.container.putDocument(uuid, data, self.updateContext)

    def deleteByUUID(self, uuid):
        results = self.manager.query("collection('%s')/Event/Inventory[ClientUUID='%s']" % (self.dbpath, uuid), self.queryContext)
        results.reset()
        for value in results:
            self.container.deleteDocument(value.asDocument().getName(), self.updateContext)
        return None

# --------------------------


class InventoryConsumer(object):
    """
    Consumer for inventory events emitted from clients.
    """

    xmldb = None
    log = None
    inv_db = None

    def __init__(self):

        # Enable logging
        self.log = logging.getLogger(__name__)
        self.env = Environment.getInstance()

        # Try to establish the database connections
        self.xmldb = InventoryDBXml(self.env.config.get("inventory.dbpath", "/var/lib/gosa/inventory/db.dbxml"))

        # Let the user know that things went fine
        self.log.info("Client-inventory databases successfully initialized")

    def process(self, data):
        """
        Receives a new inventory-event and updates the corresponding
        database entries (MySql and dbxml)
        """

        # Try to extract the clients uuid and hostname out of the received data
        self.log.debug("New incoming client inventory event")
        try:
            binfo = data.xpath('/gosa:Event/gosa:Inventory', namespaces={'gosa': 'http://www.gonicus.de/Events'})[0]
            hostname = str(binfo['Hostname'])
            uuid = str(binfo['ClientUUID'])
            checksum = str(binfo['GOsaChecksum'])
            self.log.debug("Client inventory event received for hostname %s (%s)" % (hostname, uuid))
        except Exception as e:
            msg = "Failed extract client info out of received Inventory-Event! Error was: %s" % (str(e), )
            self.log.error(msg)
            raise InventoryException(msg)

        # The client is already part of our inventory database
        if self.xmldb.uuidExists(uuid):

            # Now check if the checksums match or if we've to update our databases
            if checksum == self.xmldb.getChecksumByUuid(uuid):
                self.log.debug("Client record already exists and checksums (%s) are equal, skipping addition." % (checksum))
            else:
                self.log.debug("Client record already exists but the checksum had changed, updated entry.")
                self.xmldb.deleteByUUID(uuid)
                datas = etree.tostring(data, pretty_print=True)
                self.xmldb.addClientInventoryData(uuid, datas)
        else:

            # A new client has send its inventory data - Import data into dbxml
            self.log.debug("Client record is new and will be added!")
            datas = etree.tostring(data, pretty_print=True)
            self.xmldb.addClientInventoryData(uuid, datas)
