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
  1071575781458854049]

#not in use yet
async def handle_character_data(character, message):
  character_data = helpers.check_cache('character:' + character)
  if character_data:
    converted_data = helpers.convert_to_strings(character_data)
    embed = characters.character_embed(character, converted_data)
  await helpers.send_embed(client, message.channel.id, embed)
  
@client.event
async def on_ready():
  print(f'{client.user} has connected to Discord!')
   
@client.event
async def on_message(message):
  if message.author == client.user:
      return
    
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
      character = soup.find("profileheader").text.strip().lower()
      
      #add character to the database
      characters.update_character(character, str(messages[1].author.id), messages[1].content.strip())

      #add character to cache
      # Key for the Hashmap
      cache_key = 'character:' + character
      # Dictionary of key-value pairs to set in the Hashmap
      data = {
          'img_url': (soup.find("top").find("img"))['src'],
          'region': (soup.find("pfield", {"id": "region"})).find('c').text,
          'character_class': soup.find("mainprofile")['class'][0],
          'moniker': (soup.find("pfield", {"id": "moniker"})).find('c').text,
          'station': (soup.find("pfield", {"id": "station"})).find('c').text,
          'age': (soup.find("pfield", {"id": "age"})).find('c').text,
          'hooks': json.dumps([str(hook) for hook in soup.find_all("hook")]),
          'player_name': messages[1].author.name,
          'player_avatar': messages[1].author.avatar.url,
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


# Gets a character's info + sends embed to channel
  if message.content.startswith('!character'):
    character = characters.get_character_name(message.content)
    if character == "the many-faced god":
      await message.channel.send("The Many-Faced God is an NPC account.")
    else:
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
          data = {
              'img_url': (soup.find("top").find("img"))['src'],
              'region': (soup.find("pfield", {"id": "region"})).find('c').text,
              'character_class': soup.find("mainprofile")['class'][0],
              'moniker': (soup.find("pfield", {"id": "moniker"})).find('c').text,
              'station': (soup.find("pfield", {"id": "station"})).find('c').text,
              'age': (soup.find("pfield", {"id": "age"})).find('c').text,
              'hooks': json.dumps([str(hook) for hook in soup.find_all("hook")]),
              'player_name': messages[1].author.name,
              'player_avatar': messages[1].author.avatar.url,
              'player_id': messages[1].author.id,
              'profile_url': messages[1].content.strip(),
          }
          helpers.write_to_cache(cache_key, data)
          embed = characters.character_embed(character, data)
          await helpers.send_embed(client, plot_hooks_channel, embed)
       


#start admin commands
  if message.author.id in AUTHORIZED_USER_IDS:
    await admin_commands.handle_admin_command(message)
    
client.run(token)