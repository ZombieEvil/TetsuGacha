"""
/trade et /divorce.
"""
import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.helpers import success_embed, error_embed, warning_embed


class TradeConfirmView(discord.ui.View):
    def __init__(self, bot, initiator: discord.Member, target: discord.Member,
                 init_char: dict, target_char: dict):
        super().__init__(timeout=120)
        self.bot = bot
        self.initiator = initiator
        self.target = target
        self.init_char = init_char
        self.target_char = target_char
        self.initiator_ok = False
        self.target_ok = False

    async def _check_done(self, interaction: discord.Interaction):
        if self.initiator_ok and self.target_ok:
            # Revérification : les persos appartiennent toujours aux bons users
            owner_init = await self.bot.db.get_character_owner(self.init_char["id"])
            owner_target = await self.bot.db.get_character_owner(self.target_char["id"])

            if owner_init != self.initiator.id or owner_target != self.target.id:
                await interaction.followup.send(
                    embed=error_embed(
                        "Échange annulé : un des personnages n'appartient plus à son propriétaire."
                    )
                )
                self.stop()
                return

            trade_id = await self.bot.db.create_trade(
                interaction.guild.id,
                self.initiator.id, self.target.id,
                self.init_char["id"], self.target_char["id"],
            )
            await self.bot.db.complete_trade(trade_id)

            if hasattr(self.bot, "dashboard"):
                self.bot.dashboard.log_trade(
                    self.initiator.display_name, self.target.display_name,
                    self.init_char["character_name"], self.target_char["character_name"],
                )

            for child in self.children:
                child.disabled = True
            await interaction.message.edit(view=self)

            embed = success_embed(
                f"Échange accompli !\n"
                f"• {self.initiator.mention} reçoit **{self.target_char['character_name']}**\n"
                f"• {self.target.mention} reçoit **{self.init_char['character_name']}**"
            )
            await interaction.followup.send(embed=embed)
            self.stop()

    @discord.ui.button(label="Accepter", emoji="✅", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, _):
        if interaction.user.id == self.initiator.id:
            self.initiator_ok = True
        elif interaction.user.id == self.target.id:
            self.target_ok = True
        else:
            await interaction.response.send_message(
                embed=error_embed("Cet échange ne te concerne pas."),
                ephemeral=True,
            )
            return

        status = (
            f"{self.initiator.mention} : {'✅' if self.initiator_ok else '⏳'}\n"
            f"{self.target.mention} : {'✅' if self.target_ok else '⏳'}"
        )
        await interaction.response.send_message(
            embed=success_embed(f"Confirmation enregistrée.\n\n{status}"),
            ephemeral=True,
        )
        await self._check_done(interaction)

    @discord.ui.button(label="Refuser", emoji="❌", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, _):
        if interaction.user.id not in (self.initiator.id, self.target.id):
            await interaction.response.send_message(
                embed=error_embed("Cet échange ne te concerne pas."),
                ephemeral=True,
            )
            return
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(
            embed=warning_embed(f"Échange annulé par {interaction.user.display_name}.")
        )
        self.stop()


class DivorceConfirmView(discord.ui.View):
    def __init__(self, bot, user_id: int, char: dict, refund: int):
        super().__init__(timeout=30)
        self.bot = bot
        self.user_id = user_id
        self.char = char
        self.refund = refund

    @discord.ui.button(label="Confirmer le divorce", emoji="💔",
                       style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, _):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                embed=error_embed("Ce n'est pas ton divorce."),
                ephemeral=True,
            )
            return
        deleted = await self.bot.db.delete_character(self.char["id"])
        if deleted:
            await self.bot.db.update_user_currency(
                self.user_id, interaction.guild.id, self.refund
            )
            if hasattr(self.bot, "dashboard"):
                self.bot.dashboard.log_divorce(
                    interaction.user.display_name, self.char["character_name"]
                )
            await interaction.response.edit_message(
                embed=success_embed(
                    f"Tu as divorcé de **{self.char['character_name']}**.\n"
                    f"Remboursement : **{self.refund}** {config.CURRENCY_NAME}."
                ),
                view=None,
            )
        else:
            await interaction.response.edit_message(
                embed=error_embed("Erreur lors du divorce."),
                view=None,
            )
        self.stop()

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _):
        if interaction.user.id != self.user_id:
            return
        await interaction.response.edit_message(
            embed=warning_embed("Divorce annulé."),
            view=None,
        )
        self.stop()


class TradeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="trade",
        description="Propose un échange de personnage avec un autre membre"
    )
    @app_commands.describe(
        membre="Membre avec qui échanger",
        mon_perso="Personnage que tu proposes (de ta collection)",
        son_perso="Personnage que tu veux (de sa collection)",
    )
    async def trade(self, interaction: discord.Interaction, membre: discord.Member,
                    mon_perso: str, son_perso: str):
        if membre.id == interaction.user.id:
            await interaction.response.send_message(
                embed=error_embed("Tu ne peux pas échanger avec toi-même."),
                ephemeral=True,
            )
            return
        if membre.bot:
            await interaction.response.send_message(
                embed=error_embed("Tu ne peux pas échanger avec un bot."),
                ephemeral=True,
            )
            return

        my_char = await self.bot.db.find_user_character(
            interaction.user.id, interaction.guild.id, mon_perso
        )
        if not my_char:
            await interaction.response.send_message(
                embed=error_embed(f"Tu n'as pas de personnage nommé `{mon_perso}`."),
                ephemeral=True,
            )
            return

        their_char = await self.bot.db.find_user_character(
            membre.id, interaction.guild.id, son_perso
        )
        if not their_char:
            await interaction.response.send_message(
                embed=error_embed(
                    f"{membre.display_name} n'a pas de personnage nommé `{son_perso}`."
                ),
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title="🤝  Proposition d'échange",
            description=(
                f"{interaction.user.mention} propose un échange à {membre.mention}.\n"
                f"**Les deux doivent cliquer sur ✅ pour valider.**"
            ),
            color=config.BOT_ACCENT_COLOR,
        )
        embed.add_field(
            name=f"💫  {interaction.user.display_name} donne",
            value=(
                f"**{my_char['character_name']}**\n"
                f"*{my_char['character_source']}*\n"
                f"Valeur : {my_char['value']} {config.CURRENCY_NAME}"
            ),
            inline=True,
        )
        embed.add_field(
            name=f"💫  {membre.display_name} donne",
            value=(
                f"**{their_char['character_name']}**\n"
                f"*{their_char['character_source']}*\n"
                f"Valeur : {their_char['value']} {config.CURRENCY_NAME}"
            ),
            inline=True,
        )

        view = TradeConfirmView(self.bot, interaction.user, membre, my_char, their_char)
        await interaction.response.send_message(
            content=f"{membre.mention}, {interaction.user.mention} te propose un échange !",
            embed=embed, view=view,
        )

    @app_commands.command(
        name="divorce",
        description="Libère un personnage de ta collection contre 50 % de sa valeur"
    )
    @app_commands.describe(nom="Nom du personnage à libérer")
    async def divorce(self, interaction: discord.Interaction, nom: str):
        char = await self.bot.db.find_user_character(
            interaction.user.id, interaction.guild.id, nom
        )
        if not char:
            await interaction.response.send_message(
                embed=error_embed(f"Aucun personnage nommé `{nom}` dans ta collection."),
                ephemeral=True,
            )
            return

        refund = char["value"] // 2

        embed = discord.Embed(
            title="⚠️  Confirmer le divorce",
            description=(
                f"Tu t'apprêtes à libérer **{char['character_name']}** "
                f"de *{char['character_source']}*.\n"
                f"Tu récupéreras **{refund}** {config.CURRENCY_NAME} (50 % de la valeur).\n\n"
                f"*Action irréversible.*"
            ),
            color=0xE74C3C,
        )
        if char.get("image_url"):
            embed.set_thumbnail(url=char["image_url"])

        await interaction.response.send_message(
            embed=embed,
            view=DivorceConfirmView(self.bot, interaction.user.id, char, refund),
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(TradeCog(bot))
