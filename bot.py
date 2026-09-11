import os
import discord
from discord.ext import commands
from discord import app_commands, Embed, ButtonStyle, TextStyle
from discord.ui import View, Button, Modal, TextInput, Select

# ================= Configuration =================
TOKEN = os.getenv("DISCORD_TOKEN")

# Category IDs
BOOST_CATEGORY_ID = 1548054637222039664
CARRY_CATEGORY_ID = 1548054441419219064

# Payment Infos
MY_RIB_INFO = "Bank: CIH BANK\nRIB: 123456789012345678901234\nName: YOUR NAME HERE"
MY_PAYPAL_INFO = "PayPal Email: paypal.me/yourusername"

IMAGE_PRICES_1 = "https://cdn.discordapp.com/attachments/123/456/image1.png"

# Prices Matrix for Ranks
RANK_PRICES = {
    "Bronze I": 0, "Bronze II": 1, "Bronze III": 1,
    "Silver I": 1, "Silver II": 1.5, "Silver III": 1.5,
    "Gold I": 2, "Gold II": 2, "Gold III": 2,
    "Diamond I": 2, "Diamond II": 2, "Diamond III": 3,
    "Mythic I": 4, "Mythic II": 5, "Mythic III": 6,
    "Legendary I": 9, "Legendary II": 12, "Legendary III": 15,
    "Masters I": 30, "Masters II": 60, "Pro": 105
}

RANKS_ORDER = list(RANK_PRICES.keys())

def calculate_price(current_rank: str, desired_rank: str, order_type: str) -> float:
    try:
        start_idx = RANKS_ORDER.index(current_rank)
        end_idx = RANKS_ORDER.index(desired_rank)
    except ValueError:
        return 0.0

    if start_idx >= end_idx:
        return 0.0

    base_total = sum(RANK_PRICES[RANKS_ORDER[i]] for i in range(start_idx + 1, end_idx + 1))
    multiplier = 2.0 if order_type == "Carry" else 1.0
    return round(base_total * multiplier, 2)

