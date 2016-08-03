import json
import dateutil.parser
import os.path

from datetime import datetime
from pokemongo_bot import logger
from pokemongo_bot.worker_result import WorkerResult
from pokemongo_bot.cell_workers.base_task import BaseTask
from pokemongo_bot.cell_workers.catch_visible_pokemon import CatchVisiblePokemon
from utils import distance, format_dist, format_time
from pokemongo_bot.human_behaviour import action_delay

class CatchRarePokemon(BaseTask):

    def initialize(self):
        self.max_distance = self.config.get("max_distance", 1000)
        self.max_speed = self.config.get("max_speed", 104)
        self.bot_file = self.config.get('bot_file', 'data/rare_pokemons.json')

    def load_rare_list(self):
        if not os.path.isfile(self.bot_file):
            logger.log('[x] Error loading pokemon locations')
            return []

        with open(self.bot_file) as f:
            rare_pokemons = json.load(f)

        return rare_pokemons

    def save_catch_file(self):
        return 'data/rare-%s.json' % (self.bot.config.username)

    def reset_saved_catches(self):
        user_snapshot = self.save_catch_file()
        with open(user_snapshot, 'w') as outfile:
            json.dump({}, outfile, indent = 2)

    def load_saved_catches(self):
        user_snapshot = self.save_catch_file()
        if not os.path.isfile(user_snapshot):
            return {}

        with open(user_snapshot) as f:
            rare_pokemons = json.load(f)

        return rare_pokemons

    # return true if we have tried to catch rare already
    def had_caught(self, rare_pokemon):
        hash = self.load_saved_catches()
        key = rare_pokemon['location'] + "-" + rare_pokemon['name']

        if key in hash.keys():
            expire_time = dateutil.parser.parse(hash[key])
            return expire_time > datetime.now()

    def update_saved_catches(self, rare_pokemon):
        rare_pokemons_hash = self.load_saved_catches()
        user_snapshot = self.save_catch_file()

        key = rare_pokemon['location'] + "-" + rare_pokemon['name']
        rare_pokemons_hash[key] = rare_pokemon['expire']
        with open(user_snapshot, 'w') as outfile:
            json.dump(rare_pokemons_hash, outfile)

    def get_reachable_pokemon(self):
        rare_pokemons = self.load_rare_list()
        for rare_pokemon in rare_pokemons:
            if (self.had_caught(rare_pokemon)):
                continue

            unit = self.bot.config.distance_unit  # Unit to use when printing formatted distance
            position = self.bot.get_pos_by_name(rare_pokemon['location'])

            lat = position[0]
            lng = position[1]
            pokemon_name = rare_pokemon['name']

            # dist in meters
            dist = distance(
                    self.bot.position[0],
                    self.bot.position[1],
                    lat,
                    lng
            )

            # Time left to get before pokemon disappears/de-spawn
            time_left = rare_pokemon['expire']
            expire_time = dateutil.parser.parse(time_left)
            seconds_left = (expire_time - datetime.now()).total_seconds()

            # Time it takes to get to pokemon in seconds
            time_to_dist_in_seconds = dist / self.max_speed / 1000 * 60 * 60
            seconds_left_to_catch = seconds_left - time_to_dist_in_seconds
            if seconds_left_to_catch > 20:
                formatted_dist = format_dist(dist, unit)
                formatted_time_to_dist = format_time(time_to_dist_in_seconds)
                logger.log('Can reach pokemon {}, {} in {}'.format(pokemon_name, formatted_dist, formatted_time_to_dist))

                return {
                    'rare_pokemon': rare_pokemon,
                    'lat': lat,
                    'lng': lng,
                    'dist': dist,
                    'seconds_left_to_catch': seconds_left_to_catch
                }
            else:
                logger.log('Too late to reach {}'.format(pokemon_name))

        return None

    def work(self):
        data = self.get_reachable_pokemon()
        if not (data is None):
            seconds_left_to_catch = data['seconds_left_to_catch']
            lat = data['lat']
            lng = data['lng']

            logger.log('we have more than {} to catch it'.format(format_time(seconds_left_to_catch)))
            logger.log('Sleeping...')

            # Improve??? log off and log back in?
            action_delay(seconds_left_to_catch, seconds_left_to_catch + 2)

            logger.log('Arrived at the pokemon. lets wait for a bit - could takes a while to spwan')
            self.bot.api.set_position(lat, lng, 0)
            self.bot.heartbeat()

            action_delay(5,10)
            catch_pokemon = CatchVisiblePokemon(
                self.bot,
                self.bot.config
            )

            catch_pokemon.work()

            logger.log('Saved data')
            self.update_saved_catches(data['rare_pokemon'])
        else:
            logger.log('No rare pokemons to catch')

        return WorkerResult.SUCCESS
