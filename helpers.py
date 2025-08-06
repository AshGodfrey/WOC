from replit import db
from bs4 import BeautifulSoup
import requests
import os
import redis
import discord
import json
from discord.ext import commands
intents = discord.Intents.all()
intents.members = True
client = commands.Bot(command_prefix='-', intents=intents)

redis_url = os.getenv('REDIS_URL')
redis_client = redis.Redis.from_url(redis_url)

async def send_message(client, channel, message):
  await client.get_channel(channel).send(message)

async def send_embed(client, channel, embed):
  await client.get_channel(channel).send(embed = embed)

def tag_to_id(id):
  return id[2:(len(id)-1)]
  
def convert_to_strings(character_data):
  converted_data = {}
  for key, value in character_data.items():
    converted_key = key.decode() if isinstance(key, bytes) else key
    converted_value = value.decode() if isinstance(value, bytes) else value
    converted_data[converted_key] = converted_value
  return converted_data
  
def soup(url):
  response = requests.get(url)
  return BeautifulSoup(response.text, "html.parser")

def parse_character_from_soup(soup_obj):
  """
  Centralized function to extract character data from soup object.
  Based on the HTML structure from the profile page.
  """
  data = {}
  
  # Extract image URL - try multiple approaches
  try:
    # First try to find img in top section
    top_section = soup_obj.find("top")
    if top_section:
      img = top_section.find("img")
      if img and img.has_attr('src'):
        data['img_url'] = img['src']
      else:
        data['img_url'] = ""
    else:
      # Fallback: try to find any img tag in the document
      img = soup_obj.find("img")
      data['img_url'] = img['src'] if img and img.has_attr('src') else ""
  except Exception as e:
    print(f"Error extracting image URL: {e}")
    data['img_url'] = ""
  
  # Extract character class from mainprofile
  try:
    profile = soup_obj.find("mainprofile")
    if profile and profile.has_attr('class'):
      class_val = profile['class']
      data['character_class'] = class_val[0] if isinstance(class_val, list) else str(class_val)
    else:
      data['character_class'] = ""
  except Exception as e:
    print(f"Error extracting character class: {e}")
    data['character_class'] = ""
  
  # Extract profile fields by ID with better error handling
  field_mappings = {
    'region': 'region',
    'moniker': 'moniker', 
    'station': 'station',
    'age': 'age'
  }
  
  for field_id, field_key in field_mappings.items():
    try:
      # Look for pfield with specific id
      field = soup_obj.find("pfield", {"id": field_id})
      if field:
        # Try to find c tag first
        c_tag = field.find("c")
        if c_tag and c_tag.get_text(strip=True):
          data[field_key] = c_tag.get_text(strip=True)
        else:
          # Fallback to direct text content of pfield
          text = field.get_text(strip=True)
          data[field_key] = text if text else ""
      else:
        # Alternative: look for any element with id matching field_id
        alt_field = soup_obj.find(id=field_id)
        if alt_field:
          data[field_key] = alt_field.get_text(strip=True)
        else:
          data[field_key] = ""
    except Exception as e:
      print(f"Error extracting {field_key} (id: {field_id}): {e}")
      data[field_key] = ""
  
  # Extract hooks
  try:
    hooks = soup_obj.find_all("hook")
    if hooks:
      data['hooks'] = json.dumps([str(hook) for hook in hooks])
    else:
      data['hooks'] = json.dumps([])
  except Exception as e:
    print(f"Error extracting hooks: {e}")
    data['hooks'] = json.dumps([])
  
  # Debug output to help troubleshoot
  print(f"=== CHARACTER PARSING DEBUG ===")
  print(f"Found {len(soup_obj.find_all())} total elements")
  print(f"Found {len(soup_obj.find_all('pfield'))} pfield elements")
  print(f"Found {len(soup_obj.find_all('img'))} img elements")
  print(f"Parsed data: {data}")
  print("==============================")
  
  return data

def check_cache(key):
# Check if the key exists in the cache
  if redis_client.exists(key):
    # Retrieve all values from the Hashmap
    try: 
      return redis_client.hgetall(key)
    except:
      return redis_client.get(key)
  else:
    # Cache miss
    return False

def write_to_cache(key, value):
   redis_client.hmset(key, value)

def write_to_cache_expires(key, value, expires):
   redis_client.set(key, value, ex=expires)

def delete_cache(key):
  redis_client.delete(key)

