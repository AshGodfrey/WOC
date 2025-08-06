from keep_alive import keep_alive
keep_alive()

import os
import json
import time
import random
import datetime
import asyncio
import re

import discord
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from replit import db

import helpers
import characters
import players
import tags
import admin_commands

intents = discord.Intents.all()
intents.members = True
client = commands.Bot(command_prefix='-', intents=intents)

TOKEN = os.environ['token']
CHANNELS = {
    'webhooks':     1125123474134945792,
    'applications': 1129460613509292162,
    'tags':         1129461412465492099,
    'accepted':     1129460673596887141,
    'plot_hooks':   1129460842199519514,
}
AUTHORIZED_USER_IDS = {484491528128167955, 216674599427899393,
                       1071575781458854049, 276839441304125440}


def extract_gif_url(soup):
    img = soup.find('img', class_='mp-gif')
    return img['src'] if img and img.has_attr('src') else None


def extract_infogrid(soup, grid_id):
    node = soup.find('mp-infogrid', {'id': grid_id})
    if not node:
        return None
    child = node.find('scrolltrait') or node.find('c')
    return child.text.strip() if child else None


def build_character_data(soup, author, content_url):
    # Core profile fields from infogrid
    moniker = extract_infogrid(soup, 'moniker') or ''
    region = extract_infogrid(soup, 'charregion') or ''
    station = extract_infogrid(soup, 'station') or ''
    age = extract_infogrid(soup, 'age') or ''

    # Character name and title tags
    name_tag = soup.find('charactername')
    char_name = name_tag.text.strip() if name_tag else ''

    title_tag = soup.find('charactertitle')
    char_title = title_tag.text.strip() if title_tag else ''

    # Avatar: custom vattel-top2 wrapper
    img_tag = soup.select_one('vattel-top2 img')
    img_url = img_tag['src'] if img_tag and img_tag.has_attr('src') else ''

    # GIF URL if present
    gif_url = extract_gif_url(soup) or ''

    # Hooks: collect from <hook> elements
    hooks = [h.text.strip() for h in soup.find_all('hook') if h.text.strip()]

    return {
        'img_url': img_url,
        'gif_url': gif_url,
        'profile_url': content_url or '',
        'character_name': char_name,
        'moniker': moniker,
        'title': char_title,
        'region': region,
        'station': station,
        'age': age,
        'character_class': '',  # no <mainprofile> in markup
        'hooks': json.dumps(hooks),
        'player_name': author.name if author else 'Unknown',
        'player_avatar': str(author.avatar.url) if author else '',
        'player_id': author.id if author else 0,
    }

@client.event
async def on_ready():
    print(f'{client.user} connected')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    content = message.content.strip()

    if content == '!dump-html':
        db_char = db.get('some_character_key')
        soup = helpers.soup(db_char['profile'])
        await message.channel.send('HTML dumped to console.')
        return

    if content.startswith('!player'):
        await handle_player(message)
    elif message.channel.id == CHANNELS['applications'] and content.startswith('!accept'):
        await handle_accept(message)
    elif content.startswith('!character'):
        await handle_character(message)
    elif content.startswith('!notify'):
        await handle_notify(message)
    elif content.startswith('!my-activity'):
        await handle_activity(message)
    elif content.startswith('!update'):
        # parse the character key from the message
        char = helpers.get_character_name(message.content)
        # clear the cache so next !character will rebuild it
        helpers.delete_cache(f'character:{char}')
        await message.channel.send(f'Cache cleared for {char}')
    elif content.startswith('!tag') or message.channel.id == CHANNELS['webhooks']:
        await asyncio.sleep(5)
        await tags.handle_tags(client, CHANNELS['tags'])
    elif content.startswith('!choose '):
        await handle_choose(message)
    elif content.startswith('!roll '):
        await handle_roll(message)
    elif content.startswith('!roll-region'):
        await handle_roll_region(message)
    elif message.author.id in AUTHORIZED_USER_IDS:
        await admin_commands.handle_admin_command(message)

async def handle_accept(message):
    channel = client.get_channel(CHANNELS['applications'])
    msgs = [m async for m in channel.history(limit=2)]
    soup = helpers.soup(msgs[1].content.strip())
    character = soup.find('charactername').text.strip().lower()

    db[character] = {
        "profile": msgs[1].content.strip(),
        "player": msgs[1].author.id,
        "last_post_date": "",
    }

    data = build_character_data(soup, msgs[1].author, msgs[1].content.strip())
    cache_key = f'character:{character}'
    helpers.write_to_cache(cache_key, data)

    for m in msgs:
        await m.delete()

    emb = characters.character_embed(character, data)
    await helpers.send_embed(client, CHANNELS['accepted'], emb)

async def handle_character(message):
    char = characters.get_character_name(message.content)
    cache_key = f'character:{char}'
    cached = helpers.check_cache(cache_key)
    if cached:
        emb = characters.character_embed(char, helpers.convert_to_strings(cached))
        return await helpers.send_embed(client, CHANNELS['plot_hooks'], emb)
    db_char = db[char]
    soup = helpers.soup(db_char['profile'])
    player_obj = await client.fetch_user(db_char['player'])
    data = build_character_data(soup, player_obj, db_char['profile'])
    helpers.write_to_cache(cache_key, data)
    emb = characters.character_embed(char, data)
    await helpers.send_embed(client, CHANNELS['plot_hooks'], emb)

