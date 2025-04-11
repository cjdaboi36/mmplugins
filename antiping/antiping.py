import discord
from discord.ext import commands
from datetime import datetime, timedelta
import re
import asyncio

from discord.ext.commands import has_permissions


def parse_duration(duration_str: str) -> timedelta:
    match = re.match(r"(\d+)([smh])", duration_str.lower())
    if not match:
        raise ValueError("Invalid time format. Use s/m/h (e.g. 15m, 1h).")
    value, unit = int(match[1]), match[2]
    return timedelta(seconds=value) if unit == 's' else \
           timedelta(minutes=value) if unit == 'm' else \
           timedelta(hours=value)


class AntiPing(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.protected_users = set()
        self.protected_roles = set()
        self.bypass_users = set()
        self.bypass_roles = set()
        self.protection_paused = {}
        self.timeout_duration = timedelta(minutes=15)
        self.protection_enabled = True
        self.bot_main_color = discord.Color.blue()

    def is_protected(self, member: discord.Member):
        if member.id in self.protection_paused:
            if datetime.utcnow() < self.protection_paused[member.id]:
                return False
            else:
                del self.protection_paused[member.id]
        return (
            member.id in self.protected_users or
            any(role.id in self.protected_roles for role in member.roles)
        )

    def is_bypassed(self, member: discord.Member):
        return (
            member.id in self.bypass_users or
            any(role.id in self.bypass_roles for role in member.roles)
        )

    @commands.command(name="anti-ping-user-add")
    @has_permissions(administrator=True)
    async def protect_add(self, ctx, target: discord.Member):
        embed = discord.Embed(color=self.bot_main_color)
        self.protected_users.add(target.id)
        embed.title = "🛡️ Protection Added"
        embed.description = f"{target.mention} is now protected."
        await ctx.send(embed=embed)

    @commands.command(name="anti-ping-user-remove")
    @has_permissions(administrator=True)
    async def protect_remove(self, ctx, target: discord.Member):
        embed = discord.Embed(color=self.bot_main_color)
        self.protected_users.discard(target.id)
        embed.title = "❌ Protection Removed"
        embed.description = f"{target.mention} is no longer protected."
        await ctx.send(embed=embed)

    @commands.command(name="anti-ping-bypass-add")
    @has_permissions(administrator=True)
    async def bypass_add(self, ctx, target: discord.Member):
        embed = discord.Embed(color=self.bot_main_color)
        self.bypass_users.add(target.id)
        embed.title = "✅ Bypass Added"
        embed.description = f"{target.mention} can now bypass protection."
        await ctx.send(embed=embed)

    @commands.command(name="anti-ping-bypass-remove")
    @has_permissions(administrator=True)
    async def bypass_remove(self, ctx, target: discord.Member):
        embed = discord.Embed(color=self.bot_main_color)
        self.bypass_users.discard(target.id)
        embed.title = "🚫 Bypass Removed"
        embed.description = f"{target.mention} can no longer bypass protection."
        await ctx.send(embed=embed)

    @commands.command(name="anti-ping-pause")
    async def protect_pause(self, ctx, duration: str):
        embed = discord.Embed(color=self.bot_main_color)
        if ctx.author.id not in self.protected_users:
            embed.title = "❌ Protection Not Active"
            embed.description = "You are not a protected user."
            await ctx.send(embed=embed)
            return
        try:
            delta = parse_duration(duration)
        except ValueError as e:
            embed.title = "❌ Invalid Duration"
            embed.description = str(e)
            await ctx.send(embed=embed)
            return
        self.protection_paused[ctx.author.id] = datetime.utcnow() + delta
        embed.title = "⏸️ Protection Paused"
        embed.description = f"Your protection is paused for `{duration}`."
        await ctx.send(embed=embed)

    @commands.command(name="set-anti-ping-timeout-duration")
    @has_permissions(administrator=True)
    async def set_timeout_duration(self, ctx, duration: str):
        embed = discord.Embed(color=self.bot_main_color)
        try:
            self.timeout_duration = parse_duration(duration)
            embed.title = "⏱️ Timeout Duration Set"
            embed.description = f"Timeout duration set to `{duration}`."
        except ValueError as e:
            embed.title = "❌ Invalid Duration"
            embed.description = str(e)
        await ctx.send(embed=embed)

    @commands.command(name="anti-ping-toggle")
    @has_permissions(administrator=True)
    async def protect_toggle(self, ctx):
        embed = discord.Embed(color=self.bot_main_color)
        self.protection_enabled = not self.protection_enabled
        status = "enabled ✅" if self.protection_enabled else "disabled ❌"
        embed.title = "🧷 Protection Toggle"
        embed.description = f"Protection timeout system is now **{status}**."
        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if (
            not self.protection_enabled
            or message.author.bot
            or not message.mentions
        ):
            return

        for mentioned in message.mentions:
            if not isinstance(mentioned, discord.Member):
                continue
            if not self.is_protected(mentioned):
                continue
            if self.is_bypassed(message.author):
                continue
            if (
                message.reference and
                message.reference.resolved and
                isinstance(message.reference.resolved, discord.Message)
            ):
                original = message.reference.resolved
                if original.author.id == mentioned.id and mentioned.mention not in message.content:
                    continue
            
            # Add a delay of 5 seconds before timing out the user
            await asyncio.sleep(5)

            try:
                # Set timeout using keyword arguments
                await message.author.timeout(
                    reason="Pinged a protected user/role",
                    until=discord.utils.utcnow() + self.timeout_duration
                )
                embed = discord.Embed(
                    title=f"Do not ping {mentioned.mention}",
                    description=f"You have been timed out for {self.timeout_duration}.",
                    color=self.bot_main_color
                )
                await message.channel.send(embed=embed)
            except discord.Forbidden:
                embed = discord.Embed(
                    title="❌ Timeout Failed",
                    description="I don't have permission to timeout that user.",
                    color=self.bot_main_color
                )
                await message.channel.send(embed=embed)
            except Exception as e:
                embed = discord.Embed(
                    title="⚠️ Error",
                    description=f"Error timing out: {e}",
                    color=self.bot_main_color
                )
                await message.channel.send(embed=embed)
            break


async def setup(bot):
    await bot.add_cog(AntiPing(bot))
