"""Safe math calculator via AST."""

from __future__ import annotations

import ast
import operator

import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import error_embed, info_embed


class _SafeEval(ast.NodeVisitor):
    _ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
    }

    def visit(self, node):  # type: ignore[override]
        if isinstance(node, ast.Expression):
            return self.visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.UnaryOp):
            v = self.visit(node.operand)
            if isinstance(node.op, ast.USub):
                return -v
            if isinstance(node.op, ast.UAdd):
                return +v
            raise ValueError("Unsupported unary operator")
        if isinstance(node, ast.BinOp):
            op_type = type(node.op)
            if op_type not in self._ops:
                raise ValueError("Unsupported operator")
            left = self.visit(node.left)
            right = self.visit(node.right)
            fn = self._ops[op_type]
            if op_type is ast.Div and right == 0:
                raise ZeroDivisionError("division by zero")
            return fn(left, right)
        raise ValueError("Unsupported expression")


def safe_eval_expr(expr: str) -> float:
    tree = ast.parse(expr.strip(), mode="eval")
    return float(_SafeEval().visit(tree))


class CalculatorCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="calc", description="Evaluate a math expression safely.")
    @app_commands.describe(expression="Expression using + - * / ** % and parentheses")
    async def calc(self, interaction: discord.Interaction, expression: str) -> None:
        try:
            result = safe_eval_expr(expression)
            emb = info_embed(
                "Calculator",
                f"**Input:** `{expression}`\n**Result:** `{result}`",
            )
            await interaction.response.send_message(embed=emb)
        except ZeroDivisionError:
            await interaction.response.send_message(
                embed=error_embed("Error", "Division by zero."), ephemeral=True
            )
        except Exception:
            await interaction.response.send_message(
                embed=error_embed("Error", "Invalid expression."), ephemeral=True
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CalculatorCog(bot))
