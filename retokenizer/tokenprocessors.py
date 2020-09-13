import abc
import re
from copy import copy
from typing import Dict, Callable, Tuple, Any, Optional

from .tokens import *
from .tokenizerexceptions import TokenizerError


class TokenProcessor:
    """Base TokenProcessor class."""

    @abc.abstractmethod
    def process(self, content: str, offset: int) -> Optional[Tuple[Optional[Token], int]]:
        """
        Processes text content into a token.

        :param content: processed text content.
        :param offset: current offset in the text content.
        :return: tuple with a Token and a number of consumed characters.
        """
        raise NotImplementedError

    def finalizer(self) -> Optional[Token]:
        """
        Is called at the end of file.
        """
        pass

    def __or__(self, other):
        """
        Joins two TokenProcessors to create a new one.

        :param other: another TokenProcessor.
        """
        raise NotImplemented


class NewLineProcessor(TokenProcessor):
    """Processes new line characters into EndOfLineToken."""

    __reNewLine = re.compile(r"\r?\n")

    def process(self, content: str, offset: int):
        match = NewLineProcessor.__reNewLine.match(content, pos=offset)

        if match:
            return EndOfLineToken(), match.end() - offset


class ClassicScopeProcessor(TokenProcessor):
    """Processes customizable C style scopes into ScopeStartToken and ScopeEndToken."""

    def __init__(self, startCharacter, endCharacter):
        """
        ClassicScopeProcessor constructor.

        :param startCharacter: character that will start the scope.
        :param endCharacter: character that will end the scope.
        """
        # noinspection RegExpDuplicateAlternationBranch
        self.__regex = re.compile(rf"({re.escape(startCharacter)})|({re.escape(endCharacter)})")

    def process(self, content: str, offset: int):
        match = self.__regex.match(content, pos=offset)

        if match is not None:
            token = ScopeStartToken() if match.lastindex == 1 else ScopeEndToken()

            return token, match.end() - offset


class IndentScopeProcessor(TokenProcessor):
    """Processes indent based scopes into ScopeStartToken and ScopeEndToken."""

    reScope = re.compile(r"\n(\t+)|\n( +)|\n([^\t ])")
    __allowMixed: bool
    __level: int
    __mode: Optional[int]
    __divider: int

    def __init__(self, allowMixed: bool = False):
        """
        IndentScopeProcessor constructor.

        :param allowMixed: allow mixing spaces with tabs in the same text content.
        """
        self.__allowMixed = allowMixed
        self.__level: int = 0
        self.__mode = None
        self.__divider: int = 0

    def process(self, content: str, offset: int):
        res = IndentScopeProcessor.reScope.match(content, pos=offset - 1)

        if res is not None:
            newLevel = res.end() - offset

            if res.lastindex == 3:
                newLevel = 0

            elif self.__mode is None:
                self.__mode = res.lastindex
                self.__divider = newLevel

            elif self.__mode != res.lastindex:
                raise TokenizerError("mixed indent")

            if newLevel != self.__level:
                difference = abs(self.__level - newLevel)

                if difference % self.__divider != 0:
                    raise TokenizerError(f"invalid indent multiply, should be {self.__divider}")

                if newLevel > self.__level:
                    token = ScopeStartToken()
                else:
                    token = ScopeEndToken()

                for i in range(difference // self.__divider):
                    yield token, newLevel

                self.__level = newLevel

            elif newLevel != 0:
                if self.__allowMixed:
                    self.__mode = None

                yield None, newLevel

    def finalizer(self) -> Optional[Token]:
        if self.__level > 0:
            for i in range(self.__level):
                yield ScopeEndToken()


class CommentProcessor(TokenProcessor):
    """Processes comments into CommentToken."""

    def __init__(self, commentCharacter="#"):
        """
        CommentProcessor constructor.

        :param commentCharacter: character that will mark the rest of the line as a comment.
        """
        self.__regex = re.compile(rf"{commentCharacter}(.+)")

    def process(self, content: str, offset: int):
        match = self.__regex.match(content, pos=offset)

        if match is not None:
            return CommentToken(text=match[1]), match.end() - offset


class ConsumingProcessor(TokenProcessor):
    """Consumes characters without returning a token."""

    def __init__(self, toConsume: str):
        """
        ConsumingProcessor constructor.

        :param toConsume: set of characters that this instance will consume.
        """
        self.__regex = re.compile(rf"[{toConsume}]+")

    def process(self, content: str, offset: int):
        match = self.__regex.match(content, pos=offset)

        if match is not None:
            return None, match.end() - offset

    def __or__(self, other: "ConsumingProcessor"):
        newObj = copy(self)

        newRegex = f"{self.__regex.pattern}|{other.__regex.pattern}"
        newObj.__regex = re.compile(newRegex, self.__regex.flags)

        return newObj


class ValueProcessor(TokenProcessor):
    """Processes text into values, returns ValueToken"""

    def __init__(self, *valueExpressions: Tuple[str, type],
                 constructors: Optional[Dict[type, Callable[[str], Any]]] = None):
        """
        ValueProcessor constructor.

        :param valueExpressions: regular expressions that match the string of wanted values.
        :param constructors: optional dictionary that specifies conversion from string to an object of the type.
        """
        self.__types = list(x[1] for x in valueExpressions)
        self.__constructors = {} if constructors is None else constructors

        regexBuild = []

        for expression, tp in valueExpressions:
            if "(" not in expression:
                expression = f"({expression})"

            regexBuild.append(expression)

        self.__regex = re.compile(rf"{'|'.join(regexBuild)}")

    def process(self, content: str, offset: int):
        match = self.__regex.match(content, pos=offset)

        if match is not None:
            index = match.lastindex
            tp = self.__types[index - 1]

            if (constructor := self.__constructors.get(tp, None)) is None:
                constructor = tp

            return ValueToken(type=tp, value=constructor(match[index])), match.end() - offset

    def __or__(self, other: "ValueProcessor"):
        newObj = copy(self)

        newRegex = f"{self.__regex.pattern}|{other.__regex.pattern}"
        newObj.__regex = re.compile(newRegex, self.__regex.flags)

        newObj.__types.extend(other.__types)
        newObj.__constructors.update(other.__constructors)

        return newObj


NumberProcessor = ValueProcessor((r"-?\d*\.\d+", float), (r"-?\d+", int))
QuotedStringProcessor = ValueProcessor((r"\"((?:\\\"|[^\"])*?)\"", str), (r"'((?:\\'|[^'])*?)'", str))
BooleanProcessor = ValueProcessor((r"[Tt]rue|[Ff]alse", bool), constructors={bool: lambda x: x.lower() == "true"})


class SequenceProcessor(TokenProcessor):
    """Processes sequences into SequenceToken"""

    def __init__(self, *sequences: str):
        """
        SequenceProcessor constructor.

        :param sequences: string sequences to match
        """
        self.__regex = re.compile(rf"{'|'.join(sequences)}")

    def process(self, content: str, offset: int):
        match = self.__regex.match(content, pos=offset)

        if match is not None:
            return SequenceToken(sequence=match[0]), match.end() - offset

    def __or__(self, other: "SequenceProcessor"):
        newObj = copy(self)

        newRegex = f"{self.__regex.pattern}|{other.__regex.pattern}"
        newObj.__regex = re.compile(newRegex, self.__regex.flags)

        return newObj


OperatorProcessor = SequenceProcessor(r"([+\-/*=])(?:=|\1)?")

__all__ = tuple(key for key, value in locals().items() if isinstance(value, (TokenProcessor, type(TokenProcessor))))
