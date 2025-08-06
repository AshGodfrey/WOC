
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

# ------------------ Bot Setup ------------------
intents = discord.Intents.all()
intents.members = True
client = commands.Bot(command_prefix='-', intents=intents)

# ------------------ Constants ------------------
TOKEN = os.environ['token']
CHANNELS = {
    'webhooks':     1125123474134945792,
    'applications': 1129460613509292162,
    'tags':         1129461412465492099,
    'accepted':     1129460673596887141,
    'plot_hooks':   1129460842199519314,
    'test':         1125111458020196443,
}
AUTHORIZED_USER_IDS = {484491528128167955, 216674599427899393,
                       1071575781458854049, 276839441304125440}

# ------------------ Helper Functions ------------------
async def handle_character_data(character):
    character_data = helpers.check_cache('character:' + character)
    if character_data:
        converted_data = helpers.convert_to_strings(character_data)
        return converted_data
    return None

def build_character_data(soup, author, content_url):
    # Use centralized parsing function
    parsed_data = helpers.parse_character_from_soup(soup)
    
    print(f"=== BUILD CHARACTER DATA DEBUG ===")
    print(f"Parsed age from soup: '{parsed_data.get('age', 'N/A')}'")
    print(f"Parsed region: '{parsed_data.get('region', 'N/A')}'")
    print("==================================")
    
    return {
        **parsed_data,
        'player_name': author.name if author else "Unknown",
        'player_avatar': str(author.avatar.url) if author and author.avatar else 'https://assets-global.website-files.com/6257adef93867e50d84d30e2/636e0a6a49cf127bf92de1e2_icon_clyde_blurple_RGB.png',
        'player_id': author.id if author else 0,
        'profile_url': content_url or "",
    }

# ------------------ Events ------------------
@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    content = message.content.strip()

    if content.startswith('!notify'):
        await handle_notify(message)
    elif content.startswith('!player'):
        await handle_player(message)
    elif message.channel.id == CHANNELS['applications'] and content.startswith('!accept'):
        await handle_accept(message)
    elif content.startswith('!character'):
        await handle_character(message)
    elif content.startswith('!my-activity'):
        await handle_activity(message)
    elif content.startswith('!update'):
        await handle_update(message)
    elif content.startswith('!tag') or message.channel.id == CHANNELS['webhooks']:
        await asyncio.sleep(5)
        await tags.handle_tags(client, CHANNELS['tags'])
    elif content.startswith('!choose-'):
        await handle_choose_key(message)
    elif content.startswith('!choose '):
        await handle_choose(message)
    elif content.startswith('!roll-region'):
        await handle_roll_region(message)
    elif content.startswith('!roll-characters'):
        await handle_roll_characters(message)
    elif content.startswith('!roll '):
        await handle_roll(message)
    elif message.author.id in AUTHORIZED_USER_IDS:
        await admin_commands.handle_admin_command(message)

# ------------------ Command Handlers ------------------
async def handle_notify(message):
    details = message.content.split(' ')
    if len(details) != 2 or not details[1].isdigit():
        await message.channel.send("Please specify the timer duration in minutes using `!notify <minutes>`.")
        return

    minutes = int(details[1])
    end_time = int(time.time()) + (minutes * 60)
    timer_id = f"{message.author.id}-{end_time}"

    helpers.redis_client.set(timer_id, message.channel.id)
    await message.channel.send(f"Timer set for {minutes} minute(s).")

async def handle_player(message):
    parts = message.content.split(' ')
    if len(parts) < 2:
        return await message.channel.send("Usage: !player <@user>")
    
    player_id = helpers.tag_to_id(parts[1].strip())
    player_characters = players.find_characters_by_player(player_id)
    
    if not player_characters:
        await message.channel.send("No characters found")
        return

    for character in player_characters:
        character_data = helpers.check_cache('character:' + character)
        if character_data:
            converted_data = helpers.convert_to_strings(character_data)
            embed = characters.character_embed(character, converted_data)
            await helpers.send_embed(client, message.channel.id, embed)
        else:
            # Cache miss - build data and cache it
            db_character = db[character]
            soup = helpers.soup(db_character['profile'])
            cache_key = 'character:' + character
            
            try:
                player = await client.fetch_user(db_character['player'])
                data = build_character_data(soup, player, db_character['profile'])
            except:
                data = build_character_data(soup, None, db_character['profile'])
                data['player_name'] = "Unknown Player"
                data['player_id'] = player_id
            
            helpers.write_to_cache(cache_key, data)
            embed = characters.character_embed(character, data)
            await helpers.send_embed(client, CHANNELS['plot_hooks'], embed)

