# -*- coding: utf-8 -*-
import MySQLdb
from gosa.common.env import Environment


class GOforgeFetcher:

    def __init__(self):
        self.env = env = Environment.getInstance()
        host = env.config.getOption("host", "fetcher-goforge",
            default="localhost")
        user = env.config.getOption("user", "fetcher-goforge",
            default="root")
        passwd = env.config.getOption("pass", "fetcher-goforge",
            default="")
        db = env.config.getOption("base", "fetcher-goforge",
            default="goforge")

        # connect to GOforge db
        self.forge_db = MySQLdb.connect(host=host,
            user=user, passwd=passwd, db=db)

    def getTickets(self, company_id):
        # prepare result
        result = []

        cursor = self.forge_db.cursor()

        try:
            # obtain GOforge internal customer id
            len = cursor.execute("""
                SELECT customer_id
                FROM customer
                WHERE customer_unique_ldap_attribute = %s""",
                (company_id,))
            row = cursor.fetchone()

            # if entry for company exists ...
            if len == 1:
                # fetch tickets from database
                len = cursor.execute("""
                    SELECT bug.bug_id, bug.summary,
                        bug.group_id, user.user_name
                    FROM bug, user
                    WHERE bug.status_id = 1
                        AND bug.assigned_to = user.user_id
                        AND bug.customer_id = %s
                    LIMIT 29;""",
                    (row[0],))

                rows = cursor.fetchall()

                # put results into dictionary
                for row in rows:
                    result.append({'id': row[0],
                        'summary': row[1],
                        'priority': row[2],
                        'assigned': row[3]})

        finally:
            cursor.close()

        return result
