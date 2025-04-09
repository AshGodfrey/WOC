import characters
import players
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

async def send_message_to_channel(message):
  # Use regex to capture the channel ID and the message content
  match = re.match(r'!send-message (\d+) (.+)', message.content, re.DOTALL)
  if not match:
      await message.channel.send(
          "Incorrect command format. Please use the format: !send <channel_id> <your message>"
      )
      return

  # Extracting the channel ID and message content from the regex match
  channel_id, msg_content = match.groups()

      # Attempt to fetch the channel from the API
  channel = await client.get_channel(int(channel_id))

  if channel:
      try:
          await channel.send(msg_content)
          await message.channel.send(f"Message sent to channel {channel_id}.")
      except discord.errors.Forbidden:
          await message.channel.send(f"Do not have permission to send messages to channel {channel_id}.")
      except discord.errors.HTTPException as e:
          await message.channel.send(f"Failed to send message to channel {channel_id}. Error: {e}")
  else:
      await message.channel.send(f"Could not find channel with ID {channel_id}.")

async def add_character_manually(message):
  # Use regex to capture the character name within brackets, the link, and the player Discord ID
  match = re.match(r'!add \[(.*?)\] (https?://\S+) (\d+)', message.content)
  if not match:
    await message.channel.send(
      "Incorrect command format. Please use the format: !add [character name] link <player Discord ID>"
    )
    return

  # Extracting the character name, link, and Discord ID from the regex match
  character_name, link, player_discord_id = match.groups()

  
  characters.update_character(character_name.lower().strip(), player_discord_id, link)
  
  await message.channel.send(
    f"Character '{character_name}' added successfully for user {player_discord_id}."
  )

async def get_raw_character_info(message):
  character = characters.get_character_name(message.content)
  await message.channel.send(db[character])

async def change_character_name(message):
  # Extract old and new names from the message content
  matches = re.findall(r'\[(.*?)\]', message.content)
  if len(matches) != 2:
    await message.channel.send(
      "Incorrect format. Please use: !change-name [old name] [new name]")
    return

  old_name, new_name = matches
  # Check if the old character exists in the database
  if old_name not in db:
    await message.channel.send(f"Character '{old_name}' not found.")
    return

  # Retrieve player ID and profile URL from the old entry
  player_id = db[old_name]['player']
  profile_url = db[old_name]['profile']

  # Create new database entry for the new name, preserving player ID and profile URL
  db[new_name] = db[old_name]  # Copy all data from old to new
  db[new_name]['player'] = player_id  # Ensure player ID is preserved
  db[new_name]['profile'] = profile_url  # Ensure profile URL is preserved
  del db[old_name]  # Remove old entry
  helpers.delete_cache(old_name)

  await message.channel.send(
    f"Character name changed from '{old_name}' to '{new_name}', preserving player ID and profile URL in both database and cache."
  )


async def delete_character(character, message):
  helpers.delete_cache('character:' + character)
  try:
    del db[character]
    await message.channel.send('Removed: ' + character)
  except:
    await message.channel.send(character + ': Not in DB')

async def handle_delete_character(message):
  character = characters.get_character_name(message.content)
  await delete_character(character, message)


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


async def handle_character_cache(message):
  await players.cache_characters_by_player()
  await message.channel.send("cached, I hope.")
  
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
    await message.channel.send(
      "there was an error adding this, if you're not sure why, notify ashe")


async def handle_set_regions(message):
  values = message.content.split(",")
  store.set_region(values)
  await message.channel.send(db["region"])

async def handle_set_choose(message):
  key, values_string = message.content.split(':', 1)
  key = key.split('!set-choose')[1].strip()
  values = values_string.split(",")
  store.set_something(key.lower(), values)
  return message.channel.send(db[KeyboardInterrupt])

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

async def get_user_characters(message):
  player = message.content.split(' ')
  await message.channel.send(players.find_characters_by_player(player[1]))

async def handle_delete_player(message):
    player = message.content.split(' ')
    print(player[1])

    characters_to_delete = players.find_characters_by_player(player[1])

    # Delete found characters with error handling
    for character in characters_to_delete:
        try:
            await delete_character(character, message)
        except Exception as e:
            # Log the error and move on to the next character
            print(f"Error deleting character {character}: {e}")

async def handle_check_cache (message):
   await message.channel.send(db["276839441304125440"])

#all admin commands:
command_list = {
  '!delete-character': handle_delete_character,
  '!check-character': handle_check_character,
  '!set-all-colors': handle_set_all_colors,
  '!set-color': handle_set_color,
  '!get-colors': handle_get_colors,
  '!set-regions': handle_set_regions,
  '!set-choose': handle_set_choose,
  '!get-color-for-group': handle_get_color_for_group,
  '!delete-cache': handle_delete_cache,
  '!cache': handle_cache,
  '!admin-force-update-character': update_character,
  '!delete-player': handle_delete_player,
  '!change-name': change_character_name,
  '!add': add_character_manually,
  '!ash-cache': handle_character_cache,
  '!check-cache': handle_check_cache,
  '!send-message': send_message_to_channel,
  '!raw-character': get_raw_character_info,
  '!get-character-list': get_user_characters,
}


async def handle_admin_command(message):
  for command, handler in command_list.items():
    if message.content.startswith(command):
      await handler(message)
      return