async def handle_accept(message):
    channel = client.get_channel(CHANNELS['applications'])
    messages = [message async for message in channel.history(limit=2)]
    soup = helpers.soup(messages[1].content.strip())
    
    # Try different possible tag names for character name
    character_name = None
    for tag in ['name', 'charactername']:
        name_tag = soup.find(tag)
        if name_tag:
            character_name = name_tag.text.strip().lower()
            break
    
    if not character_name:
        await message.channel.send("Could not find character name in application")
        return
    
    # Save character to database
    characters.update_character(character_name, str(messages[1].author.id), messages[1].content.strip())
    
    # Build and cache character data
    data = build_character_data(soup, messages[1].author, messages[1].content.strip())
    cache_key = 'character:' + character_name
    helpers.write_to_cache(cache_key, data)
    
    # Delete application messages
    for msg in messages:
        await msg.delete()
    
    # Send acceptance embed
    embed = characters.character_embed(character_name, data)
    await helpers.send_embed(client, CHANNELS['accepted'], embed)

async def handle_character(message):
    character = characters.get_character_name(message.content)
    cache_key = f'character:{character}'
    character_data = helpers.check_cache(cache_key)
    
    print(f"=== CHARACTER COMMAND DEBUG ===")
    print(f"Looking for character: '{character}'")
    print(f"Cache key: '{cache_key}'")
    print(f"Cache hit: {character_data is not None}")
    
    if character_data:
        converted_data = helpers.convert_to_strings(character_data)
        print(f"Using cached data: {converted_data}")
        embed = characters.character_embed(character, converted_data)
        await helpers.send_embed(client, CHANNELS['plot_hooks'], embed)
    else:
        # Cache miss - fetch from database
        if character not in db:
            await message.channel.send(f"Character '{character}' not found in database")
            return
            
        db_character = db[character]
        print(f"DB character data: {db_character}")
        
        # Fetch the profile page
        profile_url = db_character['profile']
        print(f"Fetching profile from: {profile_url}")
        
        try:
            soup = helpers.soup(profile_url)
            print(f"Soup fetched successfully, length: {len(str(soup))}")
        except Exception as e:
            print(f"Error fetching soup: {e}")
            await message.channel.send(f"Error fetching profile for {character}: {str(e)}")
            return
        
        if character == "the many-faced god":
            data = build_character_data(soup, None, db_character['profile'])
            data['player_name'] = "The Many-Faced God"
            data['player_avatar'] = "https://i.ytimg.com/vi/JkdMGgh87nw/hqdefault.jpg"
            data['player_id'] = ""
        else:
            try:
                player = await client.fetch_user(db_character['player'])
                data = build_character_data(soup, player, db_character['profile'])
            except Exception as e:
                print(f"Error fetching player: {e}")
                data = build_character_data(soup, None, db_character['profile'])
                data['player_name'] = "Unknown Player"
        
        print(f"Final character data: {data}")
        helpers.write_to_cache(cache_key, data)
        embed = characters.character_embed(character, data)
        await helpers.send_embed(client, CHANNELS['plot_hooks'], embed)
    print("===============================")

async def handle_activity(message):
    await message.channel.send("Building your activity report… one moment.")
    now = datetime.datetime.utcnow()
    cutoff = now - datetime.timedelta(days=14)
    me = str(message.author.id)

    try:
        raw_chars = players.find_characters_by_player(me)
        my_chars = list(raw_chars)
    except:
        return await message.channel.send("You have no characters in the database.")
    
    if not my_chars:
        return await message.channel.send("You have no characters in the database.")

    active, inactive = [], []
    for char in my_chars:
        entry = db.get(char)
        if not entry or not hasattr(entry, 'get'):
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
    character = characters.get_character_name(message.content)
    print(f"=== UPDATE COMMAND DEBUG ===")
    print(f"Character to update: '{character}'")
    
    cache_key = 'character:' + character
    print(f"Cache key: '{cache_key}'")
    
    # Check what's currently in cache before deletion
    old_cache_data = helpers.check_cache(cache_key)
    print(f"Cache data before deletion: {old_cache_data is not None}")
    if old_cache_data:
        converted_old = helpers.convert_to_strings(old_cache_data)
        print(f"Old cache sample: img_url='{converted_old.get('img_url', 'N/A')}', age='{converted_old.get('age', 'N/A')}', region='{converted_old.get('region', 'N/A')}'")
    
    helpers.delete_cache(cache_key)
    print(f"Cache deleted for: {cache_key}")
    
    # Rebuild the cache with fresh data
    try:
        if character not in db:
            await message.channel.send(f"Character '{character}' not found in database")
            print(f"Character '{character}' not found in database")
            return
            
        db_character = db[character]
        print(f"DB character data: {db_character}")
        
        profile_url = db_character['profile']
        print(f"Fetching profile from: {profile_url}")
        
        soup = helpers.soup(profile_url)
        print(f"Soup fetched successfully, length: {len(str(soup))}")
        
        try:
            player = await client.fetch_user(db_character['player'])
            print(f"Player fetched: {player.name} (ID: {player.id})")
            data = build_character_data(soup, player, db_character['profile'])
        except Exception as e:
            print(f"Error fetching player: {e}")
            data = build_character_data(soup, None, db_character['profile'])
            data['player_name'] = "Unknown Player"
        
        print(f"Character data built: {data}")
        
        helpers.write_to_cache(cache_key, data)
        print(f"Data written to cache with key: {cache_key}")
        
        # Verify cache was written
        new_cache_data = helpers.check_cache(cache_key)
        print(f"Cache verification after write: {new_cache_data is not None}")
        if new_cache_data:
            converted_new = helpers.convert_to_strings(new_cache_data)
            print(f"New cache sample: img_url='{converted_new.get('img_url', 'N/A')}', age='{converted_new.get('age', 'N/A')}', region='{converted_new.get('region', 'N/A')}'")
        
        await message.channel.send(f'Updated: {character}')
        
        # Send the updated embed to verify it worked
        embed = characters.character_embed(character, data)
        await helpers.send_embed(client, message.channel.id, embed)
        
    except Exception as e:
        print(f"Error in handle_update: {str(e)}")
        import traceback
        traceback.print_exc()
        await message.channel.send(f'Error updating {character}: {str(e)}')
    
    print("==============================")

