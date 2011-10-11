# -*- coding: utf-8 -*-
import uuid
import datetime
from gosa.agent.objects.index import ObjectIndex

ie = ObjectIndex()

#u1 = str(uuid.uuid4())
#ie.insert(u1, dn=u"cn=Cajus Pollmeier,ou=people,ou=Technik,dc=gonicus,dc=de", sn=u"Pollmeier", givenName=u"Cajus", uid="cajus", mail=['cajus@debian.org', 'cajus@naasa.net', 'pollmeier@gonicus.de'], _lastChanged=datetime.datetime.now())
#print ie.exists(u1)
#ie.update(u1, uid="lorenz")

#fltr = {}
fltr = {'uid': '*us'}
#fltr = {'mail': 'cajus@*'}
#fltr = {'_and': {'uid': 'lorenz', 'givenName': u'Cajus', '_or': {'sn': u'ding', 'sn_2': u'dong', '_gt': ['dob', datetime.datetime.now()]}}}
#fltr = {'_and': {'uid': 'lorenz', 'givenName': u'Cajus', '_or': {'_in': {'sn': [u'ding', u'dong']}, '_gt': ['dob', datetime.datetime.now()]}}}
print "Count:", ie.count(fltr)
for e in ie.search(fltr, attrs=['sn', 'givenName', 'uid'], begin=0, end=10):
    print e

#ie.remove(u1)
#print ie.exists(u1)

#ie.refresh()
