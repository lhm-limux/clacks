# -*- coding: utf-8 -*-
from clacks.agent.objects.types import AttributeType


class SambaLogonHoursAttribute(AttributeType):
    """
    This is a special object-attribute-type for sambaLogonHours.

    This call can convert sambaLogonHours to a UnicodeString and vice versa.
    It is used in the samba-object definition file.
    """

    __alias__ = "SambaLogonHours"

    @classmethod
    def values_match(cls, value1, value2):
        return(str(value1) == str(value2))

    @classmethod
    def is_valid_value(cls, value):

        if value and len(value) and type(value[0]) == dict:

            # Check if we've got a dict with values for all seven week days.
            if value[0].keys() != range(0,7):
                return False

            # Check if each week day contains 24 values.
            for i in range(0,7):
                if type(value[0][i]) != str or len(value[0][i]) != 24 or len(set(value[0][i]) - set('01')):
                    return False

        return True

    @classmethod
    def _convert_to_unicodestring(cls, value):
        """
        This method is a converter used when values gets read from or written to the backend.

        Converts the 'SambaLogonHours' object-type into a 'UnicodeString'-object.
        """
        if len(value):

            # Combine the binary strings
            val = value[0]
            lstr = ""
            for day in range(0,7):
                lstr += val[day]

            # New reverse every 8 bit part, and toggle high- and low-tuple (4Bits)
            new = ""
            for i in range(0, 21):
                n = lstr[i*8:((i+1)*8)]
                n = n[0:4] + n[4:]
                n = n[::-1]
                n = str(hex(int( n, 2)))[2::].rjust(2,'0')
                new += n
            value = [new.upper()]

        return(value)

    @classmethod
    def _convert_from_unicodestring(cls, value):
        """
        This method is a converter used when values gets read from or written to the backend.

        Converts a 'UnicodeString' attribute into the 'SambaLogonHours' object-type.
        """

        if len(value):

            # Convert each hex-pair into binary values.
            # Then reverse the binary result and switch high and low pairs.
            res = {}
            value = value[0]
            lstr = ""
            for i in range(0,42,2):
                n = (bin(int(value[i:i+2], 16))[2::]).rjust(8, '0')
                n = n[::-1]
                lstr += n[0:4] + n[4:]

            # Parse result into more readable value
            for day in range(0,7):
                res[day] = lstr[(day*24):((day+1)*24)]
            value = [res]

        return(value)
