# -*- coding: utf-8 -*-
import os
import logging
from gosa.common import Environment
from dbxml import *
from bsddb3.db import *


class DbxmlException(Exception):
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

        self.dbpath = dbpath

        # Enable logging
        self.log = logging.getLogger(__name__)
        self.env = Environment.getInstance()

        # Ensure that the given dbpath is accessible
        if not os.path.exists(os.path.dirname(dbpath)):
            os.makedirs(os.path.dirname(dbpath))

        # External access is required to validate against a given xml-schema
        self.manager = XmlManager(DBXML_ALLOW_EXTERNAL_ACCESS)
        #self.manager.setLogLevel(LEVEL_INFO, True)

        # Create the update context, it is required to query and manipulate data later.
        self.updateContext = self.manager.createUpdateContext()

        # Create query context and set namespaces
        self.queryContext = self.manager.createQueryContext()
        self.queryContext.setNamespace("", "http://www.gonicus.de/Events")
        self.queryContext.setNamespace("gosa", "http://www.gonicus.de/Events")
        self.queryContext.setNamespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")

        # Set a variable named $doc which contains the path to the dbxml container
        # This make queries a lot shorter.
        self.queryContext.setVariableValue("doc", XmlValue("dbxml:///%s" % (self.dbpath,)));

        # Let the user know that things went fine
        self.log.info("inventory database successfully initialized")

        # List all known inventory clients
        self.open()
        results = self.manager.query("collection($doc)/Event/Inventory/"
                "ClientUUID/text()", self.queryContext)
        results.reset()
        for value in results:
            self.log.debug("inventory database contains client-uuid %s'" % (value.asString(),))

    def sync(self):
        """
        Syncs database changes back to the filesystem
        """
        self.log.debug("inventory database '%s' synced" % (self.dbpath))
        self.container.sync()

    def close(self):
        """
        Closes the opened inventory container
        """
        self.log.debug("inventory database '%s' closed" % (self.dbpath))
        self.container.close()

    def open(self):
        """
        Opens the inventory container file.
        """

        # Open (create) the database container
        if self.manager.existsContainer(self.dbpath) != 0:
            self.log.debug("inventory database '%s' opened" % (self.dbpath))
            self.container = self.manager.openContainer(self.dbpath)
        else:
            self.log.debug("inventory database '%s' created and opened" % (self.dbpath))
            self.container = self.manager.createContainer(self.dbpath, DBXML_ALLOW_VALIDATION, XmlContainer.NodeContainer)

    def hardwareUUIDExists(self, huuid):
        """
        Checks whether an inventory exists for the given client ID or not.
        """
        results = self.manager.query("collection($doc)/Event/Inventory"
                "[HardwareUUID='%s']/HardwareUUID/string()" % (huuid), self.queryContext)

        # Walk through results if there are any and return True in that case.
        results.reset()
        return(results.size() != 0)

    def getClientUUIDByHardwareUUID(self, huuid):
        """
        Returns the ClientUUID used by the given HardwareUUID.
        """
        results = self.manager.query("collection($doc)/Event/Inventory"
                "[HardwareUUID='%s']/ClientUUID/string()" % (huuid), self.queryContext)

        # Walk through results and return the ClientUUID
        results.reset()
        if results.size() == 1:
            return(results.next().asString())
        else:
            raise DbxmlException("No or more than one ClientUUID was found for HardwareUUID")

    def getChecksumByUUID(self, uuid):
        """
        Returns the checksum of a specific entry.
        """
        results = self.manager.query("collection($doc)/Event/Inventory"
                "[ClientUUID='%s']/GOsaChecksum/string()" % (uuid), self.queryContext)

        # Walk through results and return the found checksum
        results.reset()
        if results.size() == 1:
            return(results.next().asString())
        else:
            raise DbxmlException("No or more than one checksums found for ClientUUID=%s" % (uuid))

    def addClientInventoryData(self, uuid, huuid, data):
        """
        Adds client inventory data to the database.
        """
        self.container.putDocument(huuid, data, self.updateContext)

    def deleteByHardwareUUID(self, huuid):
        results = self.manager.query("collection($doc)/Event/Inventory"
                "[HardwareUUID='%s']" % (huuid), self.queryContext)
        results.reset()
        if results.size() == 1:
            value = results.next()
            self.container.deleteDocument(value.asDocument().getName(), self.updateContext)
        else:
            raise DbxmlException("No or more than one document found, removal aborted!")
        return None