# ================= Discord Bot Setup =================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Confirmation View for Closing
class ConfirmCloseView(View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Yes, Close", style=ButtonStyle.danger, emoji="✅", custom_id="confirm_close_btn")
    async def confirm(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("🔒 Closing channel in 5 seconds...")
        await discord.utils.sleep_until(discord.utils.utcnow() + discord.utils.datetime.timedelta(seconds=5))
        await interaction.channel.delete()

    @discord.ui.button(label="Cancel", style=ButtonStyle.secondary, emoji="❌", custom_id="cancel_close_btn")
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Closing cancelled.", ephemeral=True)
        await interaction.message.delete()

# Modal for Close with Reason
class CloseReasonModal(Modal):
    def __init__(self):
        super().__init__(title="Close Ticket With Reason")
        self.reason = TextInput(
            label="Reason for closing",
            style=TextStyle.paragraph,
            placeholder="Write the reason here...",
            required=True
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        reason_text = self.reason.value
        await interaction.response.send_message(f"🔒 Ticket closing. Reason: **{reason_text}**\nDeleting in 5 seconds...")
        await discord.utils.sleep_until(discord.utils.utcnow() + discord.utils.datetime.timedelta(seconds=5))
        await interaction.channel.delete()

# Ticket View Controls
class TicketControlsView(View):
    def __init__(self, payment_method: str = "Bank Transfer / RIB", payment_enabled: bool = False):
        super().__init__(timeout=None)
        self.payment_method = payment_method

        self.close_btn = Button(label="Close", style=ButtonStyle.danger, emoji="🔒", custom_id="ticket_close_btn")
        self.close_btn.callback = self.close_callback

        self.close_reason_btn = Button(label="Close With Reason", style=ButtonStyle.secondary, emoji="📝", custom_id="ticket_close_reason_btn")
        self.close_reason_btn.callback = self.close_reason_callback

        self.sent_payment_btn = Button(
            label="I Sent Payment",
            style=ButtonStyle.success,
            emoji="💳",
            disabled=not payment_enabled,
            custom_id="ticket_sent_payment_btn"
        )
        self.sent_payment_btn.callback = self.sent_payment_callback

        self.add_item(self.close_btn)
        self.add_item(self.close_reason_btn)
        self.add_item(self.sent_payment_btn)

    async def close_callback(self, interaction: discord.Interaction):
        embed = Embed(
            title="Confirm Action",
            description="Are you sure you want to close this ticket?",
            color=0xFF0000
        )
        await interaction.response.send_message(embed=embed, view=ConfirmCloseView(), ephemeral=True)

    async def close_reason_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CloseReasonModal())

    async def sent_payment_callback(self, interaction: discord.Interaction):
        pm_lower = self.payment_method.lower()
        if "bank" in pm_lower or "rib" in pm_lower:
            pay_details = f"🏦 **Bank Transfer Details (RIB):**\n```\n{MY_RIB_INFO}\n```"
        else:
            pay_details = f"🅿️ **PayPal Details:**\n```\n{MY_PAYPAL_INFO}\n```"

        embed = Embed(
            title="Payment Instructions",
            description=f"{pay_details}\n\nPlease send a screenshot of the payment in this channel for verification!",
            color=0x00FF00
        )
        await interaction.response.send_message(embed=embed)

# Step-by-Step Selection Flow (Dropdowns)
class OrderFlowView(View):
    def __init__(self, order_type: str):
        super().__init__(timeout=180)
        self.order_type = order_type
        self.current_rank = None
        self.desired_rank = None
        self.payment_method = None

        # Current Rank Dropdown
        self.current_select = Select(
            placeholder="Select your Current Rank...",
            options=[discord.SelectOption(label=rank) for rank in RANKS_ORDER[:-1]]
        )
        self.current_select.callback = self.current_callback
        self.add_item(self.current_select)

    async def current_callback(self, interaction: discord.Interaction):
        self.current_rank = self.current_select.values[0]
        
        start_idx = RANKS_ORDER.index(self.current_rank)
        valid_desired = RANKS_ORDER[start_idx + 1:]

        self.clear_items()
        self.desired_select = Select(
            placeholder=f"Current: {self.current_rank} ➔ Select Desired Rank...",
            options=[discord.SelectOption(label=rank) for rank in valid_desired[:25]]
        )
        self.desired_select.callback = self.desired_callback
        self.add_item(self.desired_select)

        await interaction.response.edit_message(
            content=f"✅ Current Rank: **{self.current_rank}**\nNow select your **Desired Rank**:",
            view=self
        )

    async def desired_callback(self, interaction: discord.Interaction):
        self.desired_rank = self.desired_select.values[0]

        self.clear_items()
        self.payment_select = Select(
            placeholder="Select Payment Method...",
            options=[
                discord.SelectOption(label="Bank Transfer / RIB", emoji="🏦"),
                discord.SelectOption(label="PayPal", emoji="🅿️"),
                discord.SelectOption(label="Crypto / Other", emoji="💳")
            ]
        )
        self.payment_select.callback = self.payment_callback
        self.add_item(self.payment_select)

        await interaction.response.edit_message(
            content=f"✅ Current: **{self.current_rank}** | Desired: **{self.desired_rank}**\nSelect your **Payment Method**:",
            view=self
        )

    async def payment_callback(self, interaction: discord.Interaction):
        self.payment_method = self.payment_select.values[0]
        await interaction.response.defer(ephemeral=True)

        total_price = calculate_price(self.current_rank, self.desired_rank, self.order_type)

        category_id = CARRY_CATEGORY_ID if self.order_type == "Carry" else BOOST_CATEGORY_ID
        category = interaction.guild.get_channel(category_id)

        ticket_name = f"order-{interaction.user.name}".lower()

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }

        ticket_channel = await interaction.guild.create_text_channel(
            name=ticket_name,
            category=category if isinstance(category, discord.CategoryChannel) else None,
            overwrites=overwrites
        )

        header_embed = Embed(
            title="Ranked Boost Order Ticket",
            description=f"Your Ranked **{self.order_type}** order ticket is open 👊",
            color=0x8A2BE2
        )
        header_embed.set_footer(text="Powered by Iceyz BrawlMart™")

        details_embed = Embed(
            title="Your Ranked Boost Order Details",
            color=0x8A2BE2
        )
        details_embed.add_field(name="Current Rank 🛡️", value=f"└ `{self.current_rank}`", inline=False)
        details_embed.add_field(name="Desired Rank 🏆", value=f"└ `{self.desired_rank}`", inline=False)
        details_embed.add_field(name="Order Type 🚀", value=f"└ `{self.order_type}`", inline=False)
        details_embed.add_field(name="Total Price 💰", value=f"└ `${total_price} USD`", inline=False)
        details_embed.add_field(name="Payment Method 💳", value=f"└ `{self.payment_method}`", inline=False)
        details_embed.set_footer(text=f"Powered by Iceyz BrawlMart™ • {interaction.user.id}")

        view = TicketControlsView(payment_method=self.payment_method, payment_enabled=False)

        msg = await ticket_channel.send(content=f"{interaction.user.mention}", embeds=[header_embed, details_embed], view=view)

        bot.ticket_data[ticket_channel.id] = {
            "payment_method": self.payment_method,
            "message_id": msg.id
        }

        await interaction.followup.send(f"Ticket created successfully! {ticket_channel.mention}", ephemeral=True)

# Select Service Type View
class ServiceTypeView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Get B00sted", style=ButtonStyle.success, emoji="🚀", custom_id="srv_boosted_btn")
    async def boosted_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Please select your order parameters:", view=OrderFlowView("Boost"), ephemeral=True)

    @discord.ui.button(label="Get Carried (2x Price)", style=ButtonStyle.blurple, emoji="🤝", custom_id="srv_carried_btn")
    async def carried_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Please select your order parameters:", view=OrderFlowView("Carry"), ephemeral=True)

# Main Ticket Panel View
class MainTicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Get Your Rank Upgraded", style=ButtonStyle.primary, emoji="👊", custom_id="get_rank_upgraded")
    async def upgrade_button(self, interaction: discord.Interaction, button: Button):
        embed = Embed(
            title="Choose your service type:",
            description="🚀 **B00st** - Standard service\n🤝 **Carry** - Play together (2x price)",
            color=0x8A2BE2
        )
        await interaction.response.send_message(embed=embed, view=ServiceTypeView(), ephemeral=True)

# Command to Setup Main Panel
@bot.tree.command(name="setup_panel", description="Setup Ranked Boost Panel")
@app_commands.default_permissions(administrator=True)
async def setup_panel(interaction: discord.Interaction):
    embed = Embed(
        title="Ranked B00st Service",
        description="**What We Offer**\n• Climb the ranks with professional boosting service\n• Fast, secure, and reliable rank progression\n• Experienced boosters with proven track records",
        color=0x8A2BE2
    )
    embed.set_image(url=IMAGE_PRICES_1)

    await interaction.channel.send(embed=embed, view=MainTicketView())
    await interaction.response.send_message("Panel created successfully!", ephemeral=True)

@bot.event
async def on_ready():
    bot.ticket_data = getattr(bot, 'ticket_data', {})
    
    # Register persistent views so buttons work even after restart
    bot.add_view(MainTicketView())
    bot.add_view(ServiceTypeView())
    bot.add_view(TicketControlsView())
    
    await bot.tree.sync()
    print(f"Bot logged in as {bot.user}")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if message.channel.id in bot.ticket_data:
        if message.content.strip().lower() == "done":
            data = bot.ticket_data[message.channel.id]
            pm_method = data["payment_method"]
            msg_id = data["message_id"]

            try:
                msg = await message.channel.fetch_message(msg_id)
                new_view = TicketControlsView(payment_method=pm_method, payment_enabled=True)
                await msg.edit(view=new_view)
                await message.channel.send("✅ Payment button activated! Click **'I Sent Payment'** below to receive payment details.")
            except Exception as e:
                print(f"Error updating payment button: {e}")

    await bot.process_commands(message)

if __name__ == "__main__":
    bot.run(TOKEN)
