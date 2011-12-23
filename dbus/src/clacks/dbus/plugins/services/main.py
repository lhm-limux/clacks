# -*- coding: utf-8 -*-
import dbus.service
import logging
from os.path import basename
from clacks.common import Environment
from clacks.common.components import Plugin
from clacks.dbus import get_system_bus
import re
import subprocess


class ServiceException(Exception):
    """
    Exception thrown for general service failures.
    """
    pass

class NoSuchServiceException(ServiceException):
    """
    Exception thrown for unknown services
    """
    pass

class DBusUnixServiceHandler(dbus.service.Object, Plugin):
    """
    DBus plugin which allows to administrate the client and its services.
    """

    log = None
    env = None
    svc_command = None

    def __init__(self):
        conn = get_system_bus()
        dbus.service.Object.__init__(self, conn, '/org/clacks/service')
        self.env = Environment.getInstance()
        self.svc_command = self.env.config.get("unix.service-command", default="/usr/sbin/service")
        self.log = logging.getLogger(__name__)

    def _validate(self, name, action=None):
        """
        Checks if the requested service exists and if it provides the requested action.
        """
        services = self.get_services()
        if not name in services:
            raise ServiceException("unknown service %s" % name)

        if action and not action in services[name]['actions']:
            raise ServiceException("action '%s' not supported for service %s" % (action, name))

        return services[name]

    @dbus.service.method('org.clacks', out_signature='i')
    def service_get_runlevel(self):
        """
        Returns the current runlevel of the clacks-client.
        """

        # Call 'who -r' and parse the return value to get the run-level
        # run-level 2  Dec 19 01:21                   last=S
        process = subprocess.Popen(["who","-r"], env={'LC_ALL': 'C'}, \
                shell=False, stdout=subprocess.PIPE,  stderr=subprocess.PIPE)
        ret = process.communicate()
        runlevel = re.sub("^run-level[ ]*([0-9]*).*$", "\\1", ret[0].strip())
        return int(runlevel)

    @dbus.service.method('org.clacks', in_signature='i', out_signature='i')
    def service_set_runlevel(self, level):
        """
        Sets a new runlevel for the clacks-client
        """
        self.log.debug("client runlevel set toggled to: %s" % (str(level)))
        process = subprocess.Popen(["telinit","%s" % (str(level))], shell=False, stdout=subprocess.PIPE,  stderr=subprocess.PIPE)
        ret = process.communicate()
        return process.returncode

    @dbus.service.method('org.clacks', in_signature='s', out_signature='b')
    def service_start(self, name):
        """
        Starts the given service, if it is not running.
        """
        service = self._validate(name, "start")

        # Skip if running
        if "True" in service['running']:
            return True

        # Execute call
        self.log.debug("starting service %s" % (name))
        return subprocess.call([self.svc_command, name, 'start']) == 0

    @dbus.service.method('org.clacks', in_signature='s', out_signature='b')
    def service_stop(self, name):
        """
        Stop the given service, if it is running.
        """
        service = self._validate(name, "stop")

        # Skip if running
        if "True" not in service['running']:
            return True

        # Execute call
        self.log.debug("stopping service %s" % (name))
        return subprocess.call([self.svc_command, name, 'stop']) == 0

    @dbus.service.method('org.clacks', in_signature='s', out_signature='b')
    def service_restart(self, name):
        """
        Restart the given service.
        """
        service = self._validate(name, "restart")
        self.log.debug("restarting service %s" % (name))
        return subprocess.call([self.svc_command, name, 'restart']) == 0

    @dbus.service.method('org.clacks', in_signature='s', out_signature='b')
    def service_reload(self, name):
        """
        Reloads the given service.
        """
        service = self._validate(name, "reload")

        # Skip if running
        if "True" not in service['running']:
            return False

        self.log.debug("reloading service %s" % (name))
        return subprocess.call([self.svc_command, name, 'reload']) == 0

    @dbus.service.method('org.clacks', in_signature='s', out_signature='a{sv}')
    def get_service(self, name):
        """
        Returns status information for the given service.
        """
        services = self.get_services()
        if not name in services:
            raise NoSuchServiceException("unknown service %s" % name)

        return services[name]

    @dbus.service.method('org.clacks', out_signature='a{sa{sas}}')
    def get_services(self):
        """
        Returns status information for all services.
        """

        # Get the current runlevel and then check for registered services using
        #  run-parts --test --regex=^S* /etc/rc<level>.d
        level = self.get_runlevel()
        process = subprocess.Popen(["run-parts", "--test", "--regex=^S*", "/etc/rc%s.d" % (str(level))],
                shell=False, stdout=subprocess.PIPE,  stderr=subprocess.PIPE, env={'LC_ALL': 'C'})
        ret = process.communicate()

        # Parse results and strip out path infos and S[0-9] prefix
        services = {}
        for entry in ret[0].split("\n"):
            sname = re.sub("^S[0-9]*", "", basename(entry))

            # Do not add empty service names
            if not sname:
                continue

            # Try to detect the service actions we can perform (e.g. start/stop)
            _svcs = subprocess.Popen([self.svc_command, sname], env={'LC_ALL': 'C'},
                    stderr=subprocess.PIPE, stdout=subprocess.PIPE).communicate()
            content = _svcs[0] + _svcs[1]

            # Search useable service actions in the result
            res = re.findall("(([a-zA-Z\-]*)\|)", content, re.MULTILINE) + re.findall("(\|([a-zA-Z\-]*))", content, re.MULTILINE)
            actions = set()
            for entry in res:
                actions |= set([entry[1]],)

            # Create a service entry for the result
            services[sname] = {'actions': list(actions), 'running': ['None'], 'icon': ['']}

            # Check if the service running by calling 'status', if available
            if 'status' in services[sname]['actions']:
                _svcs = subprocess.Popen([self.svc_command, sname, 'status'], env={'LC_ALL': 'C'},
                        stderr=subprocess.PIPE, stdout=subprocess.PIPE).communicate()

                # Search for a string which tells us that the service is running
                # Be careful some infos return values like this:
                #  * isn't running | is not running | not running | failed (running) ...
                state = re.search('is running', _svcs[0]+_svcs[1], flags=re.IGNORECASE) != None
                services[sname]['running'] = ["True"] if(state) else ["False"]

        return services