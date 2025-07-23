import discord
from discord.ext import commands, tasks
from apscheduler.schedulers.background import BackgroundScheduler

from dotenv import load_dotenv
import logging
import os
import json
import aiohttp
import re
from datetime import datetime, timedelta
from flask import Flask



# Environment and Logging Setup
load_dotenv()

token = os.getenv('DISCORD_TOKEN')
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')


app = Flask(__name__)

@app.route('/')
def index():
    return "Hello from Render!"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)


# Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)





# File Paths
birthdays_file = "birthdays.json"
birthday_channel_file = "birthday_channel.json"
already_wished_today = {"already_wished_today.json"}
wished_log_file = ("wished_log.json")


def reset_wishes_if_new_day():
    current_date = datetime.date.today().isoformat()
    if already_wished_today.get("date") != current_date:
        already_wished_today.clear()
        already_wished_today["date"] = current_date

# Utilities
def load_birthdays():
    try:
        with open(birthdays_file, "r") as f:
            content = f.read().strip()
            return json.loads(content) if content else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_birthdays(data):
    with open(birthdays_file, "w") as f:
        json.dump(data, f)

def load_wished_log():
    try:
        with open(wished_log_file, "r") as f:
            return json.load(f)
    except:
        return {}

def save_wished_log(data):
    with open(wished_log_file, "w") as f:
        json.dump(data, f)

# Events
@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user.name}")
    check_birthdays.start()

@bot.event
async def on_member_join(member):
    print(f"{member.name} joined the server.")
    await member.send(f"🎉 Welcome, {member.name}! What’s your birthday? Reply in `DD-MM` format (e.g., 21-07).")

    def check(m):
        return m.author == member and isinstance(m.channel, discord.DMChannel)

    try:
        msg = await bot.wait_for('message', check=check, timeout=60)
        dob_raw = re.sub(r"[/.]", "-", msg.content.strip())
        match = re.match(r"^(\d{1,2})-(\d{1,2})$", dob_raw)
        if match:
            day, month = match.groups()
            dob_with_year = f"1904-{int(day):02d}-{int(month):02d}"
            datetime.strptime(dob_with_year, "%Y-%d-%m")
            dob_formatted = f"{int(day):02d}-{int(month):02d}"
            birthdays = load_birthdays()
            birthdays[str(member.id)] = dob_formatted
            save_birthdays(birthdays)
            await member.send("📆 Birthday saved! We’ll celebrate when the day arrives 🎂")
        else:
            await member.send("⚠️ Invalid format. Use `DD-MM`, like `21-07`.")
    except Exception as e:
        print(f"Error handling {member.name}: {e}")

@bot.event
async def on_member_remove(member):
    print(f"{member.name} left the server.")
    try:
        await member.send(f"👋 Goodbye, {member.name}. If you have feedback, we’d love to hear it.")
    except discord.Forbidden:
        pass

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    bad_words = [
        "fuck", "shit", "bitch", "asshole", "bastard", "dick", "piss", 
        "son of a bitch", "twat", "wanker", "slut","jerk", "moron",
        "retard",  "scumbag", 
        "bhenchod", "madarchod", "chutiya", "gandu", "lund", "loda", "raand",
        "randi", "kuttiya", "gaand", "gand",
        "chod", "chudwa", "chudne", "bhosdike", "bhosda", "bakchod", 
        "bhosdika", "bhosdiki", "gand mara", "gand maar", "gandu ki aulad",
        "gandu ki aulad", "gandu ki maa", "gandu ki beti", "gandu ki behen",
        "gandu ki chudiya", "gandu ki chudai", "gandu ki chudai", "gandu ki chudai",
        "lauda", "lulli", "chut", "choot", "chutiyapa", "jhatu", "jhaat"
    ]

    if any(word in message.content.lower() for word in bad_words):
        await message.delete()
        await message.channel.send(f"🚫 {message.author.mention}, watch the language.")
        try:
            await message.author.edit(timed_out_until=discord.utils.utcnow() + timedelta(hours=24))
        except Exception as e:
            print(f"Could not timeout user: {e}")
        return

    if message.content.startswith('!hello'):
        await message.channel.send(f'👋 Hello {message.author.name}!')
    
    await bot.process_commands(message)

