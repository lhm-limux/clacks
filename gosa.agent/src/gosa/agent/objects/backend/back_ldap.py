# -*- coding: utf-8 -*-
import ldap
import ldap.filter
import ldap.schema
import time
import datetime
from logging import getLogger
from gosa.common import Environment
from gosa.agent.ldap_utils import LDAPHandler
from gosa.agent.objects.backend.backend import ObjectBackend, EntryNotFound, EntryNotUnique


class LDAP(ObjectBackend):

    def __init__(self):
        # Load LDAP handler class
        self.env = Environment.getInstance()
        self.log = getLogger(__name__)

        self.lh = LDAPHandler.get_instance()
        self.con = self.lh.get_connection()
        self.uuid_entry = self.env.config.get("ldap.uuid_attribute", "entryUUID")

    def __del__(self):
        self.lh.free_connection(self.con)

    def load(self, uuid, info):
        keys = info.keys()
        fltr_tpl = "%s=%%s" % self.uuid_entry
        fltr = ldap.filter.filter_format(fltr_tpl, [uuid])

        self.log.debug("searching with filter '%s' on base '%s'" % (fltr,
            self.lh.get_base()))
        res = self.con.search_s(self.lh.get_base(), ldap.SCOPE_SUBTREE, fltr,
            keys)

        # Check if res is valid
        self.__check_res(uuid, res)

        # Do value conversation
        items = dict((k,v) for k, v in res[0][1].iteritems() if k in keys)
        for key, value in items.items():
            cnv = getattr(self, "_convert_from_%s" % info[key].lower())
            lcnv = []
            for lvalue in items[key]:
                lcnv.append(cnv(lvalue))
            items[key] = lcnv

        return items

    def exists(self, misc):
        if self.is_uuid(misc):
            fltr_tpl = "%s=%%s" % self.uuid_entry
            fltr = ldap.filter.filter_format(fltr_tpl, [misc])

            res = self.con.search_s(self.lh.get_base(), ldap.SCOPE_SUBTREE,
                    fltr, [self.uuid_entry])

        else:
            res = self.con.search_s(misc, ldap.SCOPE_ONELEVEL, '(objectClass=*)',
                [self.uuid_entry])

        if not res:
            return False

        return len(res) == 1

    def remove(self, uuid, recursive=False):
        dn = self.dn2uuid(uuid)

        if recursive:
            self.__delete_children(dn)

        else:
            self.con.delete_s(dn)

    def __delete_children(self, dn):
        res = self.con.search_s(dn, ldap.SCOPE_ONELEVEL, '(objectClass=*)',
                [self.uuid_entry])

        for c_dn, entry in res:
            self.__delete_children(c_dn)

        # Delete ourselves
        self.con.delete_s(dn)

#    def retract(self, uuid):
#        pass

#    def create(self, base, data):
#        pass

#    def extend(self, base, data):
#        pass

    def update(self, uuid, data):
        print

        # Load DN for entry and assemble a proper modlist
        dn = self.uuid2dn(uuid)
        print "Resolved to DN:", dn
        print "-"*80

        # We only get the values that have changed

        print "="*80
        from pprint import pprint
        pprint(data)

        print "="*80
        print

    def uuid2dn(self, uuid):
        # Get DN of entry
        fltr_tpl = "%s=%%s" % self.uuid_entry
        fltr = ldap.filter.filter_format(fltr_tpl, [uuid])

        self.log.debug("searching with filter '%s' on base '%s'" % (fltr,
            self.lh.get_base()))
        res = self.con.search_s(self.lh.get_base(), ldap.SCOPE_SUBTREE, fltr,
                [self.uuid_entry])

        self.__check_res(uuid, res)

        return unicode(res[0][0].decode('utf-8'))

    def dn2uuid(self, dn):
        res = self.con.search_s(dn.encode('utf-8'), ldap.SCOPE_BASE, '(objectClass=*)',
                [self.uuid_entry])

        # Check if res is valid
        self.__check_res(dn, res)

        return res[0][1][self.uuid_entry][0]

    def __check_res(self, uuid, res):
        if not res:
            raise EntryNotFound("entry '%s' is not present" % uuid)

        if len(res) != 1:
            raise EntryNotUnique("entry '%s' is not unique" % uuid)

    def _convert_from_boolean(self, value):
        return value == "TRUE"

    def _convert_from_string(self, value):
        return str(value)

    def _convert_from_unicodestring(self, value):
        return unicode(value.decode('utf-8'))

    def _convert_from_integer(self, value):
        return int(value)

    def _convert_from_timestamp(self, value):
        return datetime.datetime.strptime(value, "%Y%m%d%H%M%SZ")

    def _convert_from_date(self, value):
        ts = time.mktime(time.strptime(value, "%Y%m%d%H%M%SZ"))
        return datetime.date.fromtimestamp(ts)

    def _convert_from_binary(self, value):
        return value
