import discord
from replit import db

#initial seed colors, this command should be updated to allow an admin to pass in colors in bulk.
def set_all_colors():
  db["color"] = {
    'group-3':  '144, 147, 151', 'group-6': '205, 201, 189', 'group-7': '144, 147, 151', 'group-8': '64, 99, 197', 'group-9': '0, 147, 21', 'group-10': '162, 47, 39', 'group-11': '171, 134, 186', 'group-12': '108, 161, 90', 'group-13': '235, 191, 80', 'group-14': '239, 122, 59', 'group-15': '165, 133, 177', 'group-16': '92, 158, 216'
}

def set_something(key, values):
  db[key] = values 
  return db[key]
  
def set_color(group, value): 
  obj = db["color"]
  obj[group] = value
  return group, value

def set_region(value):
  db["region"] = value
  return db["region"]
  
def get_color_for_group(group):
  return db["color"]["group-3"]