class TokenMetaClass(type):
    @classmethod
    def __prepare__(metaCls, name, bases):
        cls = super().__prepare__(metaCls, name, bases)
        cls["__slots__"] = ()

        return cls

    def __contains__(self, item: "Token") -> bool:
        return self is type(item)


class Token(metaclass=TokenMetaClass):
    """Base Token class."""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def args(self):
        return dict((x, getattr(self, x, None)) for x in self.__slots__)

    def __repr__(self):
        args = ', '.join(f"{key}={repr(value)}" for key, value in self.args.items())
        return f"{self.__class__.__name__}({args})"


class EndOfLineToken(Token):
    """Marks an end of a line."""


class EndOfFileToken(EndOfLineToken):
    """Marks an end of a file."""


class ScopeStartToken(Token):
    """Marks a start of a scope."""


class ScopeEndToken(Token):
    """Marks an end of a scope."""


class CommentToken(Token):
    """Contains a text value of a comment."""

    __slots__ = ("text",)
    text: str


class ValueToken(Token):
    """Contains a type and a converted value."""

    __slots__ = ("type", "value")
    type: type


class SequenceToken(Token):
    """Contains a text sequence."""
    __slots__ = ("sequence",)
    sequence: str
