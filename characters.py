import discord
import json
from replit import db


def character_embed(cache_key: str, data: dict) -> discord.Embed:
    """
    Create a rich Embed for a character, using safe lookups for hooks.
    """
    try:
        rgb_str = db['color'].get(data.get('character_class', ''), '0,0,0')
        r, g, b = map(int, rgb_str.split(','))
    except Exception:
        r = g = b = 0

    display_name = data.get('character_name') or cache_key.title()
    moniker = data.get('moniker', '')
    station = data.get('station', '')
    title_line = f"{station} {display_name}" + (f", {moniker}" if moniker else "")

    embed = discord.Embed(
        title=title_line.strip(', '),
        url=data.get('profile_url'),
        colour=discord.Color.from_rgb(r, g, b)
    )

    # Set images
    if data.get('img_url'):
        embed.set_thumbnail(url=data['img_url'])
    if data.get('gif_url'):
        embed.set_image(url=data['gif_url'])

    embed.set_author(
        name=data.get('player_name', 'Unknown'),
        icon_url=data.get('player_avatar', '')
    )

    # Core stats
    embed.add_field(name='Age', value=data.get('age', 'N/A'), inline=True)
    embed.add_field(name='Region', value=data.get('region', 'N/A'), inline=True)

    # Hooks
    try:
        hooks = json.loads(data.get('hooks', '[]'))
    except json.JSONDecodeError:
        hooks = []

    for raw in hooks:
        subtitle = None
        text = None
        try:
            from bs4 import BeautifulSoup
            snippet = BeautifulSoup(raw, 'html.parser')
            subtitle = snippet.find('subtitle').get_text(strip=True) if snippet.find('subtitle') else None
            block = snippet.find('div', class_='blockquote3')
            text = block.get_text(strip=True) if block else None
        except Exception:
            pass

        if not subtitle or not text:
            continue
        if len(text) > 900:
            text = 'Please view in profile.'
        embed.add_field(name=subtitle, value=text, inline=False)

    return embed


def mini_embed(cache_key: str, data: dict) -> discord.Embed:
    """
    Create a compact Embed for menu displays.
    """
    try:
        rgb_str = db['color'].get(data.get('character_class', ''), '0,0,0')
        r, g, b = map(int, rgb_str.split(','))
    except Exception:
        r = g = b = 0

    display_name = data.get('character_name') or cache_key.title()
    moniker = data.get('moniker', '')
    title_line = display_name + (f", {moniker}" if moniker else "")

    embed = discord.Embed(
        title=title_line,
        url=data.get('profile_url'),
        colour=discord.Color.from_rgb(r, g, b)
    )

    if data.get('img_url'):
        embed.set_thumbnail(url=data['img_url'])

    embed.add_field(name='Age', value=data.get('age', 'N/A'), inline=True)
    embed.add_field(name='Region', value=data.get('region', 'N/A'), inline=True)

    return embed
