from replit import db
import discord
import store
import json
from bs4 import BeautifulSoup

def get_character_name(message_content):
    basecharacter = message_content.split(' ')
    character = str(' '.join(basecharacter[1:]).lower().strip())
    return character
  
def update_character(character, player, profile):
  if character in db:
      return 'This character already exists. If you would like to replace them please say `!admin-delete "' + character + '"`. Then try again.'
  else:
    db[character] = {'player': player, 'profile': profile}
    return 'character added'

def character_embed(cache_key, data):
  try: 
    rgb = db["color"][data['character_class']]
    rgbArray = rgb.split(",")
    r = int(rgbArray[0])
    g = int(rgbArray[1])
    b = int(rgbArray[2])
  except:  
    r = 0
    g = 0
    b = 0
  
  hooks = json.loads(data['hooks'])
  embed = discord.Embed(title=data['station'] + ' ' + cache_key.title() +', ' + data['moniker'], url=data['profile_url'],  colour=discord.Color.from_rgb(r, g, b))
  embed.set_thumbnail(url=data['img_url'])
  embed.set_author(name=data['player_name'], icon_url= data['player_avatar'])
  embed.add_field(name="Age", value=data['age'], inline=True)
  embed.add_field(name="Region", value=data['region'], inline=True)
  for hook in hooks:
    soup = BeautifulSoup(hook, features='html.parser')
    subtitle = soup.find('subtitle').text
    div = soup.find('div', class_='blockquote3').text
    if len(div) > 900: 
      embed.add_field(name=subtitle, value="Please view in my profile.", inline=False)
    else:
      embed.add_field(name=subtitle, value=div, inline=False)
  return embed

def mini_embed(cache_key, data):
  try: 
    rgb = db["color"][data['character_class']]
    rgbArray = rgb.split(",")
    r = int(rgbArray[0])
    g = int(rgbArray[1])
    b = int(rgbArray[2])
  except:  
    r = 0
    g = 0
    b = 0

  embed = discord.Embed(title=cache_key.title() +', ' + data['moniker'], url=data['profile_url'],  colour=discord.Color.from_rgb(r, g, b))
  embed.set_thumbnail(url=data['img_url'])
  embed.add_field(name="Age", value=data['age'], inline=True)
  embed.add_field(name="Region", value=data['region'], inline=True)
  return embed
