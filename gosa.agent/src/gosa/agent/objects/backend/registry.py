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
        for entry in pkg_resources.iter_entry_points("gosa.object.backend"):
            clazz = entry.load()
            ObjectBackendRegistry.backends[clazz.__name__] = clazz()

    def dn2uuid(self, backend, dn):
        return ObjectBackendRegistry.backends[backend].dn2uuid(dn)

    def uuid2dn(self, backend, uuid):
        return ObjectBackendRegistry.backends[backend].uuid2dn(uuid)

    def get_timestamps(self, backend, dn):
        return ObjectBackendRegistry.backends[backend].get_timestamps(dn)

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
