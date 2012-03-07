from search_wrapper import SearchWrapper
from pprint import pprint
import time

query1 = """
SELECT User.sn, SambaDomain.*, User.Type
BASE SambaDomain SUB "dc=gonicus,dc=de"
BASE User SUB "dc=gonicus,dc=de"
WHERE (SambaDomain.sambaDomainName = User.sambaDomainName)
ORDER BY User.sn, User.givenName DESC
"""

query2 = """
SELECT User.sn, User.givenName, User.DN
BASE User BASE "cn=Sebastian Denz,ou=people,ou=Technik,dc=gonicus,dc=de"
ORDER BY User.sn, User.givenName DESC
"""

query3 = """
SELECT User.sn, SambaDomain.*, User.Type
BASE SambaDomain SUB "dc=gonicus,dc=de"
BASE User SUB "dc=gonicus,dc=de"
WHERE NOT(SambaDomain.sambaDomainName = User.sambaDomainName)
ORDER BY User.sn, User.givenName DESC
"""

query4 = """
SELECT User.sn, User.givenName, User.DN
BASE User SUB "dc=gonicus,dc=de"
"""

sw = SearchWrapper.get_instance()
while(True):
    time.sleep(1)
    pprint(len(sw.execute(query4)))
