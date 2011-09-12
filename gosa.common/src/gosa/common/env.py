# -*- coding: utf-8 -*-
"""
The environment module encapsulates the access of all
central information like logging, configuration management
and threads.

You can import it to your own code like this::

   >>> from gosa.common import Environment
   >>> env = Environment.getInstance()

--------
"""
import config
import platform
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy import *
from gosa.common.utils import dmi_system
import gosa.common.log


class Environment:
    """
    The global information container, used as a singleton.
    """
    threads = []
    locks = []
    id = None
    config = None
    log = None
    domain = ""
    config = None
    noargs = False
    __instance = None
    __db = {}

    def __init__(self):
        # Load configuration
        self.config = config.Config(config=Environment.config,  noargs=Environment.noargs)
        self.log = gosa.common.log.getLogger(
                logtype=self.config.get("core.log"),
                logfile=self.config.get("core.logfile"),
                loglevel=self.config.get("core.loglevel"))

        self.id = platform.node()
        self.log.info("server id %s" % self.id)

        # Dump configuration
        if self.config.get("core.loglevel") == "DEBUG":
            self.log.debug("configuration dump:")

            for section in self.config.getSections():
                self.log.debug("[%s]" % section)
                items = self.config.getOptions(section)

                for item in items:
                    self.log.debug("%s = %s" % (item, items[item]))

            self.log.debug("end of configuration dump")

        # Initialized
        self.domain = self.config.get("core.domain", default="org.gosa")
        self.uuid = self.config.get("core.id", default=None)
        if not self.uuid:
            self.log.warning("system has no id - falling back to configured hardware uuid")
            self.uuid = dmi_system("uuid")

            if not self.uuid:
                self.log.error("system has no id - please configure one in the core section")
                raise Exception("No system id found")

        self.active = True

    def getDatabaseEngine(self, section, key="database"):
        """
        Return a database engine from the registry.

        ========= ============
        Parameter Description
        ========= ============
        section   name of the configuration section where the config is placed.
        key       optional value for the key where the database information is stored, defaults to *database*.
        ========= ============

        ``Return``: database engine
        """
        index = "%s.%s" % (section, key)

        if not index in self.__db:
            self.__db[index] = create_engine(self.config.get(index),
                    pool_size=40, pool_recycle=120)

        return self.__db[index]

    def getDatabaseSession(self, section, key="database"):
        """
        Return a database session from the pool.

        ========= ============
        Parameter Description
        ========= ============
        section   name of the configuration section where the config is placed.
        key       optional value for the key where the database information is stored, defaults to *database*.
        ========= ============

        ``Return``: database session
        """
        sql = self.getDatabaseEngine(section, key)
        session = scoped_session(sessionmaker(autoflush=True))
        session.configure(bind=sql)
        return session()

    @staticmethod
    def getInstance():
        """
        Act like a singleton and return the
        :class:`gosa.common.env.Environment` instance.

        ``Return``: :class:`gosa.common.env.Environment`
        """
        if not Environment.__instance:
            Environment.__instance = Environment()
        return Environment.__instance
