# -*- coding: utf-8 -*-

"""
jishaku.codeblocks
~~~~~~~~~~~~~~~~~~

Converters for detecting and obtaining codeblock content

:copyright: (c) 2021 Devon (Gorialis) R
:license: MIT, see LICENSE for more details.

"""
from __future__ import annotations

import collections
import typing

from discord import ButtonStyle, ui, TextStyle
from discord.ext.commands.converter import Converter, MessageConverter, MessageNotFound

if typing.TYPE_CHECKING:
    from jishaku.types import ContextA

    from discord import Message, Interaction
    from discord.app_commands import Command as AppCommand, Group as AppGroup
    from discord.ext.commands import Command as ExtCommand, Group as ExtGroup, HybridCommand as HybridCommand, HybridGroup  # type: ignore

    CommandT = typing.Union[AppCommand, AppGroup, ExtCommand, ExtGroup, HybridCommand, HybridGroup]  # type: ignore


__all__ = ("Codeblock", "codeblock_converter")

class InputModal(ui.Modal):
    argument: ui.TextInput[InputModal] = ui.TextInput(label="Enter your argument here", placeholder="Argument", min_length=1, max_length=4000, style=TextStyle.long)

    def __init__(
        self,
        author_id: int,
    ) -> None:
        self.author_id: int = author_id
        super().__init__(timeout=60.0, title="Code Input")

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This is not your modal!", ephemeral=True)
            return False
        
        return True
    
    async def on_submit(self, interaction: Interaction) -> None:
        await interaction.response.defer()
        self.stop()
        

class OpenInputModalButton(ui.View):
    message: typing.Any
    def __init__(
        self,
        modal: InputModal,
    ) -> None:
        self.modal: InputModal = modal
        super().__init__(timeout=60.0)

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.modal.author_id:
            await interaction.response.send_message("This is not your button!", ephemeral=True)
            return False
        
        return True

    @ui.button(label="Input Text", style=ButtonStyle.blurple)
    async def input_text(self, interaction: Interaction, button: ui.Button[OpenInputModalButton]) -> None:
        await interaction.response.send_modal(self.modal)
        await self.modal.wait()
        self.stop()


async def get_input(
    ctx: ContextA,
    argument: typing.Optional[Codeblock] = None,
) -> Codeblock:
    if argument is not None:
        return argument

    if ctx.interaction:
        modal = InputModal(ctx.author.id)
        await ctx.interaction.response.send_modal(modal)
        await modal.wait()
        return codeblock_converter(modal.argument.value)
    else:
        view = OpenInputModalButton(InputModal(ctx.author.id))
        msg = await ctx.send("Input your argument", view=view)
        await view.modal.wait()
        await msg.edit(view=None)
        return codeblock_converter(view.modal.argument.value, message=msg)
        

class Codeblock(typing.NamedTuple):
    """
    Represents a parsed codeblock from codeblock_converter
    """

    language: typing.Optional[str]
    content: str
    message: typing.Optional[Message] = None


def codeblock_converter(argument: str, message: typing.Optional[Message] = None) -> Codeblock:
    """
    A converter that strips codeblock markdown if it exists.

    Returns a namedtuple of (language, content).

    :attr:`Codeblock.language` is an empty string if no language was given with this codeblock.
    It is ``None`` if the input was not a complete codeblock.
    """
    if not argument.startswith("`"):
        return Codeblock(None, argument, message=message)

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

    return Codeblock("".join(language), "".join(code[len(language) : -backticks]), message=message)


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
