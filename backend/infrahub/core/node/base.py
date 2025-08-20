from __future__ import annotations

from ..utils import SubclassWithMeta, SubclassWithMeta_Meta


class BaseOptions:
    name: str | None = None
    description: str | None = None

    _frozen: bool = False

    def __init__(self, class_type):
        self.class_type = class_type

    def freeze(self) -> None:
        self._frozen = True

    def __setattr__(self, name, value):
        if not self._frozen:
            super().__setattr__(name, value)
        else:
            raise Exception(f"Can't modify frozen Options {self}")

    def __repr__(self):
        return f"<{self.__class__.__name__} name={repr(self.name)}>"


BaseNodeMeta = SubclassWithMeta_Meta


class BaseNode(SubclassWithMeta):
    # @classmethod
    # def create_node(cls, class_name, **options):
    #     return type(class_name, (cls,), {"Meta": options})

    @classmethod
    def __init_subclass_with_meta__(cls, name=None, description=None, _meta=None, **_kwargs) -> None:
        assert "_meta" not in cls.__dict__, "Can't assign meta directly"
        if not _meta:
            return
        _meta.name = name or cls.__name__
        _meta.description = description
        _meta.freeze()
        cls._meta = _meta
        super().__init_subclass_with_meta__()


class BaseNodeOptions(BaseOptions):
    default_filter = None
    # fields = None  # type: Dict[str, Field]
    # interfaces = ()  # type: Iterable[Type[Interface]]


class ObjectNodeMeta(BaseNodeMeta):
    def __new__(mcs, name_, bases, namespace, **options):
        # Note: it's safe to pass options as keyword arguments as they are still type-checked by NodeOptions.

        # We create this type, to then overload it with the dataclass attrs
        class InterObjectNode:
            pass

        base_cls = super().__new__(mcs, name_, (InterObjectNode,) + bases, namespace, **options)
        # if base_cls._meta:
        #     fields = [
        #         (
        #             key,
        #             "typing.Any",
        #             field(
        #                 default=field_value.default_value
        #                 if isinstance(field_value, Field)
        #                 else None
        #             ),
        #         )
        #         for key, field_value in base_cls._meta.fields.items()
        #     ]
        #     dataclass = make_dataclass(name_, fields, bases=())
        #     InterObjectType.__init__ = dataclass.__init__
        #     InterObjectType.__eq__ = dataclass.__eq__
        #     InterObjectType.__repr__ = dataclass.__repr__
        return base_cls
