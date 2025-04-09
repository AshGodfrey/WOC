import asyncio
from replit import db

def find_characters_by_player(player_id):
    playerCharacters = db[player_id]
    return playerCharacters

async def cache_characters_by_player():
    loop = asyncio.get_running_loop()

    # Fetch keys from the database in a thread to prevent blocking
    keys = await loop.run_in_executor(None, db.keys)

    # Create a set of valid keys for faster checking
    valid_keys = set(keys)

    for key in keys:
        try:
            # Fetch each character info in a thread to prevent blocking
            character_info = await loop.run_in_executor(None, db.__getitem__, key)
            if 'player' in character_info:
                player_id = character_info['player']
                player_cache_key = player_id

                # Retrieve or initialize the player's character list
                current_characters = await loop.run_in_executor(None, db.get, player_cache_key, [])

                # Update the list if the key is not already present and is valid
                if key not in current_characters and key in valid_keys:
                    current_characters.append(key)

                # Remove invalid keys
                updated_characters = [char_key for char_key in current_characters if char_key in valid_keys]

                # Set the updated list back in the database
                await loop.run_in_executor(None, db.__setitem__, player_cache_key, updated_characters)

        except Exception as e:
            print(f"Error processing key {key}: {e}")
