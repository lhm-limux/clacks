# -*- coding: utf-8 -*-


class XMLDBException(Exception):
    """
    Exception used for DBXml errors
    """
    pass



class XMLDBInterface(object):

    def openDatabase(self):
        """
        Opens an existing database
        """
        raise NotImplementedError("openDatabase")

    def createDatabase(self, name):
        """
        Creates a new database collection.

        =========== ======================
        Key         Value
        =========== ======================
        name        The name of the database to create
        =========== ======================
        """
        raise NotImplementedError("createDatabase")

    def databaseExists(self, name):
        """
        Checks whethter a databse exists or not

        =========== ======================
        Key         Value
        =========== ======================
        name        The name of the database to check for.
        =========== ======================
        """
        raise NotImplementedError("databaseExists")

    def addDocument(self, name, contents):
        """
        Adds a new document to the database

        addDocument('/path/world.xml', contents)

        =========== ======================
        Key         Value
        =========== ======================
        name        The name of the document to add
        content     The xml content of the document as string
        =========== ======================
        """
        raise NotImplementedError("addDocument")

    def documentExists(self, name):
        """
        Checks whethter a document exists or not

        =========== ======================
        Key         Value
        =========== ======================
        name        The name of the document to check for.
        =========== ======================
        """
        raise NotImplementedError("documentExists")

    def getDocuments(self):
        """
        Returns a list of all documents attached to the given database.
        """
        raise NotImplementedError("getDocuments")

    def xquery(self, query):
        """
        =========== ======================
        Key         Value
        =========== ======================
        query       The query to execute.
        =========== ======================

        Executes an xquery statement
            xquery("collection('db/universe/world.xml')")

        Returns an interable result set.
        """
        raise NotImplementedError("xquery")

    def setNamespace(self, abbr, namespace):
        """
        Sets a namespace abbreviation

        =========== ======================
        Key         Value
        =========== ======================
        name        The abbreviation/short-name of the namespace
        uri         The namespace uri
        =========== ======================
        """
        raise NotImplementedError("setNamespace")

    def dropDatabase(self, name):
        """
        Drops the given database

        =========== ======================
        Key         Value
        =========== ======================
        name        The name of the database to drop
        =========== ======================
        """
        raise NotImplementedError("dropDatabase")

    def deleteDocument(self, name):
        """
        Removes the given document from the currently openened database

        =========== ======================
        Key         Value
        =========== ======================
        name        The name of the document to delete
        =========== ======================
        """
        raise NotImplementedError("deleteDocument")