async def handle_choose_key(message):
    key = message.content.split('!choose-')[1].strip()
    try:
        values = db[key]
        rolled_value = random.choice(values)
        await message.channel.send(f"{rolled_value}")
    except KeyError:
        await message.channel.send(f"Key '{key}' not found in database")

async def handle_choose(message):
    content = message.content[len('!choose '):]  
    items = [item.strip() for item in content.split(',')]
    chosen_item = random.choice(items)
    await message.channel.send(chosen_item)

async def handle_roll(message):
    match = re.search(r'^!roll (\d+)d(\d+)((?:[-+*]\d+)*)', message.content)
    if not match:
        await message.channel.send("Please use the format XdY[+|-|*]Z, where X is the number of dice, Y is the number of sides, and Z is an optional modifier.")
        return

    num_dice, sides, modifiers = match.groups()
    num_dice, sides = map(int, [num_dice, sides])

    if num_dice < 1 or sides < 1:
        await message.channel.send("Both the number of dice and the number of sides must be at least 1.")
        return

    # Roll the dice
    results = [random.randint(1, sides) for _ in range(num_dice)]
    total = sum(results)

    # Calculate the total with all modifiers applied
    modifiers_list = re.findall(r'[-+*]\d+', modifiers)
    modified_total = total

    for modifier in modifiers_list:
        operator = modifier[0]
        mod_value = int(modifier[1:])
        if operator == '+':
            modified_total += mod_value
        elif operator == '-':
            modified_total -= mod_value
        elif operator == '*':
            modified_total *= mod_value

    results_str = ", ".join(map(str, results))
    await message.channel.send(f"🎲 Rolls: {results_str} {modifiers}\nTotal: {modified_total}")

async def handle_roll_region(message):
    try:
        regions = db["region"]
        chosen_region = random.choice(regions)
        await message.channel.send(chosen_region)
    except KeyError:
        await message.channel.send("No regions found in database")

async def handle_roll_characters(message):
    player_id = str(message.author.id)
    try:
        player_characters = db[player_id]
        chosen_item = random.choice(player_characters)
        
        data = await handle_character_data(chosen_item)
        if data:
            embed = characters.mini_embed(chosen_item, data)
            await message.channel.send(embed=embed)
        else:
            await message.channel.send(chosen_item)
    except Exception as e:
        await message.channel.send(f"An error occurred getting character card, notify Ashe: {str(e)}")

# ------------------ Scheduler & Timers ------------------
scheduler = AsyncIOScheduler()

async def scheduled_job():
    await players.cache_characters_by_player()

scheduler.add_job(scheduled_job, 'cron', hour='0', minute='0')

async def check_timers():
    while True:
        try:
            current_time = int(time.time())
            for key in helpers.redis_client.keys("*"):
                key_parts = key.decode().split('-')
                if len(key_parts) == 2 and key_parts[1].isdigit():
                    end_time = int(key_parts[1])
                    if end_time <= current_time:
                        channel_id = int(helpers.redis_client.get(key).decode())
                        author_id = key_parts[0]
                        channel = client.get_channel(channel_id)
                        if channel:
                            await channel.send(f'<@{author_id}> your timer is up!')
                        else:
                            print(f"Invalid channel ID: {channel_id}")
                        helpers.redis_client.delete(key)
            await asyncio.sleep(10)
        except Exception as e:
            print(f"An error occurred in check_timers: {e}")

@client.event
async def setup_hook():
    client.loop.create_task(check_timers())
    scheduler.start()

client.run(TOKEN)
