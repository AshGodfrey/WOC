from keep_alive import keep_alive
keep_alive()
import os
import discord
import json
from discord.ext import commands
import characters
import helpers
import players
import tags
import time
import admin_commands
import asyncio
import random
import re
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from replit import db
intents = discord.Intents.all()
intents.members = True
client = commands.Bot(command_prefix='-', intents=intents)
token = os.environ['token']
webhooks_channel = 1125123474134945792
applications_channel = 1129460613509292162
tags_channel = 1129461412465492099
accepted_channel = 1129460673596887141
plot_hooks_channel = 1129460842199519314
test_channel = 1125111458020196443
#https://windsofchangerp.jcink.net/index.php?act=Search&CODE=getactive
AUTHORIZED_USER_IDS = [
  #ash
  484491528128167955, 
  #hana
  216674599427899393, 
  #paige 
  1071575781458854049,
  #dixie 
  276839441304125440,]

#not in use yet
async def handle_character_data(character):
  character_data = helpers.check_cache('character:' + character)
  if character_data:
    converted_data = helpers.convert_to_strings(character_data)
    return converted_data
  
@client.event
async def on_ready():
  print(f'{client.user} has connected to Discord!')
   
@client.event
async def on_message(message):
  if message.author == client.user:
      return

  if message.content.startswith('!notify'):
    details = message.content.split(' ')
    if len(details) != 2 or not details[1].isdigit():
        await message.channel.send("Please specify the timer duration in minutes using `!timer <minutes>`.")
        return

    minutes = int(details[1])
    end_time = int(time.time()) + (minutes * 60)
    timer_id = f"{message.author.id}-{end_time}"

    # Store the timer in Redis
    helpers.redis_client.set(timer_id, message.channel.id)

    await message.channel.send(f"Timer set for {minutes} minute(s).")
    
  if message.content.startswith('!player'):
    player = message.content.split(' ')
    player_id = helpers.tag_to_id(player[1].strip())
    player_characters = players.find_characters_by_player(player_id)
    if player_characters == []: 
      print("no characters found")
    else:
      for character in player_characters:
        character_data = helpers.check_cache('character:' + character)
        if character_data:
           converted_data = helpers.convert_to_strings(character_data)
        embed = characters.character_embed(character, converted_data)
        await helpers.send_embed(client, message.channel.id, embed)
      else:
        character = db[character]
        soup = helpers.soup(character['profile'])
        cache_key = 'character:' + character
        data = {
            'img_url': (soup.find("top").find("img"))['src'],
            'region': (soup.find("pfield", {"id": "region"})).find('c').text,
            'character_class': soup.find("mainprofile")['class'][0],
            'moniker': (soup.find("pfield", {"id": "moniker"})).find('c').text,
            'station': (soup.find("pfield", {"id": "station"})).find('c').text,
            'age': (soup.find("pfield", {"id": "age"})).find('c').text,
            'hooks': json.dumps([str(hook) for hook in soup.find_all("hook")]),
            'player_name': "need to fix logic",
            'player_avatar': "need to fix logic",
            'player_id': player_id,
            'profile_url': "need to fix logic",
        }
        helpers.write_to_cache(cache_key, data)
        embed = characters.character_embed(character, data)
        await helpers.send_embed(client, plot_hooks_channel, embed)
      
  #accept a character
  if message.channel.id == applications_channel:
    if message.content.startswith('!accept'):
      #get last two messages
      channel = client.get_channel(applications_channel)
      messages = [message async for message in channel.history(limit=2)]
      soup = helpers.soup(messages[1].content.strip())
      character = soup.find("name").text.strip().lower()
      
      #add character to the database
      characters.update_character(character, str(messages[1].author.id), messages[1].content.strip())

      #add character to cache
      # Key for the Hashmap
      cache_key = 'character:' + character
      # Dictionary of key-value pairs to set in the Hashmap
      player_avatar = messages[1].author.avatar.url if messages[1].author.avatar is not None and messages[1].author.avatar.url else 'https://assets-global.website-files.com/6257adef93867e50d84d30e2/636e0a6a49cf127bf92de1e2_icon_clyde_blurple_RGB.png'

      data = {
          'img_url': (soup.find("top").find("img"))['src'],
          'region': (soup.find("pfield", {"id": "region"})).find('c').text,
          'character_class': soup.find("mainprofile")['class'][0],
          'moniker': (soup.find("pfield", {"id": "moniker"})).find('c').text,
          'station': (soup.find("pfield", {"id": "station"})).find('c').text,
          'age': (soup.find("pfield", {"id": "age"})).find('c').text,
          'hooks': json.dumps([str(hook) for hook in soup.find_all("hook")]),
          'player_name': messages[1].author.name,
          'player_avatar': player_avatar,
          'player_id': messages[1].author.id,
          'profile_url': messages[1].content.strip(),
      }
      # Set key-value pairs in bulk using hmset()
      helpers.write_to_cache(cache_key, data)
      
      #delete last two messages
      for message in messages: 
        await message.delete()
      #await message.channel.send(character + 'accepted')

      embed = characters.character_embed(character, data)
      await helpers.send_embed(client, accepted_channel, embed)

  #Handle Tags
  if message.channel.id == webhooks_channel:
    time.sleep(5)
    await tags.handle_tags(client, tags_channel)

  if message.content.startswith('!tag'):
    time.sleep(5)
    await tags.handle_tags(client, tags_channel)
    
