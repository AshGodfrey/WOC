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
  
  # Extract image URL - look for any img tag in the document
  try:
    img = soup_obj.find("img")
    data['img_url'] = img['src'] if img and img.has_attr('src') else ""
  except Exception as e:
    print(f"Error extracting image URL: {e}")
    data['img_url'] = ""
  
  # Extract character class from any element with class attribute
  try:
    # Look for elements that might have character class info
    profile_elements = soup_obj.find_all(class_=True)
    data['character_class'] = ""
    for elem in profile_elements:
      classes = elem.get('class', [])
      if isinstance(classes, list) and classes:
        # Take the first meaningful class
        data['character_class'] = classes[0]
        break
  except Exception as e:
    print(f"Error extracting character class: {e}")
    data['character_class'] = ""
  
  # Try to extract profile fields - be more flexible with the structure
  field_mappings = {
    'region': 'region',
    'moniker': 'moniker', 
    'station': 'station',
    'age': 'age'
  }
  
  for field_id, field_key in field_mappings.items():
    try:
      data[field_key] = ""
      
      # Method 1: Look for any element with matching id
      field_by_id = soup_obj.find(id=field_id)
      if field_by_id:
        data[field_key] = field_by_id.get_text(strip=True)
        continue
      
      # Method 2: Look for text that contains the field name (case insensitive)
      all_text_elements = soup_obj.find_all(text=True)
      for text in all_text_elements:
        text_str = str(text).strip().lower()
        if field_id.lower() in text_str:
          # Try to find the parent element and get following text
          parent = text.parent
          if parent:
            next_text = parent.get_text(strip=True)
            # Extract text after the field name
            if ':' in next_text:
              parts = next_text.split(':', 1)
              if len(parts) > 1:
                data[field_key] = parts[1].strip()
                break
      
      # Method 3: Look for common field patterns in the HTML
      if not data[field_key]:
        # Search for field patterns like "Age: 25" in the text
        page_text = soup_obj.get_text()
        import re
        pattern = rf'{field_id}\s*:?\s*([^\n\r]+)'
        match = re.search(pattern, page_text, re.IGNORECASE)
        if match:
          data[field_key] = match.group(1).strip()
          
    except Exception as e:
      print(f"Error extracting {field_key}: {e}")
      data[field_key] = ""
  
  # Extract hooks - look for any elements that might contain hook information
  try:
    hooks = []
    
    # Method 1: Look for actual <hook> tags
    hook_tags = soup_obj.find_all("hook")
    if hook_tags:
      hooks = [str(hook) for hook in hook_tags]
    else:
      # Method 2: Look for any elements that might be hooks based on content patterns
      # This is a fallback for when the structure is different
      all_elements = soup_obj.find_all()
      for elem in all_elements:
        elem_text = elem.get_text(strip=True).lower()
        # Look for hook-like patterns
        if any(word in elem_text for word in ['hook', 'child', 'defender', 'free', 'handmaid', 'missing', 'oblivious']):
          # Create a mock hook structure
          subtitle = elem.get_text(strip=True)
          if subtitle and len(subtitle) < 100:  # Reasonable length for a subtitle
            mock_hook = f'<hook><subtitle>{subtitle}</subtitle></hook>'
            hooks.append(mock_hook)
    
    data['hooks'] = json.dumps(hooks)
  except Exception as e:
    print(f"Error extracting hooks: {e}")
    data['hooks'] = json.dumps([])
  
  # Debug output to help troubleshoot
  print(f"=== CHARACTER PARSING DEBUG ===")
  print(f"Found {len(soup_obj.find_all())} total elements")
  print(f"Found {len(soup_obj.find_all('img'))} img elements")
  print(f"All element tags found: {set(tag.name for tag in soup_obj.find_all() if tag.name)}")
  print(f"Sample of page text: {soup_obj.get_text()[:200]}...")
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

