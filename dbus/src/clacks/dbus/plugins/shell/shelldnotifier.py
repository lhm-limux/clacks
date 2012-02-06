"""
This plugin is part of the shell extension module of clacks-dbus.

It starts a Thread and uses inotify to register itself to the kernel to receive
events about changes made in the shelld directory.

"""

import re
import pyinotify
import logging
from clacks.common import Environment


class ShellDNotifier(pyinotify.ProcessEvent):
    """
    It monitors the clacks shell extension directory usually '/etc/clacks/shell.d'
    for modifications and executes the given callback if a modification was detected.

    =========== =====================
    Key         Desc
    =========== =====================
    path        The path to check modification for
    regex       A regular expression of filenames that we are interested in
    callback    A function to call, once we detected a modification.
    =========== =====================

    """
    path = None
    callback = None
    regex = None

    def __init__(self, path, regex, callback):

        # Initialize the plugin and set path
        self.bp = self.path = path
        self.regex = regex
        self.callback = callback
        self.env = Environment.getInstance()
        self.log = logging.getLogger(__name__)

        # Start the files ystem surveillance thread now
        self.__start()

    def __start(self):
        """
        Starts the survailance. This is automatically called in the constructor.
        """
        wm = pyinotify.WatchManager()
        wm.add_watch(self.path, pyinotify.IN_ATTRIB | pyinotify.IN_MODIFY | pyinotify.IN_DELETE | pyinotify.IN_MOVED_TO, rec=True, auto_add=True)
        notifier = pyinotify.ThreadedNotifier(wm, self)
        notifier.daemon = True
        notifier.start()

    def process_IN_MOVED_TO(self, event):
        """
        Method to process moved files
        """
        self.__handle(event.pathname)

    def process_IN_ATTRIB(self, event):
        """
        Method to process attribute modification events
        """
        self.__handle(event.pathname)

    def process_IN_MODIFY(self, event):
        """
        Method to process file modifications events
        """
        self.__handle(event.pathname)

    def process_IN_DELETE(self, event):
        """
        Method to process file delete events
        """
        self.__handle(event.pathname)

    def __handle(self, path):
        """
        This method call the 'callback' method once it receives a
        filename that matches the 'regex' given in 'init'.
        """
        shortname = path[len(self.path) +1:]
        if re.match(self.regex, shortname):

            # Use the callback method to announce the new change event
            self.callback(shortname)
