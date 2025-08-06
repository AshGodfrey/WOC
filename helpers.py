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
  
  # Remove style and script tags to avoid CSS pollution
  for tag in soup_obj(['style', 'script']):
    tag.decompose()
  
  # Extract image URL - look for avatar/profile images specifically
  try:
    # Look for profile/avatar images first
    avatar_img = soup_obj.find("img", {"class": lambda x: x and ("avatar" in str(x).lower() or "profile" in str(x).lower())})
    if not avatar_img:
      # Fallback to any img tag
      avatar_img = soup_obj.find("img")
    
    data['img_url'] = avatar_img['src'] if avatar_img and avatar_img.has_attr('src') else ""
    
    # Clean up URL if it's relative
    if data['img_url'] and data['img_url'].startswith('//'):
      data['img_url'] = 'https:' + data['img_url']
    elif data['img_url'] and data['img_url'].startswith('/'):
      data['img_url'] = 'https://windsofchangerp.jcink.net' + data['img_url']
      
  except Exception as e:
    print(f"Error extracting image URL: {e}")
    data['img_url'] = ""
  
  # Extract character class - look for meaningful class names, avoid CSS classes
  try:
    data['character_class'] = ""
    # Look for elements with meaningful class names (not CSS-related)
    profile_elements = soup_obj.find_all(class_=True)
    for elem in profile_elements:
      classes = elem.get('class', [])
      if isinstance(classes, list):
        for cls in classes:
          # Skip CSS-related classes
          if not any(css_term in cls.lower() for css_term in ['color', 'background', 'font', 'margin', 'padding', 'border', 'width', 'height']):
            if len(cls) > 2 and len(cls) < 30:  # Reasonable length for a class name
              data['character_class'] = cls
              break
        if data['character_class']:
          break
  except Exception as e:
    print(f"Error extracting character class: {e}")
    data['character_class'] = ""
  
  # Try to extract profile fields more precisely
  field_mappings = {
    'region': 'region',
    'moniker': 'moniker', 
    'station': 'station',
    'age': 'age'
  }
  
  for field_id, field_key in field_mappings.items():
    try:
      data[field_key] = ""
      
      # Method 1: Look for elements with matching id
      field_by_id = soup_obj.find(id=field_id)
      if field_by_id:
        field_text = field_by_id.get_text(strip=True)
        # Remove the field label from the text
        clean_text = field_text.replace(field_id, '').strip()
        # Limit field text length to avoid CSS pollution
        if len(clean_text) < 100 and clean_text:
          data[field_key] = clean_text
          continue
      
      # Method 2: Look for field labels and extract following content
      import re
      # Search for field patterns in a more controlled way
      text_content = soup_obj.get_text(separator='\n')
      # Limit text content to avoid processing CSS
      if len(text_content) > 5000:
        # Only look in the first part of the content to avoid CSS
        text_content = text_content[:5000]
        
      # Special handling for age field to extract just the number
      if field_id == 'age':
        # Look for age patterns and extract just the number
        age_patterns = [
          r'years\s+of\s+age\s*(\d+)',   # "years of age 26"
          r'years\s+of\s+(\d+)',         # "years of 26"
          r'age\s*(\d+)',                # "age 26"
          r'(\d+)\s+years?\s+of\s+age',  # "26 years of age"
          r'(\d+)\s+years?',             # "26 years"
          r'(?:age|years).*?(\d+)',      # fallback: age/years followed by any chars then number
        ]
        
        for age_pattern in age_patterns:
          age_match = re.search(age_pattern, text_content, re.IGNORECASE)
          if age_match:
            age_value = age_match.group(1).strip()
            if age_value and age_value.isdigit() and 10 <= int(age_value) <= 150:  # reasonable age range
              data[field_key] = age_value
              break
      else:
        # More specific patterns to extract just the value after the label
        patterns = [
          rf'{field_id}\s*[:]\s*([^\n]+)',  # "field: value"
          rf'{field_id}\s+([^\n]+)',       # "field value" (space separated)
          rf'{field_id}([^\n\s][^\n]*)'    # "fieldvalue" (concatenated)
        ]
        
        for pattern in patterns:
          match = re.search(pattern, text_content, re.IGNORECASE)
          if match:
            field_value = match.group(1).strip()
            # Clean up common prefixes that might be left
            field_value = re.sub(rf'^{field_id}\s*[:]*\s*', '', field_value, flags=re.IGNORECASE).strip()
            # Only use if it's reasonable length and doesn't look like CSS
            if len(field_value) < 100 and field_value and not any(css_term in field_value.lower() for css_term in ['color:', 'background:', 'font-', 'margin:', 'padding:', 'border:', '{', '}', 'px', 'em', 'rem']):
              data[field_key] = field_value
              break
          
    except Exception as e:
      print(f"Error extracting {field_key}: {e}")
      data[field_key] = ""
  
  # Extract hooks - be more careful to avoid CSS content
  try:
    hooks = []
    
    # Look for actual <hook> tags first
    hook_tags = soup_obj.find_all("hook")
    if hook_tags:
      for hook in hook_tags:
        hook_str = str(hook)
        # Only include if it's reasonable size and doesn't contain CSS
        if len(hook_str) < 500 and not any(css_term in hook_str.lower() for css_term in ['color:', 'background:', 'font-', 'margin:', 'padding:', 'border:']):
          hooks.append(hook_str)
    
    # Limit total hooks to avoid huge embeds
    hooks = hooks[:6]  # Max 6 hooks
    data['hooks'] = json.dumps(hooks)
    
  except Exception as e:
    print(f"Error extracting hooks: {e}")
    data['hooks'] = json.dumps([])
  
  # Debug output with size limits
  print(f"=== CHARACTER PARSING DEBUG ===")
  print(f"Found {len(soup_obj.find_all())} total elements")
  print(f"Parsed data sizes: img_url={len(data.get('img_url', ''))}, hooks={len(data.get('hooks', ''))}")
  for key, value in data.items():
    if key != 'hooks':
      print(f"{key}: '{value[:50]}{'...' if len(str(value)) > 50 else ''}'")
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

