# helpers.py
from replit import db
import json
from bs4 import BeautifulSoup
import requests
import os
import redis
import discord
from discord.ext import commands
import asyncio

# Redis client initialization
redis_url = os.getenv('REDIS_URL')
redis_client = redis.Redis.from_url(redis_url)

# Discord bot client instance (import main to avoid circular reference if needed)
client: commands.Bot  # type hint; actual client is created in main.py


def send_message(client_obj: commands.Bot, channel: int, message: str):
    return client_obj.get_channel(channel).send(message)


def send_embed(client_obj: commands.Bot, channel: int, embed: discord.Embed):
    return client_obj.get_channel(channel).send(embed=embed)


def tag_to_id(tag: str) -> str:
    return tag[2:-1]


def convert_to_strings(character_data: dict) -> dict:
    converted = {}
    for key, value in character_data.items():
        k = key.decode() if isinstance(key, bytes) else key
        v = value.decode() if isinstance(value, bytes) else value
        converted[k] = v
    return converted


def soup(url: str) -> BeautifulSoup:
    """Fetch HTML from URL and return BeautifulSoup object."""
    resp = requests.get(url)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, 'html.parser')


def check_cache(key: str):
    """Return cached hash or string, or False if missing."""
    if redis_client.exists(key):
        try:
            return redis_client.hgetall(key)
        except Exception:
            return redis_client.get(key)
    return False


def write_to_cache(key: str, value: dict):
    """Store a dict into Redis hash."""
    redis_client.hset(key, mapping=value)


def write_to_cache_expires(key: str, value: dict, expires: int):
    """Store a value with expiration (in seconds)."""
    redis_client.set(key, json.dumps(value), ex=expires)


def delete_cache(key: str):
    """Remove a cache entry."""
    redis_client.delete(key)


def get_character_name(content: str) -> str:
    """Extract character name from message content."""
    basecharacter = content.split(' ')
    character = str(' '.join(basecharacter[1:]).lower().strip())
    return character


def update_character(character: str, player_id: int, profile_html: str) -> str:
    """
    Add new character to Replit DB and prime cache.
    """
    # import inside to avoid circular dependency
    from main import build_character_data, client as bot_client

    if character in db:
        return (
            f"This character already exists. To replace, run `!admin-delete \"{character}\"` then try again."
        )

    # Save raw profile data
    db[character] = {
        'player': player_id,
        'profile': profile_html,
        'last_post_date': ''
    }

    # Prime cache with parsed data
    soup_obj = BeautifulSoup(profile_html, 'html.parser')
    try:
        author = bot_client.get_user(player_id) or asyncio.run(bot_client.fetch_user(player_id))
    except Exception:
        author = None
    data = build_character_data(soup_obj, author, profile_html)
    cache_key = f'character:{character}'
    write_to_cache(cache_key, data)

    return 'Character added and cache primed.'

