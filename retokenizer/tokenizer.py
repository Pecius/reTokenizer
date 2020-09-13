from collections.abc import Generator
from typing import List, Iterable, Dict, Union, TextIO, Optional

from .tokenprocessors import TokenProcessor
from .tokens import Token, EndOfFileToken
from .tokenizerexceptions import TokenizerError


class TokenMappingView:
    """Contains data about Token's position in the processed file."""
    __slots__ = ("__source", "__offset", "__lineNumber", "__line", "__lineOffset")

    __source: str
    __offset: int
    __lineNumber: Optional[int]
    __line: Optional[str]
    __lineOffset: Optional[int]

    def __init__(self, source: str, offset: int):
        """
        TokenMappingView constructor.

        :param source: Source of the processed text.
        :param offset: Offset at which the Token starts in the processed text.
        """
        self.__source = source
        self.__offset = offset
        self.__lineNumber = None
        self.__line = None
        self.__lineOffset = None

    @property
    def lineNumber(self):
        """Number of the line that contains the Token."""
        if self.__lineNumber is None:
            self.__lineNumber = self.__source.count("\n", 0, self.__offset) + 1

        return self.__lineNumber

    @property
    def line(self):
        """Line that contains the Token."""
        if self.__line is None:
            left = self.__source.rfind("\n", 0, self.__offset) + 1
            right = self.__source.find("\n", self.__offset)

            self.__line = self.__source[left : right]
            self.__lineOffset = self.__offset - left

        return self.__line

    @property
    def lineOffset(self):
        """Offset where the Token starts in the line."""
        if self.__lineOffset is None:
            self.__lineOffset = self.__offset - self.__source.rfind("\n", 0, self.__offset) - 1

        return self.__lineOffset

    @property
    def offset(self):
        """Offset where the Token starts in the file."""
        return self.__offset

    def makePointer(self):
        """
        Make a visual pointer for the Token.

        :return: Two line string containing a text line and a pointer underneath pointing at the token source beginning.
        """
        line = self.line.replace("\t", "    ")
        tabNumber = self.line.count("\t")
        offset = self.lineOffset
        lineMarker = f"{self.lineNumber}:{offset}: "
        pointerOffset = offset + len(lineMarker) + tabNumber * 4 - 1

        return f"{lineMarker}{line}\n{' ' * pointerOffset}^"


class TokenizerResult:
    """Stores result created by a Tokenizer."""
    __source: Union[str, None]
    __tokenMap: Dict[Token, int]
    __tokens: List[Token]

    def __init__(self, source: str):
        """
        TokenizerResult constructor.

        :param source: Text source of the Tokens.
        """
        self.__tokenMap = {}
        self.__tokens = []
        self.__sourceFilePath = None
        self.__source = source

    @property
    def source(self):
        """Processed text content."""
        return self.__source

    @property
    def tokens(self):
        """List of tokens created from processed text."""
        return self.__tokens

    def addToken(self, token: Token, offset: int):
        """
        Add a token to the tokenizer result.

        :param token: Token to add.
        :param offset: Offset at which the token was captured from in the processed text.
        """
        self.__tokens.append(token)
        self.__tokenMap[token] = offset

    def getTokenMapping(self, token: Token):
        """
        Get a mapping for specified token.

        :param token: Token.
        :return: Mapping for the provided Token.
        """
        if self.__source is None:
            raise TokenizerError("Tried to get a Token mapping without text source!")

        offset = self.__tokenMap.get(token, None)

        if offset is not None:
            return TokenMappingView(self.source, offset)


class Tokenizer:
    """Converts text into Tokens."""
    __tokenProcessors: List[TokenProcessor]

    def __init__(self, tokenProcessors: Iterable[Union[type(TokenProcessor), TokenProcessor]]):
        """
        Tokenizer Constructor.

        :param tokenProcessors: instances or classes of TokenProcessors.
        """
        tokenProcessorInstances = []
        self.__tokenProcessors = tokenProcessorInstances

        for tokenProcessor in tokenProcessors:
            if not isinstance(tokenProcessor, TokenProcessor):
                tokenProcessor = tokenProcessor()

            tokenProcessorInstances.append(tokenProcessor)

    def tokenize(self, source: Union[str, TextIO]):
        """
        Tokenize text content.

        :param source: source of the content to process.
        :return: token result.
        """
        tokenProcessors = self.__tokenProcessors
        pos = 0

        if not isinstance(source, str):
            source = source.read()

        sourceLength = len(source)
        result = TokenizerResult(source)

        processed = True
        while processed:
            processed = False
            for tokenProcessor in tokenProcessors:
                res = tokenProcessor.process(source, pos)

                if res is not None:
                    if not isinstance(res, Generator) and not isinstance(res[0], Iterable):
                        res = (res,)

                    for token, consumed in res:
                        if token is not None:
                            result.addToken(token, pos)

                        pos += consumed

                        processed = True

                    if processed:
                        break

        if pos != sourceLength:
            mappingView = TokenMappingView(source, pos)
            raise TokenizerError(f"Unable to tokenize:\n{mappingView.makePointer()}")

        for tokenProcessor in tokenProcessors:
            res = tokenProcessor.finalizer()

            if not isinstance(res, Generator):
                res = (res,)

            for token in res:
                if token is not None:
                    result.addToken(token, sourceLength)

        result.addToken(EndOfFileToken(), sourceLength)

        return result
