from inspect import getargspec

# Global command types
NORMAL = 1
FIRSTRESULT = 2
CUMULATIVE = 4


def Command(**d_kwargs):
    """
    This is the Command decorator. It adds properties based on its
    parameters to the function attributes::

      >>> @Command(needsQueue= False, type= NORMAL)
      >>> def hello():
      ...

    ========== ============
    Parameter  Description
    ========== ============
    needsQueue indicates if the decorated function needs a queue parameter
    type       describes the function type
    ========== ============

    Function types can be:

    * **NORMAL** (default)

      The decorated function will be called as if it is local. Which
      node will answer this request is not important.

    * **FIRSTRESULT**

      Some functionality may be distributed on several nodes with
      several information. FIRSTRESULT iterates thru all nodes which
      provide the decorated function and return on first success.

    * **CUMULATIVE**

      Some functionality may be distributed on several nodes with
      several information. CUMULATIVE iterates thru all nodes which
      provide the decorated function and returns the combined result.
    """
    def decorate(f):
        setattr(f, 'isCommand', True)
        for k in d_kwargs:
            setattr(f, k, d_kwargs[k])

        # Tweak docstrings
        doc = getattr(f, '__doc__')
        if doc:
            lines = map(lambda x: x.lstrip(' '), doc.split('\n'))
            try:
                hlp = getattr(f, '__help__')
            except:
                hlp = "no help available"
            name = getattr(f, '__name__')
            setattr(f, '__doc__', ".. command:: %s\n\n    %s\n\n.. note::\n    **This method will be exported by the CommandRegistry.**\n\n%s" % (name, hlp, "\n".join(lines)))

        return f

    return decorate


def NamedArgs(d_collector=None, **d_kwargs):
    """
    The *NamedArgs* decorator is used to transfer a dictionary parameter named
    by *d_collector* to the ordinary *kwargs* following this keyword.

    =========== ============
    Parameter   Description
    =========== ============
    d_collector Name of the dict container
    =========== ============

    Example::

        >>> @NamedArgs('m_hash')
        ... def getArchitectures(self, m_hash=None, distribution=None, release=None):

    This will transfer a JSON call like::

        >>> getArchitectures({'release': 'squeeze/1.0'})

    to be::

        >>> getArchitectures(release='squeeze/1.0')
    """
    def decorate(f):
        d_args = getargspec(f).args
        d_index = d_args.index(d_collector)

        def new_f(*args, **kwargs):
            # Transfer
            if len(args) > d_index:
                for d_arg in [d for d in d_args if not d in kwargs and d in args[d_index]]:
                    kwargs.update({d_arg: args[d_index][d_arg]})

            f_result = f(*args, **kwargs)

            return f_result

        new_f.__doc__ = f.__doc__
        new_f.__name__ = f.__name__
        return new_f

    return decorate


class CommandInvalid(Exception):
    """ Exception which is raised when the command is not valid. """
    pass


class CommandNotAuthorized(Exception):
    """ Exception which is raised when the call was not authorized. """
    pass