# Birthday Checker
def get_theme():
    month = datetime.utcnow().month
    themes = {
        1: ("❄️", discord.Color.blue(), "Snowy vibes ahead!"),
        2: ("💖", discord.Color.magenta(), "Love and celebration!"),
        3: ("🌼", discord.Color.gold(), "Spring blooms for you!"),
        4: ("🌸", discord.Color.pink(), "Fresh starts and cherry blossoms!"),
        5: ("🌞", discord.Color.orange(), "Summer light and warmth!"),
        6: ("🏳️‍🌈", discord.Color.teal(), "Celebrate freely and brightly!"),
        7: ("🎆", discord.Color.red(), "Sparkles of joy!"),
        8: ("🌻", discord.Color.yellow(), "Golden sunshine in every moment!"),
        9: ("🍂", discord.Color.dark_orange(), "Cozy autumn vibes!"),
        10: ("🎃", discord.Color.dark_purple(), "Spooky sweets and treats!"),
        11: ("🍁", discord.Color.dark_gold(), "Grateful hearts and warm wishes!"),
        12: ("🎄", discord.Color.green(), "Festive magic in the air!")
    }
    return themes.get(month, ("🎉", discord.Color.purple(), "A day to celebrate YOU!"))

# Check if a birthday wish already exists via message history OR log
async def already_wished_today(channel, user, wished_log):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    if wished_log.get(today, {}).get(str(user.id)):
        return True

    async for msg in channel.history(limit=100, after=datetime.utcnow().replace(hour=0, minute=0)):
        if (
            msg.author == channel.guild.me and
            user.mention in msg.content and
            "Happy Birthday" in msg.content
        ):
            return True
    return False

@tasks.loop(hours=24)
async def check_birthdays():
    today_dm = datetime.utcnow().strftime("%d-%m")
    today_log_key = datetime.utcnow().strftime("%Y-%m-%d")
    birthdays = load_birthdays()
    wished_log = load_wished_log()

    try:
        with open(birthday_channel_file, "r") as f:
            channel_id = json.load(f).get("channel_id")
            channel = bot.get_channel(channel_id)
    except Exception as e:
        print("Error loading birthday channel:", e)
        return

    if not channel:
        print("Birthday channel not found.")
        return

    emoji, color, theme_msg = get_theme()

    for user_id, dob in birthdays.items():
        if dob == today_dm:
            user = await bot.fetch_user(int(user_id))

            if await already_wished_today(channel, user, wished_log):
                print(f"✅ Already wished {user.name} today.")
                continue

            embed = discord.Embed(
                title=f"{emoji} Happy Birthday {user.name}!",
                description=f"{user.mention}, today’s your special day!",
                color=color
            )
            embed.add_field(name="🎉 Wishes", value=f"{theme_msg}\nWishing you joy, creativity!", inline=False)
            embed.set_footer(text="From your friendly Discord bot ❤️")
            embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/4966/4966194.png")

            try:
                birthday_msg = await channel.send(embed=embed)
                thread = await birthday_msg.create_thread(name=f"🎈 Wish {user.name} here!")
                await thread.send(f"Drop your wishes for {user.mention}! 🎊")

                # Log the wish
                wished_log.setdefault(today_log_key, {})[str(user.id)] = {
                    "name": user.name,
                    "time": datetime.utcnow().isoformat()
                }
                save_wished_log(wished_log)

            except Exception as e:
                print(f"Error sending birthday wish to {user_id}:", e)





# Commands
@bot.command(name='setbirthday')
async def set_birthday(ctx, dob: str = None):
    if dob is None:
        await ctx.send(f"{ctx.author.mention}, enter your birthday in `DD-MM` format (e.g., 21-07).")

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            msg = await bot.wait_for('message', check=check, timeout=60)
            dob = msg.content.strip()
        except Exception:
            await ctx.send("⏰ Timeout. Try again using `!setbirthday DD-MM`.")
            return

    dob_clean = re.sub(r"[/.]", "-", dob)
    match = re.match(r"^(\d{1,2})-(\d{1,2})$", dob_clean)
    if match:
        day, month = match.groups()
        try:
            dob_with_year = f"1904-{int(day):02d}-{int(month):02d}"
            datetime.strptime(dob_with_year, "%Y-%d-%m")
            dob_formatted = f"{int(day):02d}-{int(month):02d}"
            birthdays = load_birthdays()
            birthdays[str(ctx.author.id)] = dob_formatted
            save_birthdays(birthdays)
            await ctx.send(f"✅ Birthday saved as `{dob_formatted}` for {ctx.author.mention}")
            return
        except ValueError as e:
            print(f"Birthday parse error: {e}")
    await ctx.send("⚠️ Invalid format. Use DD-MM (e.g., 21-07)")

