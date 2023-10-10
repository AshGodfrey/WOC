import characters
from replit import db
import helpers
import discord
import store
import json
import discord.utils  
from discord.ext import commands
import re

intents = discord.Intents.all()
intents.members = True
client = commands.Bot(command_prefix='-', intents=intents)

async def handle_delete_character(message):
  character = characters.get_character_name(message.content)
  try:
      del db[character]
  except:
      print("not in DB")
  helpers.delete_cache('character:' + character)
  await message.channel.send('Removed: ' + character)

async def handle_check_character(message):
  character = characters.get_character_name(message.content)
  character_data = helpers.check_cache('character:' + character)
  #cache hit
  if character_data:
    await message.channel.send("character still in cache")
  else: 
    await message.channel.send("removed")

async def handle_set_all_colors(message):
  store.set_all_colors()

async def handle_set_color(message):
  try: 
    value = message.content.split("(")
    value = value[1].split(")")
    array = message.content.split(" ")
    group = array[1]
    value = value[0]
    store.set_color(group, value)
    await message.channel.send(group + " set with rgb value of " + value)
  except: 
    await message.channel.send("there was an error adding this, if you're not sure why, notify ashe")

async def handle_get_colors(message):
  await message.channel.send(db["color"])

async def handle_get_color_for_group(message):
  group = message.content.split(" ")
  color = store.get_color_for_group(group[1])
  await message.channel.send(color)

async def handle_delete_cache(message):
  character = characters.get_character_name(message.content)
  helpers.delete_cache('character:' + character)
  await message.channel.send('Removed: ' + character)

async def handle_cache(message):
  character = characters.get_character_name(message.content)
  soup = helpers.soup(db[character]['profile'])
  #add character to cache
    # Key for the Hashmap
  cache_key = 'character:' + character
  # Fetch the User object for the player
  playerDiscord = await client.fetch_user(db[character]['player'])
  avatar_url = playerDiscord.avatar.url  # Get the avatar hash
  player_name = playerDiscord.name  # Get the user ID

#
  # Dictionary of key-value pairs to set in the Hashmap
  data = {
      'img_url': (soup.find("top").find("img"))['src'],
      'region': (soup.find("pfield", {"id": "region"})).find('c').text,
      'character_class': soup.find("mainprofile")['class'][0],
      'moniker': (soup.find("pfield", {"id": "moniker"})).find('c').text,
      'station': (soup.find("pfield", {"id": "station"})).find('c').text,
      'age': (soup.find("pfield", {"id": "age"})).find('c').text,
      'hooks': json.dumps([str(hook) for hook in soup.find_all("hook")]),
      'player_name': player_name,
      'player_avatar': avatar_url,
      'player_id': db[character]['player'],
      'profile_url': db[character]['profile']
  }
  # Set key-value pairs in bulk using hmset()
  helpers.write_to_cache(cache_key, data)
  embed = characters.character_embed(character, data)
  await helpers.send_embed(client, message.channel.id, embed)


async def update_character(message):
  matches = re.findall(r'\[(.*?)\]', message.content)
  character, key, value = matches
  db[character][key] = value
  await message.channel.send(db[character])
    
#all admin commands: 
command_list = {
    '!delete-character': handle_delete_character,
    '!check-character': handle_check_character,
    '!set-all-colors': handle_set_all_colors,
    '!set-color': handle_set_color,
    '!get-colors': handle_get_colors,
    '!get-color-for-group': handle_get_color_for_group,
    '!delete-cache': handle_delete_cache,
    '!cache': handle_cache,
    '!update-character': update_character,
}
  
async def handle_admin_command(message):
  for command, handler in command_list.items():
    if message.content.startswith(command):
      await handler(message)
      return