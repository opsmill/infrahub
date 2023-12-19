from __future__ import annotations

from inspect import isclass

# --------------------------------------------------------------------------------
# CODE IMPORTED FROM:
#   https://github.com/graphql-python/graphene/blob/9c3e4bb7da001aac48002a3b7d83dcd072087770/graphene/utils/subclass_with_meta.py#L18
#   https://github.com/graphql-python/graphene/blob/9c3e4bb7da001aac48002a3b7d83dcd072087770/graphene/utils/props.py#L12
# --------------------------------------------------------------------------------


class _OldClass:
    pass


class _NewClass:
    pass


_all_vars = set(dir(_OldClass) + dir(_NewClass))


def props(x):
    return {key: vars(x).get(key, getattr(x, key)) for key in dir(x) if key not in _all_vars}


class SubclassWithMeta_Meta(type):
    _meta = None

    def __str__(cls):
        if cls._meta:
            return cls._meta.name
        return cls.__name__

    def __repr__(cls):
        return f"<{cls.__name__} meta={repr(cls._meta)}>"


class SubclassWithMeta(metaclass=SubclassWithMeta_Meta):
    """This class improves __init_subclass__ to receive automatically the options from meta"""

    def __init_subclass__(cls, **meta_options):
        """This method just terminates the super() chain"""
        _Meta = getattr(cls, "Meta", None)
        _meta_props = {}
        if _Meta:
            if isinstance(_Meta, dict):
                _meta_props = _Meta
            elif isclass(_Meta):
                _meta_props = props(_Meta)
            else:
                raise TypeError(f"Meta have to be either a class or a dict. Received {_Meta}")
            delattr(cls, "Meta")
        options = dict(meta_options, **_meta_props)

        abstract = options.pop("abstract", False)
        if abstract:
            assert not options, (
                "Abstract types can only contain the abstract attribute. " f"Received: abstract, {', '.join(options)}"
            )
        else:
            super_class = super(cls, cls)
            if hasattr(super_class, "__init_subclass_with_meta__"):
                super_class.__init_subclass_with_meta__(**options)

    @classmethod
    def __init_subclass_with_meta__(cls, **meta_options):
        """This method just terminates the super() chain"""
