import re
import json
import ldap


#TODO: Think about ldap relations, how to store and load objects.
#TODO: What about object groups, to be able to inlcude clients?
#TODO: Groups are not supported yet


"""
This is a collection of classes that can manager Access control lists.

AclSet      - Is a container class for Acl objects. An AclSet-object can be attached
              to ldap organizationalUnits to restrict permissions for a set of
              users.
Acl         - This class represents a single ACL rule, Acl-objects can be
              bundled in an AclSet object.

AclResoler  - This class is used to manage all Acl- and AclSets objects.

"""


class AclSet(list):
    """
    This is a container for ACL entries.
    """
    location = None

    def __init__(self, location):
        self.location = location

    def get_location(self):
        return(self.location)

    def add(self, item):
        """
        Adds a new acl object to this aclSet.
        """
        if not isinstance(item, Acl):
            raise TypeError('item is not of type %s' % Acl)

        if item.priority == None:
            item.priority = len(self)

        self.append(item)

        # Sort Acl items by id
        sorted(self, key=lambda item: item.priority)


class AclRole(list):
    """
    This is a container for ACL entries that should act like an acl role.
    """
    name = None
    priority = None

    def __init__(self, name):
        self.name = name

    def add(self, item):
        """
        Adds a new acl object to this aclSet.
        """
        if not isinstance(item, Acl):
            raise TypeError('item is not of type %s' % Acl)

        if item.priority == None:
            item.priority = len(self)

        self.append(item)

        # Sort Acl items by id
        sorted(self, key=lambda item: item.priority)

class Acl(object):
    """
    The Acl class contains list of action for a set of members.
    These Acl classes can then be bundled and attached to a ldap base using
    the aclSet class.
    """
    priority = None

    ONE = 1
    SUB = 2
    PSUB = 3
    RESET = 4

    members = None
    actions = None
    scope = None

    uses_role = False
    role = None

    def __init__(self, scope=None, role=None):

        if scope == None:
            scope = Acl.SUB

        if scope not in (Acl.ONE, Acl.SUB, Acl.PSUB, Acl.RESET):
            raise(Exception("Invalid ACL type given"))

        self.scope = scope
        self.actions = []
        self.locations = []
        self.members = []

        if role:
            self.use_role(role)

    def use_role(self, role):
        self.uses_role = True
        self.role = role.name

    def add_member(self, member):
        """
        Adds a new member to this acl.
        """
        if type(member) != unicode:
            raise(Exception("Member should be of type str!"))
        self.members.append(member)

    def add_members(self, members):
        """
        Adds a list of new members to this acl.
        """
        if type(members) != list or len(members) == 0:
            print  members
            raise(Exception("Requires a list of members!"))

        for member in members:
            self.add_member(member)

    def add_action(self, target, acls, options):
        """
        Adds a new action to this acl.
        """
        if self.uses_role:
            raise Exception("Acl classes that use a role cannot define"
                   " additional costum acls!")

        acl = {
                'target': target,
                'acls': acls,
                'options': options}
        self.actions.append(acl)

    def get_members(self):
        """
        Returns the list of members this ACL is valid for.
        """
        return(self.member)

    def match(self, user, action, acls, options={}, skip_user_check=False):
        """
        Check of the requested user, action and the action options match this
        acl-object.
        """
        if user in self.members or skip_user_check:

            if self.uses_role:
                r = AclResolver.get_instance()
                print "ACL: Checking ACL role entries for role: '%s'!" % self.role
                for acl in r.acl_roles[self.role]:
                    if acl.match(user, action, acls, options,skip_user_check=True):
                        print "ACL:  ACL role entry matched!"
                        return True
            else:
                for act in self.actions:

                    # check for # and * placeholders
                    test_act = re.escape(act['target'])
                    test_act = re.sub(r'(^|\\.)(\\\*)(\\.|$)', '\\1.*\\3', test_act)
                    test_act = re.sub(r'(^|\\.)(\\#)(\\.|$)', '\\1[^\.]*\\3', test_act)

                    # Check if the requested-action matches the acl-action.
                    if not re.match(test_act, action):
                        continue

                    # Check if the required permissions are allowed.
                    if (set(acls) & set(act['acls'])) != set(acls):
                        continue

                    # Check if all required options are given
                    for entry in act['options']:

                        # Check for missing options
                        if entry not in options:
                            print "ACL:   Option '%s' is missing" % entry
                            continue

                        # Simply match string options.
                        if type(act['options'][entry]) == str and not re.match(act['options'][entry], options[entry]):
                            print "ACL:   Option '%s' with value '%s' does not match '%s'!" % (entry,
                                    act['options'][entry], options[entry])
                            continue

                        # Simply match string options.
                        elif act['options'][entry] != options[entry]:
                            print "ACL:   Option '%s' with value '%s' does not match '%s'!" % (entry,
                                    act['options'][entry], options[entry])
                            continue

                    # The acl rule matched!
                    return(True)

        # Nothing matched!
        return False

    def get_type(self):
        """
        Returns the type of an ACL.
        SUB, PSUB, RESET, ...
        """
        return(self.scope)


