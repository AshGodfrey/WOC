import helpers
import discord
from replit import db
from datetime import datetime, timedelta
import json

def tag_player(posters):
  tags = []
  try:
      for character in posters:
          print(f"Checking character: '{character}'")  # Debugging output

          # Ensure "open" is detected correctly
          if "open" in character.lower().strip():  # Case-insensitive + removes spaces
              print("Detected 'open', adding '<@OPEN THREAD>'")  # Debugging output
              tags.append('<@&1345834632557629441>')
              continue  # Skip further processing

          if "pages" in character.lower():  # Case-insensitive check
              print("Detected 'pages', skipping")  # Debugging output
              continue  # Skip further processing

          # Attempt to look up character in db
          character_data = db.get(character.lower())  # Use .get() to avoid KeyError
          if character_data:
              player = character_data.get("player")
              if player:
                  tags.append(f'<@{player}>')
              else:
                  print(f"No player found for {character}")  # Debugging output
                  return "Other player not found, please tag them the old-fashioned way."
          else:
              print(f"{character} not found in db.")  # Debugging output
              return "Other player not found, please tag them the old-fashioned way."

      return ', '.join(tags) if tags else "No valid players found."
  except Exception as e:
      return f"Error: {e}"


def create_tag_embed(data):
  embed = discord.Embed(title=data['title'], url=data['link'], colour=0x8499B1)
  embed.set_thumbnail(url=data['img_url'])
  embed.add_field(name="Posted By", value=data['poster'].title(), inline=False)
  embed.add_field(name="Posted For",
                  value=', '.join(data['posted_for']).title(),
                  inline=False)
  return embed

def create_special_embed(data):
  embed = discord.Embed(title=data['title'], url=data['link'], colour=0x8499B1)
  embed.set_thumbnail(url=data['img_url'])
  embed.add_field(name="Posted By", value=data['poster'].title(), inline=False)
  embed.add_field(name="Looking For", value=data['looking_for'].title(), inline=False)
  return embed

def get_thread_id(url):
  array = url.split("=")
  smaller = array[2].split('&')
  return smaller[0]


def parse_timestamp(timestamp_str):
  time_str = timestamp_str.split("at ")[1]
  return datetime.strptime(time_str, "%I:%M %p")


def check_time(timestamp):
  post_timestamp = timestamp
  current_time = datetime.now()
  post_time = parse_timestamp(post_timestamp)

  # Get the minutes from the datetime objects
  current_minutes = current_time.minute
  post_minutes = post_time.minute

  # Compare the minutes
  if current_minutes - post_minutes > 1:
    #perform additional checks?
    return False
  else:
    return True


