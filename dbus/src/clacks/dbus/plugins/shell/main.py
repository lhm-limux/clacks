"""

Clacks D-Bus Shell plugin
^^^^^^^^^^^^^^^^^^^^^^^^^


The clacks-dbus shell plugin allows to execute shell scripts
on the client side with root privileges.

Scripts can be executed like this:

>>> clacksh
>>>  Suche Dienstanbieter...
>>> ...
>>> clientDispatch("49cb1287-db4b-4ddf-bc28-5f4743eac594", "dbus_shell_list")
>>> [u'script1.sh', u'test.py']

>>> clientDispatch("49cb1287-db4b-4ddf-bc28-5f4743eac594", "dbus_shell_exec", "script1.sh", ['param1', 'param2'])
>>> {u'code': 0, u'stderr': u'', u'stdout': u'result'}


Creating scripts
^^^^^^^^^^^^^^^^

Create a new executable file in ``/etc/clacks/shell.d`` and ensure that its name match the
following expression ``^[a-zA-Z0-9][a-zA-Z0-9_\.]*$``.

The script can contain any programming language you want, it just has to be executable
and has to act on the parameter '-- --signature', see below.


The parameter -- --signature
.........................

Each script has to return a signature when it is used with the parameter '-- --signature'.
This is required to populate the method to the clacks-dbus process.

A signature is a json string describing what is required and what is returned by the
script. See `dbus-python tutorial from freedesktop.org <http://dbus.freedesktop.org/doc/dbus-python/doc/tutorial.html>`_
for details on signatures.

Usually you'll pass strings to the script and it will return a string again:

>>> {"in": [{"param1": "s"},{"param2": "s"}], "out": "s"}


Example script
..............

Here is an example script:

>>>   #!/bin/bash
>>>   detail="-1"
>>>   dir=$HOME
>>>
>>>   usage() {
>>>       echo $(basename $0) [--detail] [--directory DIR]
>>>       exit 0
>>>   }
>>>
>>>   set -- `getopt -n$0 -u -a --longoptions="signature detail directory:" "h" "$@"` || usage
>>>   [ $# -eq 0 ] && usage
>>>
>>>   while [ $# -gt 0 ]
>>>   do
>>>       case "$1" in
>>>          --signature)
>>>              echo '{"in": [{"detail": "b"},{"directory": "s"}], "out": "s"}'
>>>              exit 0
>>>              ;;
>>>          --detail)
>>>              detail="-la"
>>>              ;;
>>>          --directory)
>>>              dir=$2
>>>              shift
>>>              ;;
>>>          -h)        usage;;
>>>          --)        shift;break;;
>>>          -*)        usage;;
>>>          *)         break;;
>>>       esac
>>>       shift
>>>   done

"""

import re
import os
import dbus.service
import logging
from clacks.dbus.plugins.shell.shelldnotifier import ShellDNotifier
from subprocess import Popen, PIPE
from clacks.common import Environment
from clacks.common.components import Plugin
from clacks.dbus import get_system_bus
from json import loads


class DBusShellException(Exception):
    """
    Exception thrown for generic errors
    """
    pass


class NoSuchScriptException(DBusShellException):
    """
    Exception thrown for unknown scripts
    """
    pass


