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



# characters.py
import discord
import json
from bs4 import BeautifulSoup
from replit import db


def character_embed(cache_key: str, data: dict) -> discord.Embed:
    """
    Create a rich Embed for a character, using safe lookups for hooks.
    """
    # Determine color
    try:
        rgb = db['color'].get(data.get('character_class'), '0,0,0')
        r, g, b = (int(c) for c in rgb.split(','))
    except Exception:
        r = g = b = 0

    # Build title and embed
    title = f"{data.get('station', '')} {cache_key.title()}, {data.get('moniker', '')}".strip(', ')
    embed = discord.Embed(title=title,
                          url=data.get('profile_url'),
                          colour=discord.Color.from_rgb(r, g, b))
    if data.get('img_url'):
        embed.set_thumbnail(url=data['img_url'])
    embed.set_author(name=data.get('player_name', 'Unknown'),
                     icon_url=data.get('player_avatar'))

    # Core stats
    embed.add_field(name='Age', value=data.get('age', 'N/A'), inline=True)
    embed.add_field(name='Region', value=data.get('region', 'N/A'), inline=True)

    # Parse hooks safely
    raw_hooks = []
    try:
        raw_hooks = json.loads(data.get('hooks') or '[]')
    except json.JSONDecodeError:
        raw_hooks = []

    for raw in raw_hooks:
        soup = BeautifulSoup(raw, 'html.parser')
        subtitle_node = soup.find('subtitle')
        block_node = soup.find('div', class_='blockquote3')

        subtitle = subtitle_node.get_text(strip=True) if subtitle_node else None
        text = block_node.get_text(strip=True) if block_node else None

        # If the hook is just an empty placeholder, skip it
        if not subtitle or not text:
            continue

        # Truncate overly long content
        if len(text) > 900:
            text = 'Please view in my profile.'

        embed.add_field(name=subtitle, value=text, inline=False)

    return embed


def mini_embed(cache_key: str, data: dict) -> discord.Embed:
    """
    Create a compact Embed for menu displays.
    """
    # Determine color
    try:
        rgb = db['color'].get(data.get('character_class'), '0,0,0')
        r, g, b = (int(c) for c in rgb.split(','))
    except Exception:
        r = g = b = 0

    title = f"{cache_key.title()}, {data.get('moniker', '')}".strip(', ')
    embed = discord.Embed(title=title,
                          url=data.get('profile_url'),
                          colour=discord.Color.from_rgb(r, g, b))
    if data.get('img_url'):
        embed.set_thumbnail(url=data['img_url'])

    embed.add_field(name='Age', value=data.get('age', 'N/A'), inline=True)
    embed.add_field(name='Region', value=data.get('region', 'N/A'), inline=True)
    return embed