class AclRoleEntry(Acl):

    def __init__(self, scope=None, role=None):
        super(AclRoleEntry, self).__init__(scope=scope)

    def add_member(self, member):
        """
        Adds a new member to this acl.
        """
        raise Exception("Role Acls do not support direct members")


class AclResolver(object):
    instance = None
    acl_sets = None
    acl_roles = None

    def __init__(self):

        self.acl_sets = []
        self.acl_roles = {}

        # from config later on:
        self.base = "dc=gonicus,dc=de"
        self.acl_file = "agent.acl"

        self.load_from_file()

    def add_acl_set(self, acl):
        """
        Adds an AclSet object to the list of active-acl rules.
        """
        self.acl_sets.append(acl)

    def add_acl_role(self, acl):
        """
        Adds an AclRole object to the list of active-acl roles.
        """
        self.acl_roles[acl.name] = acl

    def load_from_file(self):
        """
        Save acl definition into a file
        """
        self.acl_sets = []

        acl_scope_map = {}
        acl_scope_map['one'] = Acl.ONE
        acl_scope_map['sub'] = Acl.SUB
        acl_scope_map['psub']= Acl.PSUB
        acl_scope_map['reset']= Acl.RESET

        try:
            data = json.loads(open(self.acl_file).read())

            # Add AclRoles
            for name in data['roles']:

                acl_entry = data['roles'][name]
                role = AclRole(name)
                acl = Acl(acl_scope_map[acl_entry['scope']])

                for action in acl_entry['actions']:
                    acl.add_action(action['target'], action['acls'], action['options'])

                role.add(acl)
                self.add_acl_role(role)

            # Add AclSets
            for location in data['acl']:

                # The Acl defintion is based on an acl role.
                for acls_data in data['acl'][location]:

                    acls = AclSet(location)
                    for acl_entry in acls_data['acls']:

                        if 'role' in acl_entry:
                            acl_rule_set = self.acl_roles[acl_entry['role']]
                            acl = Acl(role=acl_rule_set)
                            acl.add_members(acl_entry['members'])
                            acls.add(acl)
                        else:
                            acl = Acl(acl_scope_map[acl_entry['scope']])
                            acl.add_members(acl_entry['members'])

                            for action in acl_entry['actions']:
                                acl.add_action(action['target'], action['acls'], action['options'])

                            acls.add(acl)
                    self.add_acl_set(acls)

        except IOError:
            return {}

    def save_to_file(self):
        """
        Save acl definition into a file
        """
        ret = {'acl': {}, 'roles':  {}}

        acl_scope_map = {}
        acl_scope_map[Acl.ONE] = 'one'
        acl_scope_map[Acl.SUB] = 'sub'
        acl_scope_map[Acl.PSUB] = 'psub'
        acl_scope_map[Acl.RESET] = 'reset'

        # Save AclSets
        for acl_set in self.acl_sets:

            # Prepare lists
            if acl_set.location not in ret['acl']:
                ret['acl'][acl_set.location] = []

            acls = []
            for acl in acl_set:

                if acl.uses_role:
                    entry = {'role': acl.role,
                            'members': acl.members
                            }
                else:
                    entry = {'actions': acl.actions,
                            'members': acl.members,
                            'priority': acl.priority,
                            'scope': acl_scope_map[acl.scope]
                            }

                acls.append(entry)
            ret['acl'][acl_set.location].append({'acls': acls})

        # Save AclRoles
        for role_name in self.acl_roles:
            ret['roles'][role_name] = []
            for acl in self.acl_roles[role_name]:
                entry = {'actions': acl.actions,
                         'priority': acl.priority,
                         'scope': acl_scope_map[acl.scope]}
                ret['roles'][role_name] = entry

        with open(self.acl_file, 'w') as f:
            import json
            json.dump(ret, f, indent=2)


    def get_permissions(self, user, location, action, acls, options={}):
        """
        Check permissions for a given user and a location.
        """

        # Collect all acls matching the where statement
        allowed = False
        reset = False

        print "ACL: Checking acl for %s/%s/%s" % (user, location, str(action))

        # Remove the first part of the dn, until we reach the ldap base.
        while self.base in location:

            # Check acls for each acl set.
            for acl_set in self.acl_sets:

                # Skip acls that do not match the current ldap location.
                if location != acl_set.location:
                    continue

                # Check ACls
                for acl in acl_set:
                    if acl.match(user, action, acls, options):
                        print "ACL: Found matching acl in '%s'!" % location
                        if acl.get_type() == Acl.RESET:
                            print "ACL:  Acl reset for action '%s'!" % (action)
                            reset = True
                        elif acl.get_type() == Acl.PSUB:
                            print "ACL:  Found permanent acl for action '%s'!" % (action)
                            return True
                        elif acl.get_type() in (Acl.SUB, ) and not reset:
                            print "ACL:  Found acl for action '%s'!" % (action)
                            return True

            # Remove the first part of the dn
            location = ','.join(ldap.dn.explode_dn(location)[1::])

        return(allowed)

    @staticmethod
    def get_instance():
        if not AclResolver.instance:
            AclResolver.instance = AclResolver()

        return AclResolver.instance
