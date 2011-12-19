# -*- coding: utf-8 -*-
"""
Object Index
============

The Object Index is the search engine in GOsa. It keeps track about
all defined object types and can find references to it inside of its
local index database

----
"""
import re
import inspect
import logging
import collections
import ldap.dn
import zope.event
import datetime
import pkg_resources
import ldap.dn
from itertools import izip
from lxml import etree, objectify
from zope.interface import implements
from time import time
from base64 import b64encode, b64decode
from ldap import DN_FORMAT_LDAPV3
from gosa.common import Environment
from gosa.common.utils import N_
from gosa.common.handler import IInterfaceHandler
from gosa.common.components import Command, Plugin, PluginRegistry
from gosa.agent.objects import GOsaObjectFactory, GOsaObjectProxy, ObjectChanged, SCOPE_BASE, SCOPE_ONE, SCOPE_SUB, ProxyException, ObjectException
from gosa.agent.lock import GlobalLock
from gosa.agent.xmldb import XMLDBHandler
from gosa.agent.ldap_utils import LDAPHandler


class FilterException(Exception):
    pass


class IndexException(Exception):
    pass


class ObjectIndex(Plugin):
    """
    The *ObjectIndex* keeps track of objects and their indexed attributes. It
    is the search engine that allows quick querries on the data set with
    paged results and wildcards.
    """
    implements(IInterfaceHandler)

    _priority_ = 20
    _target_ = 'core'
    _indexed = False

    def __init__(self):
        self.env = Environment.getInstance()
        self.log = logging.getLogger(__name__)
        self.log.info("initializing object index handler")
        self.factory = GOsaObjectFactory.getInstance()

        # Listen for object events
        zope.event.subscribers.append(self.__handle_events)

    def serve(self):
        # Load db instance
        self.db = PluginRegistry.getInstance("XMLDBHandler")
        self.base = LDAPHandler.get_instance().get_base()

        if not self.db.collectionExists("objects"):
            schema = self.factory.getXMLObjectSchema(True)
            self.db.createCollection("objects",
                {"o": "http://www.gonicus.de/Objects", "xsi": "http://www.w3.org/2001/XMLSchema-instance"},
                {"objects.xsd": schema})

        # Sync index
        if self.env.config.get("index.disable", "False").lower() != "true":
            sobj = PluginRegistry.getInstance("SchedulerService")
            sobj.getScheduler().add_date_job(self.sync_index,
                    datetime.datetime.now() + datetime.timedelta(seconds=30),
                    tag='_internal', jobstore='ram')

    def escape(self, data):
        html_escape_table = [
                ("$", "&#36;"), ("{", "&#123;"), ("}", "&#125;"),
                ("(", "&#40;"), (")", "&#41;")]

        for a, b in html_escape_table:
            data = data.replace(a, b)

        return data

    def sync_index(self):
        # Don't index if someone else is already doing it
        if GlobalLock.exists():
            return

        # Don't run index, if someone else already did until the last
        # restart.
        cr = PluginRegistry.getInstance("CommandRegistry")
        nodes = cr.getNodes()
        if len([n for n, v in nodes.items() if 'Indexed' in v and v['Indexed']]):
            return

        GlobalLock.acquire()
        self._indexed = True

        t0 = time()

        def resolve_children(dn):
            self.log.debug("found object '%s'" % dn)
            res = {}

            children = self.factory.getObjectChildren(dn)
            res = dict(res.items() + children.items())

            for chld in children.keys():
                res = dict(res.items() + resolve_children(chld).items())

            return res

        self.log.info("scanning for objects")
        res = resolve_children(self.base)
        res[self.base] = 'dummy'

        self.log.info("generating object index")

        # Find new entries
        backend_objects = []
        for o in sorted(res.keys(), key=len):

            # Get object
            try:
                obj = GOsaObjectProxy(o)

            except ProxyException as e:
                self.log.warning("not indexing %s: %s" % (o, str(e)))
                continue

            except ObjectException as e:
                self.log.warning("not indexing %s: %s" % (o, str(e)))
                continue

            # Check for index entry
            changed = self.db.xquery("collection('objects')/*[UUID/string() = '%s']/LastChanged/string()" % obj.uuid)

            # Entry is not in the database
            if not changed:
                self.insert(obj)

            # Entry is in the database
            else:
                # OK: already there
                if obj.modifyTimestamp == datetime.datetime.strptime(changed[0], "%Y-%m-%d %H:%M:%S"):
                    self.log.debug("found up-to-date object index for %s" % obj.uuid)

                else:
                    self.log.debug("updating object index for %s" % obj.uuid)
                    self.update(obj)

            backend_objects.append(obj.uuid)
            del obj

        # Remove entries that are in XMLDB, but not in any other backends
        for entry in self.db.xquery("collection('objects')//o:UUID/string()"):
            if entry not in backend_objects:
                self.remove_by_uuid(entry)

        # Sync to propagate all the changes
        self.db.syncCollection('objects')

        t1 = time()
        self.log.info("processed %d objects in %ds" % (len(res), t1 - t0))
        GlobalLock.release()

    def index_active(self):
        return self._indexed

    def __handle_events(self, event):
        uuid = event.uuid

        if isinstance(event, ObjectChanged):
            uuid = event.uuid

            if event.reason == "post remove":
                self.log.debug("removing object index for %s" % uuid)
                self.remove_by_uuid(uuid)

            if event.reason == "post move":
                self.log.debug("updating object index for %s" % uuid)
                obj = GOsaObjectProxy(event.dn)
                self.update(obj)

            if event.reason == "post create":
                self.log.debug("creating object index for %s" % uuid)
                obj = GOsaObjectProxy(event.dn)
                self.insert(obj)

            if event.reason in ["post retract", "post update", "post extend"]:
                self.log.debug("updating object index for %s" % uuid)
                if not event.dn:
                    event.dn = self.db.xquery("collection('objects')/*[UUID/string() = '%s']/DN/string()" % event.uuid)

                obj = GOsaObjectProxy(event.dn)
                self.update(obj)

    def insert(self, obj):
        self.log.debug("creating object index for %s" % obj.uuid)

        # If this is the root node, add the root document
        if obj.dn == self.base:
            self.log.debug("creating object index for %s" % obj.uuid)
            self.db.addDocument('objects', 'root', self.escape(obj.asXML(True)))

        # Insert node into the root document
        else:
            pdn, inode_name = self.get_insert_parameters(obj)
            self.db.xquery("""
                insert nodes
                    %s
                after
                    collection('objects')//node()[o:DN='%s']/o:%s[last()]
                """ % (self.escape(obj.asXML(True)), pdn, inode_name))

    def remove(self, obj):
        self.remove_by_uuid(obj.uuid)

    def remove_by_uuid(self, entry):
        self.log.debug("removing object index for %s" % entry)
        self.db.xquery("delete nodes collection('objects')//node()[o:UUID/string()='%s']" % entry)

    def update(self, obj):
        # Gather information
        current = obj.asXML(True)
        saved = self.db.xquery("collection('objects')/*[o:UUID/string() = '%s']" % obj.uuid)
        if not saved:
            raise IndexException("no such object %s" % obj.uuid)

        # Convert result set into handy objects
        current = objectify.fromstring(current)
        saved = objectify.fromstring(saved[0])

        # Has the entry been moved?
        if current.DN.text != saved.DN.text:

            # Remove old entry
            self.remove_by_uuid(obj.uuid)

            # Find new parent and push 'current' to that position
            pdn, inode_name = self.get_insert_parameters(obj)
            self.db.xquery("""
                insert nodes
                    %s
                after
                    collection('objects')//node()[o:DN='%s']/o:%s[last()]
                """ % (self.escape(current), pdn, inode_name))

            # Adjust all DN entries inside of current
            res = iter(self.db.xquery("""let $doc := collection('objects')
                for $x in
                    $doc//node()[o:DN='%s']//o:DN
                return
                    ($x/../o:UUID/string(), $x/string())""" % obj.dn))
            for uuid, dn in izip(res, res):

                # No need to modify the parent - it's already done
                if dn == obj.dn:
                    continue

                # Remove parts of the old parent dn and append new pdn
                rdn = ldap.dn.dn2str(ldap.dn.str2dn(current.DN.text.encode('utf-8'), flags=ldap.DN_FORMAT_LDAPV3)[0]).decode('utf-8')

                self.db.xquery("""
                    replace node
                        collection('objects')/*[o:UUID/string() = '%s']/o:DN
                    with
                        <o:DN>%s</o:DN>
                    """ % (obj.uuid, rdn + "," + pdn))

        # Move extensions
        self.db.xquery("""
        replace node
            collection('objects')/*[o:UUID/string() = '%s']/o:Extensions
        with
            %s
        """ % (obj.uuid, etree.tostring(current.Extensions)))

        # Move attributes
        self.db.xquery("""
        replace node
            collection('objects')/*[o:UUID/string() = '%s']/o:Attributes
        with
            %s
        """ % (obj.uuid, etree.tostring(current.Attributes)))

        # Set LastChanged
        self.db.xquery("""
        replace node
            collection('objects')/*[o:UUID/string() = '%s']/o:LastChanged
        with
            <o:LastChanged>%s</o:LastChanged>
        """ % (obj.uuid, current.LastChanged.text))


    def get_insert_parameters(self, obj):
       otype = obj.get_base_type()

       # Find new parent and push 'current' to that position
       pdn = ldap.dn.dn2str(ldap.dn.str2dn(obj.dn.encode('utf-8'), flags=ldap.DN_FORMAT_LDAPV3)[1:]).decode('utf-8')
       children = self.db.xquery("collection('objects')//node()[o:DN='%s']/node()[not(name()=('DN','LastChanged','UUID','Type'))]/name()" % pdn)

       # If these are in children, remove them from pnodes
       pnodes = ['DN', 'LastChanged', 'UUID', 'Type']
       anodes = [i for i in children if i in ['Extensions','Attributes','Container']]
       children = [i for i in children if not i in ['Extensions','Attributes','Container']]

       inode_name = otype
       if not obj.get_base_type() in children:
           children.append(otype)
           children.sort()
           pnodes = pnodes + anodes + list(set(children))
           inode_name = pnodes[pnodes.index(otype) - 1]

       return pdn, inode_name

    @Command(__help__=N_("Perform a raw xquery on the collections"))
    def xquery(self, query):
        """
        Perform a raw xquery on the object database.

        ========== ==================
        Parameter  Description
        ========== ==================
        xquery     Definition of the search/action
        ========== ==================

        ``Return``: True/False
        """
        return self.db.xquery(query)

    @Command(__help__=N_("Check if an object with the given UUID exists."))
    def exists(self, uuid):
        """
        Do a database query for the given UUID and return an
        existance flag.

        ========== ==================
        Parameter  Description
        ========== ==================
        uuid       Object identifier
        ========== ==================

        ``Return``: True/False
        """
        return len(self.db.xquery("collection('objects')/*[o:UUID/string() = '%s']" % uuid)) == 1

