# -*- coding: utf-8 -*-
import gettext
from pkg_resources import resource_filename #@UnresolvedImport
from clacks.common.components import PluginRegistry
from clacks.agent.objects.comparator import ElementComparator

# Include locales
t = gettext.translation('messages', resource_filename("clacks.agent", "locale"), fallback=True)
_ = t.ugettext


class IsValidSambaDomainName(ElementComparator):
    """
    Validates a given sambaDomainName.
    """

    def __init__(self, obj):
        super(IsValidSambaDomainName, self).__init__()

    def process(self, all_props, key, value):
        domain = value[0]
        errors = []
        index = PluginRegistry.getInstance("ObjectIndex")

        res = index.search({'_type': 'SambaDomain', 'sambaDomainName': domain},
            {'_uuid': 1})

        if res.count():
            return True, errors

        errors.append(_("The given sambaDomainName '%s' does not exists!") % value[0])
        return False, errors