@bot.command(name='setbirthdaychannel')
@commands.has_permissions(administrator=True)
async def set_birthday_channel(ctx, channel: discord.TextChannel = None):
    if not channel:
        await ctx.send("📍 Please mention a channel like `!setbirthdaychannel #birthdays`")
        return
    with open(birthday_channel_file, "w") as f:
        json.dump({"channel_id": channel.id}, f)
    await ctx.send(f"✅ Birthday channel set to {channel.mention}")

@bot.command(name='setotherbirthday')
@commands.has_permissions(administrator=True)
async def set_other_birthday(ctx, member: discord.Member = None, dob: str = None):
    """Admins can set another user's birthday using: !setotherbirthday @user DD-MM"""
    if not member or not dob:
        await ctx.send("📅 Usage: `!setotherbirthday @user DD-MM`")
        return

    dob = re.sub(r"[/.]", "-", dob.strip())
    match = re.match(r"^(\d{1,2})-(\d{1,2})$", dob)
    if match:
        day, month = match.groups()
        try:
            # Use leap year to validate (e.g., 1904)
            dob_with_year = f"1904-{int(day):02d}-{int(month):02d}"
            datetime.strptime(dob_with_year, "%Y-%d-%m")

            dob_formatted = f"{int(day):02d}-{int(month):02d}"
            birthdays = load_birthdays()
            birthdays[str(member.id)] = dob_formatted
            save_birthdays(birthdays)

            await ctx.send(f"✅ Birthday `{dob_formatted}` set for {member.mention} by {ctx.author.mention}")
        except ValueError as e:
            print(f"Date validation failed: {e}")
            await ctx.send("⚠️ Invalid date. Please use `DD-MM` format like `21-07`.")
    else:
        await ctx.send("⚠️ Format issue. Use `!setotherbirthday @user DD-MM`.")

@bot.command(name='mybirthday')
async def my_birthday(ctx):
    """Check your registered birthday."""
    birthdays = load_birthdays()
    user_id = str(ctx.author.id)

    if user_id in birthdays:
        await ctx.send(f"📅 Your birthday is set to `{birthdays[user_id]}` {ctx.author.mention}")
    else:
        await ctx.send(f"❌ {ctx.author.mention}, you haven't registered a birthday yet! Use `!setbirthday` to add yours.")

@bot.command(name='editbirthday')
async def edit_birthday(ctx, dob: str = None):
    """Edit your saved birthday in DD-MM format."""
    if dob is None:
        await ctx.send(f"{ctx.author.mention}, enter your new birthday in `DD-MM` format (e.g., 21-07).")

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            msg = await bot.wait_for('message', check=check, timeout=60)
            dob = msg.content.strip()
        except Exception:
            await ctx.send("⏰ You took too long. Try again using `!editbirthday DD-MM`.")
            return

    dob_clean = re.sub(r"[/.]", "-", dob)
    match = re.match(r"^(\d{1,2})-(\d{1,2})$", dob_clean)
    if match:
        day, month = match.groups()
        try:
            dob_with_year = f"1904-{int(day):02d}-{int(month):02d}"  # leap-year safe
            datetime.strptime(dob_with_year, "%Y-%d-%m")

            dob_formatted = f"{int(day):02d}-{int(month):02d}"
            birthdays = load_birthdays()
            birthdays[str(ctx.author.id)] = dob_formatted
            save_birthdays(birthdays)

            await ctx.send(f"✏️ Birthday updated to `{dob_formatted}` for {ctx.author.mention}")
            return
        except ValueError as e:
            print(f"Edit parse error: {e}")
    await ctx.send("⚠️ Invalid format. Use DD-MM (e.g., 21-07)")

@bot.command(name='editotherbirthday')
@commands.has_permissions(administrator=True)
async def edit_other_birthday(ctx, member: discord.Member = None, dob: str = None):
    """Admins can edit another user's birthday using: !editotherbirthday @user DD-MM"""
    if not member or not dob:
        await ctx.send("✏️ Usage: `!editotherbirthday @user DD-MM`")
        return

    dob_clean = re.sub(r"[/.]", "-", dob.strip())
    match = re.match(r"^(\d{1,2})-(\d{1,2})$", dob_clean)
    if match:
        day, month = match.groups()
        try:
            dob_with_year = f"1904-{int(day):02d}-{int(month):02d}"
            datetime.strptime(dob_with_year, "%Y-%d-%m")

            dob_formatted = f"{int(day):02d}-{int(month):02d}"
            birthdays = load_birthdays()
            birthdays[str(member.id)] = dob_formatted
            save_birthdays(birthdays)

            await ctx.send(f"📝 Birthday for {member.mention} updated to `{dob_formatted}` by {ctx.author.mention}")
        except ValueError as e:
            print(f"Edit error: {e}")
            await ctx.send("⚠️ That date doesn’t seem valid. Use `DD-MM` format like `21-07`.")
    else:
        await ctx.send("⚠️ Format issue. Use: `!editotherbirthday @user DD-MM`")