class DBusShellHandler(dbus.service.Object, Plugin):
    """
    The DBus shell handler exports shell scripts to the DBus.

    Scripts placed in '/etc/clacks/shell.d' can then be executed using the
    'shell_exec()' method.

    Exported scripts can be listed using the 'shell_list()' method.

    e.g.
        print proxy.clientDispatch("<clientUUID>", "dbus_shell_exec", "myScript.sh", [])

    (The 'dbus_' prefix in the above example was added by the clacks-client dbus-proxy
    plugin to mark exported dbus methods - See clacks-client proxy  plugin for details)
    """

    # The path were scripts were read from.
    script_path = None
    log = None
    file_regex = "^[a-zA-Z0-9][a-zA-Z0-9_\.]*$"

    def __init__(self):
        self.scripts = {}
        conn = get_system_bus()
        dbus.service.Object.__init__(self, conn, '/org/clacks/shell')
        self.env = Environment.getInstance()
        self.log = logging.getLogger(__name__)
        self.script_path = self.env.config.get("dbus.script_path", "/etc/clacks/shell.d").strip("'\"")
        ShellDNotifier(self.script_path, self.file_regex, self.__notifier_callback)

        # Intitially load all signatures
        self.__notifier_callback()

    @dbus.service.signal('org.clacks', signature='s')
    def signatureChanged(self, filename):
        pass

    def __notifier_callback(self, filename = None):
        """
        This method reads all scripts found in the 'dbus.script_path' and
        exports them as callable dbus-method.
        """

        # Check if we've the required permissions to access the shell.d directory
        if os.path.exists(self.script_path):

            # locate files in /etc/clacks/shell.d and find those matching
            if filename == None:
                self.scripts = {}
                path = self.script_path
                for filename in [n for n in os.listdir(path)]:
                    self._reload_signature(filename)
            else:

                 # Get the script path and try to load the signatures
                 self._reload_signature(filename)

            self.log.info("registered '%s' D-Bus shell script(s)" % (len(self.scripts.keys())))
            self.log.debug("registered script(s): %s " % (", ".join(self.scripts.keys())))

            # Now send the event
            self.signatureChanged(filename)
        else:
            self.log.debug("the D-Bus shell script path '%s' does not exists! " % (self.script_path,))

    def _reload_signature(self, filename = None):
        """
        #TODO
        """

        # locate files in /etc/clacks/shell.d and find those matching
        path = self.script_path
        filepath = (os.path.join(path, filename))
        if not re.match(self.file_regex, filename):
            self.log.debug("skipped registering D-Bus shell script '%s', non-conform filename" % (filename))
        else:
            if os.access(filepath, os.X_OK):
                data = self._parse_shell_script(filepath)
                if data:
                    self.scripts[data[0]] = data
                    self.log.debug("registered D-Bus shell script '%s' signatures is: %s" % (data[0], data[1]))
            else:
                self.log.debug("skipped registering D-Bus shell script '%s', it is not executable" % (filepath))

    def _parse_shell_script(self, path):
        """
        This method executes the given script (path) with the parameter
        '--signature' to receive the scripts signatur.

        It returns a tuple containing all found agruments and their type.
        """

        # Call the script with the --signature parameter
        scall = Popen([path, '--signature'], stdout=PIPE, stderr=PIPE)
        scall.wait()

        # Check returncode of the script call.
        if scall.returncode != 0:
            self.log.info("failed to read signature from D-Bus shell script '%s' (%s) " % (path, scall.stderr.read()))

        # Check if we can read the returned signature.
        sig = {}
        try:
            sig = loads(scall.stdout.read())
            # Signature was readable, now check if we got everything we need
            if not(('in' in sig and type(sig['in']) == list) or 'in' not in sig):
                self.log.debug("failed to undertand in-signature of D-Bus shell script '%s'" % (path))
            elif 'out' not in sig or type(sig['out']) not in [str, unicode]:
                self.log.debug("failed to undertand out-signature of D-Bus shell script '%s'" % (path))
            else:
                return (os.path.basename(path), sig)
        except ValueError:
            self.log.debug("failed to undertand signature of D-Bus shell script '%s'" % (path))
        return None


    @dbus.service.method('org.clacks', in_signature='', out_signature='av')
    def shell_list(self):
        """
        Returns all availabe scripts and their signatures.
        """
        return self.scripts

    @dbus.service.method('org.clacks', in_signature='sas', out_signature='a{sv}')
    def shell_exec(self, cmd, args):
        """
        Executes a shell command and returns the result with its return code
        stderr and stdout strings.
        """
        # Check if the given script exists
        if cmd not in self.scripts:
            raise NoSuchScriptException("unknown service %s" % cmd)

        # Execute the script and return the results
        args = map(lambda x: str(x), [os.path.join(self.script_path, cmd)] + args)
        res = Popen(args, stdout=PIPE, stderr=PIPE)
        res.wait()
        return ({'code': res.returncode,
                'stdout': res.stdout.read(),
                'stderr': res.stderr.read()})