async def handle_notify(message):
    parts = message.content.split()
    if len(parts) != 2 or not parts[1].isdigit():
        return await message.channel.send("Usage: !notify <minutes>")
    minutes = int(parts[1])
    key = f"{message.author.id}-{int(time.time()) + minutes * 60}"
    helpers.redis_client.set(key, message.channel.id)
    await message.channel.send(f"Timer set for {minutes} minute(s).")

async def handle_activity(message):
    await message.channel.send("Building your activity report… one moment.")
    now = datetime.datetime.utcnow()
    cutoff = now - datetime.timedelta(days=14)
    me = str(message.author.id)

    raw_chars = players.find_characters_by_player(me)
    my_chars = list(raw_chars)
    if not my_chars:
        return await message.channel.send("You have no characters in the database.")

    active, inactive = [], []
    for char in my_chars:
        entry = db.get(char)
        if not hasattr(entry, 'get'):
            continue
        raw_date = entry.get('last_post_date')
        dt = None
        if raw_date:
            s = str(raw_date).strip()
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
                try:
                    dt = datetime.datetime.strptime(s, fmt)
                    break
                except ValueError:
                    dt = None
            if not dt:
                try:
                    dt = datetime.datetime.fromisoformat(s)
                except:
                    dt = None
        title = char.title()
        if dt and dt >= cutoff:
            active.append((title, dt.strftime("%Y-%m-%d")))
        else:
            tag = dt.strftime("%Y-%m-%d") if dt else "no posts recorded"
            inactive.append(f"{title} ({tag})")

    color = discord.Color.green() if active else discord.Color.red()
    embed = discord.Embed(color=color)
    display = f"{message.author.display_name} ({message.author.name}#{message.author.discriminator})"
    embed.set_author(name=display, icon_url=message.author.display_avatar.url)
    if active:
        embed.add_field(name="🟢 Active Characters",
                        value="\n".join(f"• **{n}** — {d}" for n, d in active),
                        inline=False)
    if inactive:
        val = ", ".join(inactive)
        embed.add_field(name="⚪️ Inactive Characters",
                        value=val if len(val) <= 1024 else "Too many to display.",
                        inline=False)
    await message.channel.send(embed=embed)
    await message.channel.send("Report complete! 🚀")

async def handle_update(message):
    char = characters.get_character_name(message.content)
    helpers.delete_cache(f'character:{char}')
    await message.channel.send(f'Cache cleared for {char}')

async def handle_choose(message):
    opts = [opt.strip() for opt in message.content[len('!choose '):].split(',')]
    choice = random.choice(opts)
    await message.channel.send(choice)

async def handle_roll(message):
    match = re.match(r'^!roll (\d+)d(\d+)((?:[-+*]\d+)*)', message.content)
    if not match:
        return await message.channel.send("Use XdY[+|-|*]Z")
    num, sides, mods = match.groups()
    num, sides = int(num), int(sides)
    if num < 1 or sides < 1:
        return await message.channel.send("Dice and sides must be ≥1")
    rolls = [random.randint(1, sides) for _ in range(num)]
    total = sum(rolls)
    for m in re.findall(r'[-+*]\d+', mods):
        op, val = m[0], int(m[1:])
        if op == '+':
            total += val
        elif op == '-':
            total -= val
        elif op == '*':
            total *= val
    await message.channel.send(f"🎲 Rolls: {', '.join(map(str, rolls))} {mods}\nTotal: {total}")

async def handle_roll_region(message):
    region = random.choice(db['region'])
    await message.channel.send(region)

# ------------------ Scheduler & Timers ------------------
scheduler = AsyncIOScheduler()
scheduler.add_job(lambda: players.cache_characters_by_player(), 'cron', hour=0, minute=0)


async def check_timers():
    """
    Periodically checks Redis for timer keys in the format "<userId>-<timestamp>" and sends notifications.
    Safely skips any keys that don't match the expected pattern.
    """
    while True:
        now = int(time.time())
        for key in helpers.redis_client.keys('*'):
            try:
                decoded = key.decode()
                # Ensure the key contains exactly one dash separating user and timestamp
                user_str, ts_str = decoded.split('-', 1)
                ts = int(ts_str)
            except (ValueError, AttributeError):
                # Skip keys that don't match the expected "user-timestamp" format
                continue

            if now >= ts:
                channel_id = helpers.redis_client.get(key)
                try:
                    channel_id = int(channel_id.decode())
                except Exception:
                    continue

                ch = helpers.client.get_channel(channel_id)
                if ch:
                    await ch.send(f'<@{user_str}> your timer is up!')
                helpers.redis_client.delete(key)

        await asyncio.sleep(10)


@client.event
async def setup_hook():
    client.loop.create_task(check_timers())
    scheduler.start()

client.run(TOKEN)
