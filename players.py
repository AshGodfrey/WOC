from replit import db
keys = db.keys()

def find_characters_by_player(player_id):
  playerCharacters = []
  for key in keys: 
    value = db[key]
    if player_id == value["player"]:
      playerCharacters.append(key)
  return playerCharacters