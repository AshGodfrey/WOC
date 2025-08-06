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
  
  # Extract image URL - look for character images specifically
  try:
    data['img_url'] = ""
    
    # Method 1: Look for images with character-related classes or ids
    character_img = soup_obj.find("img", {"class": lambda x: x and any(term in str(x).lower() for term in ["character", "avatar", "profile", "portrait"])})
    if character_img and character_img.has_attr('src'):
      data['img_url'] = character_img['src']
    
    # Method 2: Look for images in divs with character-related classes
    if not data['img_url']:
      char_divs = soup_obj.find_all("div", {"class": lambda x: x and any(term in str(x).lower() for term in ["character", "avatar", "profile", "portrait"])})
      for div in char_divs:
        img = div.find("img")
        if img and img.has_attr('src'):
          data['img_url'] = img['src']
          break
    
    # Method 3: Look for larger images (profile images are usually bigger)
    if not data['img_url']:
      all_imgs = soup_obj.find_all("img")
      for img in all_imgs:
        if img.has_attr('src'):
          src = img['src']
          # Skip small icons/decorative images
          if any(skip_term in src.lower() for skip_term in ['icon', 'bullet', 'arrow', 'star', 'dot', 'line']):
            continue
          # Look for reasonable image file extensions
          if any(ext in src.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
            data['img_url'] = src
            break
    
    # Method 4: Fallback to first img tag if nothing else found
    if not data['img_url']:
      first_img = soup_obj.find("img")
      data['img_url'] = first_img['src'] if first_img and first_img.has_attr('src') else ""
    
    # Clean up URL if it's relative
    if data['img_url'] and data['img_url'].startswith('//'):
      data['img_url'] = 'https:' + data['img_url']
    elif data['img_url'] and data['img_url'].startswith('/'):
      data['img_url'] = 'https://windsofchangerp.jcink.net' + data['img_url']
      
    print(f"Found image URL: {data['img_url']}")
      
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
        # Special handling for age field - extract ONLY the number
        if field_id == 'age':
          import re
          numbers = re.findall(r'\b(\d+)\b', field_text)
          for num in numbers:
            if num.isdigit() and 10 <= int(num) <= 150:  # reasonable age range
              data[field_key] = num
              break
        else:
          # Remove the field label from the text
          clean_text = field_text.replace(field_id, '').strip()
          # Limit field text length to avoid CSS pollution
          if len(clean_text) < 100 and clean_text:
            data[field_key] = clean_text
        if data[field_key]:
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
        # Find all numbers in the text content and pick the first reasonable age
        numbers = re.findall(r'\b(\d+)\b', text_content)
        for num in numbers:
          if num.isdigit() and 10 <= int(num) <= 150:  # reasonable age range
            data[field_key] = num
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

