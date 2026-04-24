"""
/shop : acheter des items (Rarity Protection, Pack de rolls)
/buy : raccourci
"""
import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.helpers import success_embed, error_embed, warning_embed


class ShopView(discord.ui.View):
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=120)
        self.bot = bot
        self.user_id = user_id

    @discord.ui.select(
        placeholder="Choisis un item à acheter…",
        options=[
            discord.SelectOption(
                label=item["name"],
                value=key,
                description=f"{item['price']} tokens · {item['description'][:60]}",
                emoji=item["emoji"],
            )
            for key, item in config.SHOP_ITEMS.items()
        ],
    )
    async def item_select(self, interaction: discord.Interaction,
                           select: discord.ui.Select):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=error_embed("Ce n'est pas ton shop."),
                ephemeral=True,
            )
            return

        item_key = select.values[0]
        item = config.SHOP_ITEMS.get(item_key)
        if not item:
            await interaction.response.send_message(
                embed=error_embed("Item introuvable."),
                ephemeral=True,
            )
            return

        user = await self.bot.db.get_or_create_user(
            self.user_id, interaction.guild.id
        )
        if user["currency"] < item["price"]:
            await interaction.response.send_message(
                embed=error_embed(
                    f"Il te faut **{item['price']}** {config.CURRENCY_NAME} "
                    f"(tu en as **{user['currency']}**)."
                ),
                ephemeral=True,
            )
            return

        # Application de l'effet
        if "min_rarity_guaranteed" in item:
            # Rarity Protection : un seul stockable à la fois
            existing = user.get("rarity_protection")
            if existing:
                await interaction.response.send_message(
                    embed=warning_embed(
                        f"Tu as déjà une protection active : **{existing}**. "
                        f"Utilise-la d'abord en faisant un `/roll`."
                    ),
                    ephemeral=True,
                )
                return
            await self.bot.db.update_user_currency(
                self.user_id, interaction.guild.id, -item["price"]
            )
            await self.bot.db.set_rarity_protection(
                self.user_id, interaction.guild.id, item["min_rarity_guaranteed"]
            )
            msg = (
                f"{item['emoji']}  **{item['name']}** achetée !\n"
                f"Ton prochain `/roll` sera garanti minimum **{item['min_rarity_guaranteed']}**."
            )

        elif "bonus_rolls" in item:
            await self.bot.db.update_user_currency(
                self.user_id, interaction.guild.id, -item["price"]
            )
            await self.bot.db.increment_user_field(
                self.user_id, interaction.guild.id,
                "bonus_rolls", item["bonus_rolls"],
            )
            msg = (
                f"{item['emoji']}  **{item['name']}** acheté !\n"
                f"Tu as reçu **+{item['bonus_rolls']}** rolls bonus."
            )
        else:
            await interaction.response.send_message(
                embed=error_embed("Cet item n'a pas d'effet défini."),
                ephemeral=True,
            )
            return

        new_user = await self.bot.db.get_or_create_user(
            self.user_id, interaction.guild.id
        )
        embed = success_embed(
            msg + f"\n\nSolde : **{new_user['currency']}** {config.CURRENCY_NAME}"
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ShopCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="shop", description="Affiche le shop et achète des items")
    async def shop(self, interaction: discord.Interaction):
        user = await self.bot.db.get_or_create_user(
            interaction.user.id, interaction.guild.id
        )
        embed = discord.Embed(
            title=f"🛒  Shop  ·  {config.BOT_NAME}",
            description=(
                f"Solde : **{user['currency']}** {config.CURRENCY_NAME}\n"
                f"*Sélectionne un item dans le menu ci-dessous.*"
            ),
            color=config.BOT_COLOR,
        )
        for key, item in config.SHOP_ITEMS.items():
            embed.add_field(
                name=f"{item['emoji']}  {item['name']}  ·  {item['price']} {config.CURRENCY_NAME}",
                value=item["description"],
                inline=False,
            )

        if user.get("rarity_protection"):
            embed.add_field(
                name="🛡️  Protection active",
                value=f"Ton prochain roll sera garanti **{user['rarity_protection']}**.",
                inline=False,
            )

        embed.set_footer(text=config.BOT_NAME)
        view = ShopView(self.bot, interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def setup(bot):
    await bot.add_cog(ShopCog(bot))