async def handle_tags(client, channel):
  do_nothing = False
  reasons = ""

  # Get most recent post
  soup = helpers.soup("https://windsofchangerp.jcink.net/index.php?act=Search&CODE=getactive")
  posts = soup.find("div", {"id": "active-topics"})
  last_topic = (posts.find_all('tr'))[1]
  last_poster_wrapper = (last_topic.find_all("td", {"class": "row2"}))[-1]
  replies = int(last_topic.find_all("td", {"class": "row4"})[-1].text)
  last_poster = last_poster_wrapper.find('b').text.lower()
  thread = (last_topic).find_all('td')[4]
  image = ""
  posted_for = ""
  tag = ""
  embed = ""
  forum = last_topic.find_all("td", {"class": "row4"})[-2].text.lower()

  posted_at = last_poster_wrapper.find(text=True, recursive=False).strip()

  # Check if in not-applicable forums
  forum = last_topic.find_all("td", {"class": "row4"})[-2].text.lower().strip()
  if forum == "a-m members" or forum == "n-z members":
    do_nothing = True
    reasons = reasons + "Not a posting forum. Forum: " + forum

  # Check if posted today then check if posted in past minute
  if posted_at.startswith("Today"):
    do_nothing = check_time(posted_at)
    reasons = reasons + "Out of acceptable time range. "
  elif posted_at.startswith("Yesterday"):
    do_nothing = True
    reasons = reasons + "Out of acceptable time range. "

  # Check if posted by a character
  db_character = db[last_poster]
  if not db_character:
    do_nothing = True
    reasons = reasons + "Poster not a character: " + last_poster + "."

  # Check if cached as last
  try:
    cached_post = helpers.check_cache('post:' + thread.text.title() + last_poster + str(replies))
    if cached_post:
      do_nothing = True
      reasons = reasons + "This post was cached. "
  except:
    await helpers.send_message(client, 1125111458020196443,
                               "Error accessing Redis key: " + ('post:' + thread.text.title() + last_poster + str(replies)))

  if do_nothing:
    await helpers.send_message(client, 1125111458020196443,
                               "Doing nothing with this post, reasons: " + reasons)
    return 

  # Mapping of forum types to channel IDs
  forum_to_channel = {
      "character creation": 1261083626351759451,
      "lovers": 1261083616822427648,
      "group": 1261083645733638166,
      "familial": 1261083603476021430,
      "sub-plots": 1261083660740726866,
      "enemies": 1261083626351759451,
      "friends": 1261083637315538964
  }

  forum = last_topic.find_all("td", {"class": "row4"})[-2].text.lower()
  if forum in forum_to_channel:
      character_data = helpers.check_cache('character:' + last_poster)

      # Cache miss: fetch character data and cache it
      if not character_data: 
          db_character = db[last_poster]
          soup = helpers.soup(db_character['profile'])
          cache_key = 'character:' + last_poster
          player = await client.fetch_user(db_character['player'])
          
          # Use centralized parsing function
          parsed_data = helpers.parse_character_from_soup(soup)
          data = {
              **parsed_data,
              'player_name': player.name,
              'player_avatar': str(player.avatar.url),
              'player_id': player.id,
              'profile_url': db_character['profile'],
          }
          helpers.write_to_cache(cache_key, data)
          character_data = data

      if character_data: 
          converted_data = helpers.convert_to_strings(character_data)
          image = converted_data['img_url']

      # Get description from <span class="desc">
      raw_desc = ""
      for desc in (last_topic).findAll('span', {'class': 'desc'}):
        raw_desc = desc.text.lower()

      data = {
          'title': thread.text.title(),
          'img_url': image,
          'poster': last_poster,
          'looking_for': raw_desc,
          'link': thread.find('a')['href'],
      }

      # New topics: update DB and write to cache before sending embed
      if replies == 0:
          cache_key = 'post:' + thread.text.title() + last_poster + str(replies)
          helpers.write_to_cache_expires(cache_key, "", 86400)

          try:
              record = db[last_poster]
              record["last_post"] = {
                  "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                  "link": thread.find('a')['href']
              }
              db[last_poster] = record
          except Exception as e:
              print("Error updating last_post:", e)

          embed = create_special_embed(data)
          channel = forum_to_channel[forum]
          await helpers.send_embed(client, channel, embed)
          return

  else:
    # Process normal tag embed branch
    character_data = helpers.check_cache('character:' + last_poster)
    if not character_data: 
      db_character = db[last_poster]
      soup = helpers.soup(db_character['profile'])
      cache_key = 'character:' + last_poster
      player = await client.fetch_user(db_character['player'])
      
      # Use centralized parsing function
      parsed_data = helpers.parse_character_from_soup(soup)
      data = {
          **parsed_data,
          'player_name': player.name,
          'player_avatar': str(player.avatar.url),
          'player_id': player.id,
          'profile_url': db_character['profile'],
      }
      helpers.write_to_cache(cache_key, data)
      character_data = data

    if character_data: 
      converted_data = helpers.convert_to_strings(character_data)
    image = converted_data['img_url']

    # Get description text
    for desc in (last_topic).findAll('span', {'class': 'desc'}):
      raw_desc = desc.text.lower()
    posted_for = raw_desc.split(", ")
    topic_starter = ((last_topic).find_all('td')[-4].find('a').text).lower()
    posted_for.append(topic_starter)

    # Remove the current poster from the list, if present
    try:
      posted_for.remove(last_poster)
    except Exception as e:
      print("Error removing last_poster from posted_for:", e)

    if replies == 0:
      tag = tag_player(posted_for)
    else:
      # If reply and last poster isn't the topic starter, tag appropriately
      if last_poster != topic_starter:
        tag = tag_player(posted_for)
      else:
        tag = tag_player(posted_for)

    data = {
      'title': thread.text.title(),
      'img_url': image,
      'poster': last_poster,
      'posted_for': posted_for,
      'link': thread.find('a')['href'],
    }

    # Update the player's record with last_post details and write to cache
    try:
      record = db[last_poster]
      record["last_post_date"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
      record["last_post_link"] = thread.find('a')['href']
      db[last_poster] = record
    except Exception as e:
        print("Error updating last_post:", e)

    cache_key = 'post:' + thread.text.title() + last_poster + str(replies)
    helpers.write_to_cache_expires(cache_key, "", 86400)

    await helpers.send_message(client, channel, tag)
    embed = create_tag_embed(data)
    await helpers.send_embed(client, channel, embed)
