# -*- coding: utf-8 -*-

"""
jishaku.codeblocks
~~~~~~~~~~~~~~~~~~

Converters for detecting and obtaining codeblock content

:copyright: (c) 2021 Devon (Gorialis) R
:license: MIT, see LICENSE for more details.

"""
from __future__ import annotations
from email import message
from click import command

from discord.ext.commands.converter import Converter, MessageConverter, MessageNotFound  # type: ignore

import re
import collections
import typing


if typing.TYPE_CHECKING:
    from jishaku.types import ContextA

    from discord import Message
    from discord.app_commands import Command as AppCommand, Group as AppGroup
    from discord.ext.commands import Command as ExtCommand, Group as ExtGroup, HybridCommand as HybridCommand, HybridGroup  # type: ignore

    CommandT = typing.Union[AppCommand, AppGroup, ExtCommand, ExtGroup, HybridCommand, HybridGroup]  # type: ignore


__all__ = ("Codeblock", "codeblock_converter")


class Codeblock(typing.NamedTuple):
    """
    Represents a parsed codeblock from codeblock_converter
    """

    language: typing.Optional[str]
    content: str


def codeblock_converter(argument: str) -> Codeblock:
    """
    A converter that strips codeblock markdown if it exists.

    Returns a namedtuple of (language, content).

    :attr:`Codeblock.language` is an empty string if no language was given with this codeblock.
    It is ``None`` if the input was not a complete codeblock.
    """
    if not argument.startswith("`"):
        return Codeblock(None, argument)

    # keep a small buffer of the last chars we've seen
    last: typing.Deque[str] = collections.deque(maxlen=3)
    backticks = 0
    in_language = False
    in_code = False
    language: typing.List[str] = []
    code: typing.List[str] = []

    for char in argument:
        if char == "`" and not in_code and not in_language:
            backticks += 1  # to help keep track of closing backticks
        if last and last[-1] == "`" and char != "`" or in_code and "".join(last) != "`" * backticks:
            in_code = True
            code.append(char)
        if char == "\n":  # \n delimits language and code
            in_language = False
            in_code = True
        # we're not seeing a newline yet but we also passed the opening ```
        elif "".join(last) == "`" * 3 and char != "`":
            in_language = True
            language.append(char)
        elif in_language:  # we're in the language after the first non-backtick character
            if char != "\n":
                language.append(char)

        last.append(char)

    if not code and not language:
        code[:] = last

    return Codeblock("".join(language), "".join(code[len(language) : -backticks]))


class CodeblockFromMessage(Converter[Codeblock]):
    def remove_before_codeblock(self, message: Message) -> typing.Optional[str]:
        contents: typing.List[str] = message.content.split(" ")
        if not contents:
            return None

        codeblock = "```"
        for string in contents:
            if string.find(codeblock) != -1:
                contents[0] = string[string.find(codeblock) :]
                return " ".join(contents)

        return " ".join(list(contents))

    async def convert(self, ctx: ContextA, argument: str) -> Codeblock:
        """
        A converter that tries to get a codeblock from a message.
        If a message is found and the `Message.content` is not empty,
        it will strip all mentions and command name + prefix
        from the message content and call codeblock_converter on it.

        Otherwise, it will call codeblock_converter on the argument.
        """
        try:
            message = await MessageConverter().convert(ctx, argument)
        except MessageNotFound:
            argument = argument
        else:
            argument = self.remove_before_codeblock(message) or argument
        finally:
            return codeblock_converter(argument)
