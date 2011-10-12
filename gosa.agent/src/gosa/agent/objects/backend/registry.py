# -*- coding: utf-8 -*-
import pkg_resources
import logging


class ObjectBackendRegistry(object):
    instance = None
    backends = {}
    uuidAttr = "entryUUID"

    def __init__(self):
        log = logging.getLogger("gosa.object.backend")
        # Load available backends
        log.critical("Test")
        for entry in pkg_resources.iter_entry_points("gosa.object.backend"):
            print "->", entry
            clazz = entry.load()
            ObjectBackendRegistry.backends[clazz.__name__] = clazz()

    def dn2uuid(self, backend, dn):
        return ObjectBackendRegistry.backends[backend].dn2uuid(dn)

    @staticmethod
    def getInstance():
        if not ObjectBackendRegistry.instance:
            ObjectBackendRegistry.instance = ObjectBackendRegistry()

        return ObjectBackendRegistry.instance

    @staticmethod
    def getBackend(name):
        if not name in ObjectBackendRegistry.backends:
            raise ValueError("no such backend '%s'" % name)

        return ObjectBackendRegistry.backends[name]