# Allows a player to "update" the cache
  if message.content.startswith('!update'):
    character = characters.get_character_name(message.content)
    helpers.delete_cache('character:' + character)
    await message.channel.send('Updated: ' + character)


# Gets a character's info + sends embed to channel
  if message.content.startswith('!character'):
    character = characters.get_character_name(message.content)
    character_data = helpers.check_cache('character:' + character)
    #cache hit
    if character_data:
      converted_data = helpers.convert_to_strings(character_data)
      embed = characters.character_embed(character, converted_data)
      await helpers.send_embed(client, plot_hooks_channel, embed)
    #cache miss
    else:
        db_character = db[character]
        soup = helpers.soup(db_character['profile'])
        cache_key = 'character:' + character

        if character == "the many-faced god":
          data = {
            'img_url': (soup.find("top").find("img"))['src'],
            'region': (soup.find("pfield", {"id": "region"})).find('c').text,
            'character_class': soup.find("mainprofile")['class'][0],
            'moniker': (soup.find("pfield", {"id": "moniker"})).find('c').text,
            'station': (soup.find("pfield", {"id": "station"})).find('c').text,
            'age': (soup.find("pfield", {"id": "age"})).find('c').text,
            'hooks': json.dumps([str(hook) for hook in soup.find_all("hook")]),
            'player_name': "The Mancy-Faced God",
            'player_avatar': "https://i.ytimg.com/vi/JkdMGgh87nw/hqdefault.jpg",
            'player_id': "",
            'profile_url': db_character['profile'],
          }
        # Fetch the Discord user using the stored player ID
        else: 
          player = await client.fetch_user(db_character['player'])  # Assuming `client` is your Discord bot client
  
          data = {
              'img_url': (soup.find("top").find("img"))['src'],
              'region': (soup.find("pfield", {"id": "region"})).find('c').text,
              'character_class': soup.find("mainprofile")['class'][0],
              'moniker': (soup.find("pfield", {"id": "moniker"})).find('c').text,
              'station': (soup.find("pfield", {"id": "station"})).find('c').text,
              'age': (soup.find("pfield", {"id": "age"})).find('c').text,
              'hooks': json.dumps([str(hook) for hook in soup.find_all("hook")]),
              'player_name': player.name,
              'player_avatar': str(player.avatar.url),
              'player_id': player.id,
              'profile_url': db_character['profile'],  # Adjusted to use the DB value for the profile URL
          }
        helpers.write_to_cache(cache_key, data)
        embed = characters.character_embed(character, data)
        await helpers.send_embed(client, plot_hooks_channel, embed)

#start admin commands
  if message.author.id in AUTHORIZED_USER_IDS:
    await admin_commands.handle_admin_command(message)


  if message.content.startswith('!choose-'):
    # Handling key-based selection
    key = message.content.split('!choose-')[1].strip()
    values = db[key]
    await message.channel.send(key)
    # Randomly select one of the values
    rolled_value = random.choice(values)

    # Send the result back to the channel
    await message.channel.send(f"{rolled_value}")
    return

  if message.content.startswith('!choose '): 
        content = message.content[len('!choose '):]  
        items = [item.strip() for item in content.split(',')]
        chosen_item = random.choice(items)
        await message.channel.send(chosen_item)
        return

  if message.content.startswith('!roll '):
    if message.content.startswith('!roll '):
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
          operator = modifier[0]  # The operator is the first character
          mod_value = int(modifier[1:])  # The rest is the number
          if operator == '+':
              modified_total += mod_value
          elif operator == '-':
              modified_total -= mod_value
          elif operator == '*':
              modified_total *= mod_value

      # Format the results string and modifier for output
      results_str = ", ".join(map(str, results))
      # Send back the individual dice results with modifiers and the final total
      await message.channel.send(f"🎲 Rolls: {results_str} {modifiers}\nTotal: {modified_total}")


  if message.content.startswith('!roll-region'):
    regions = db["region"]
    chosen_region = random.choice(regions)
    await message.channel.send(chosen_region)
    return 

  if message.content.startswith('!roll-characters'):
    player_id = str(message.author.id)
    player_characters = db[player_id]
    chosen_item = random.choice(player_characters)
    try: 
      data = await handle_character_data(chosen_item)
      embed = characters.mini_embed(chosen_item, data)
      await message.channel.send(embed=embed)
      return
    except Exception as e: 
      await message.channel.send(chosen_item)
      await message.channel.send(f"An error occurred getting character card, notify Ashe: {str(e)}")
      return
    
# Scheduler setup
scheduler = AsyncIOScheduler()

async def scheduled_job():
  await players.cache_characters_by_player()

# Add the job to the scheduler
scheduler.add_job(scheduled_job, 'cron', hour='0', minute='0')  # Runs at midnight
# Add the job to the scheduler
scheduler.add_job(scheduled_job, 'cron', hour='0', minute='0')  # Runs at midnight

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
            await asyncio.sleep(10)  # Check every 10 seconds
        except Exception as e:
            print(f"An error occurred in check_timers: {e}")

async def setup_hook():
    # Create the task for check_timers
    client.loop.create_task(check_timers())
    # Start the scheduler in the same event loop
    scheduler.start()

client.setup_hook = setup_hook  # Setup the hook correctly


client.run(token)