@bot.command(name='deletebirthday')
async def delete_birthday(ctx):
    """Delete your stored birthday."""
    birthdays = load_birthdays()
    user_id = str(ctx.author.id)

    if user_id in birthdays:
        del birthdays[user_id]
        save_birthdays(birthdays)
        await ctx.send(f"🗑️ Your birthday has been removed, {ctx.author.mention}.")
    else:
        await ctx.send(f"❌ No birthday found for you, {ctx.author.mention}.")

@bot.command(name='deleteotherbirthday')
@commands.has_permissions(administrator=True)
async def delete_other_birthday(ctx, member: discord.Member = None):
    """Admins can delete another user's birthday using: !deleteotherbirthday @user"""
    if not member:
        await ctx.send("🗑️ Usage: `!deleteotherbirthday @user`")
        return

    birthdays = load_birthdays()
    user_id = str(member.id)

    if user_id in birthdays:
        del birthdays[user_id]
        save_birthdays(birthdays)
        await ctx.send(f"✅ Birthday for {member.mention} has been removed by {ctx.author.mention}.")
    else:
        await ctx.send(f"❌ No birthday found for {member.mention}.")



@bot.command(name='testbirthday')
@commands.has_permissions(administrator=True)
async def test_birthday(ctx):
    await check_birthdays()
    await ctx.send("🔍 Birthday check triggered manually.")

@bot.command(name='helps')
async def custom_help(ctx):
    embed = discord.Embed(
        title="📘 Birthday Bot Commands",
        description="Here's a list of what I can do!",
        color=discord.Color.blurple()
    )
    embed.set_thumbnail(url="https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExY3FramdpeWNudnBueWc4YXBtMTJ4NXRnM3E3azFla2hhbmFvM250cCZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/mgAgjH8JU55jq/giphy.gif")  # animated banner

    embed.add_field(name="!setbirthday", value="Set your own birthday", inline=False)
    embed.add_field(name="!editbirthday", value="Edit your saved birthday", inline=False)
    embed.add_field(name="!mybirthday", value="View your registered birthday", inline=False)
    embed.add_field(name="!deletebirthday", value="Delete your birthday entry", inline=False)
    embed.add_field(name="!setotherbirthday @user DD-MM", value="(Admin) Set someone else's birthday", inline=False)
    embed.add_field(name="!editotherbirthday @user DD-MM", value="(Admin) Edit someone else's birthday", inline=False)
    embed.add_field(name="!deleteotherbirthday @user", value="(Admin) Delete someone else's birthday", inline=False)
    embed.add_field(name="!upcomingbirthdays", value="Shows the next 10 upcoming birthdays", inline=False)
    embed.add_field(name="!setbirthdaychannel #channel", value="(Admin) Set the channel for birthday announcements", inline=False)
    embed.add_field(name="!testbirthday", value="(Admin) Manually trigger birthday check", inline=False)
    embed.set_footer(text="Birthday Bot by Mathews 🎂")
    await ctx.send(embed=embed)

@bot.command(name='upcomingbirthdays')
async def upcoming_birthdays(ctx):
    """Show the next 10 upcoming birthdays."""
    birthdays = load_birthdays()
    today = datetime.now()
    upcoming = []

    for user_id, dob in birthdays.items():
        try:
            day, month = map(int, dob.split("-"))
            # Use current year for comparison, adjust for past dates
            bday_this_year = datetime(today.year, month, day)
            if bday_this_year < today:
                bday_this_year = datetime(today.year + 1, month, day)
            upcoming.append((user_id, bday_this_year))
        except ValueError:
            continue  # skip invalid dates

    upcoming.sort(key=lambda x: x[1])
    top_birthdays = upcoming[:10]

    if not top_birthdays:
        await ctx.send("😔 No upcoming birthdays found.")
        return

    embed = discord.Embed(
        title="🎂 Upcoming Birthdays",
        color=discord.Color.magenta()
    )

    for user_id, bday in top_birthdays:
        user = await bot.fetch_user(int(user_id))
        days_left = (bday - today).days
        formatted = bday.strftime("%d-%m")
        embed.add_field(
            name=f"{user.name}",
            value=f"🗓️ `{formatted}` • in {days_left} day{'s' if days_left != 1 else ''}",
            inline=False
        )

    await ctx.send(embed=embed)



# Run the Bot
bot.run(token, log_handler=handler, log_level=logging.DEBUG)