# TODO:-to-be-revised--------------------------------------------------------------------------------------

    @Command(__help__=N_("Filter for indexed attributes and return the number of matches."))
    def count(self, base=None, scope=SCOPE_SUB, fltr=None):
        """
        Query the database using the given filter and return the number
        of matches.

        ========== ==================
        Parameter  Description
        ========== ==================
        base       Base to search on
        scope      Scope to use (BASE, ONE, SUB)
        fltr       Filter description
        ========== ==================

        Filter example:

         {
           '_and': {
             'uid': 'foo',
             'givenName': u'Klaus',
             '_or': {
               '_in': {
                 'sn': [u'Mustermann', u'Musterfrau']
               },
               '_lt': ['dateOfBirth', datetime.datetime.now()]
             }
           }
         }

        Available filter parameters:

        ============ ==================
        Parameter    Description
        ============ ==================
        [a-zA-Z0-9]+ Ordinary match condition, maps to a single value
        _and         And condition, maps to more conditions
        _or          Or condition, maps to more conditions
        _not         Not condition, inverts condition
        _gt          Check if value is greater, maps to a 2 value list
        _ge          Check if value is greater or equal, maps to a 2 value list
        _lt          Check if value is lesser, maps to a 2 value list
        _le          Check if value is lesser or equal, maps to a 2 value list
        ============ ==================

        ``Return``: Integer
        """
        if GlobalLock.exists("scan_index"):
            raise FilterException("index rebuild in progress - try again later")

        base_filter = None

        if scope == None or not scope in [SCOPE_ONE, SCOPE_BASE, SCOPE_SUB]:
            raise FilterException("invalid search scope")

        if base:
            base = self.dn2b64(base)
            if scope == SCOPE_BASE:
                base_filter = self.__index.c._dn == base

            if scope == SCOPE_ONE:
                base_filter = or_(self.__index.c._dn == base, self.__index.c._parent_dn == base)

            if scope == SCOPE_SUB:
                base_filter = or_(self.__index.c._dn == base, self.__index.c._parent_dn.like("%%,%s" % base))

        if fltr:
            if base:
                fltr = and_(base_filter, *self.__build_filter(fltr))
            else:
                fltr = self.__build_filter(fltr)

            slct = select([func.count(self.__index.c._uuid)], fltr)

        else:
            if base:
                slct = select([func.count(self.__index.c._uuid)], base_filter)
            else:
                slct = select([func.count(self.__index.c._uuid)])

        return self.__conn.execute(slct).fetchone()[0]

    @Command(__help__=N_("Filter for indexed attributes and return the matches."))
    def search(self, base=None, scope=SCOPE_SUB, fltr=None, attrs=None, begin=None, end=None, order_by=None, descending=False):
        """
        Query the database using the given filter and return the
        result set.

        ========== ==================
        Parameter  Description
        ========== ==================
        base       Base to search on
        scope      Scope to use (BASE, ONE, SUB)
        fltr       Filter description
        attrs      List of attributes the result set should contain
        begin      Offset to start returning results
        end        End offset to stop returning results
        order_by   Attribute to sort for
        descending Ascending or descending sort
        ========== ==================

        For more information on the filter format, consult the ref:`gosa.agent.objects.index.count`
        documentation.

        ``Return``: List of dicts
        """
        if GlobalLock.exists("scan_index"):
            raise FilterException("index rebuild in progress - try again later")

        base_filter = None

        if not attrs:
            ats = [self.__index]
        else:
            ats = []
            for a in attrs:
                ats.append(getattr(self.__index.c, a))

        if base:
            base = self.dn2b64(base)
            if scope == SCOPE_BASE:
                base_filter = self.__index.c._dn == base

            if scope == SCOPE_ONE:
                base_filter = or_(self.__index.c._dn == base, self.__index.c._parent_dn == base)

            if scope == SCOPE_SUB:
                base_filter = or_(self.__index.c._dn == base, self.__index.c._parent_dn.like("%%,%s" % base))

        if fltr:
            if base:
                sl = select(ats, and_(base_filter, *self.__build_filter(fltr)))
            else:
                sl = select(ats, *self.__build_filter(fltr))
        else:
            if base:
                sl = select(ats, base_filter)
            else:
                sl = select(ats)

        # Apply ordering
        if order_by:
            if descending:
                sl = sl.order_by(desc(order_by))
            else:
                sl = sl.order_by(asc(order_by))

        # Apply range
        if begin != None and end != None:
            if begin >= end:
                raise FilterException("filter range error - 'begin' is not < 'end'")

            sl = sl.offset(begin).limit(end - begin + 1)

        res = [dict(r.items()) for r in self.__conn.execute(sl).fetchall()]
        return self.__convert_lists(res)
