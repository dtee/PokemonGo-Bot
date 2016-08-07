import json
import dateutil.parser
import os.path
import dateutil.parser

from datetime import datetime
from pokemongo_bot.worker_result import WorkerResult
from pokemongo_bot.cell_workers.base_task import BaseTask
from pokemongo_bot.cell_workers.catch_visible_pokemon import CatchVisiblePokemon
from utils import distance, format_dist, format_time
from pokemongo_bot.human_behaviour import action_delay

'''
Expects data/rare_pokemons.json to have the following format:
[
	{
	    "id": 139,
		"name": "Dragonite",
		"location": "37.713724, -122.4284539",
		"expire": "2016-08-02T01:12:57.807680"
	},
	{
		"name": "Electabuzz",
		"location": "37.759540, -122.4180126",
		"expire": "2016-08-02T01:18:57.807680"
	}
]
'''


class CatchRarePokemon(BaseTask):
    SUPPORTED_TASK_API_VERSION = 1

    def initialize(self):
        self.max_distance = self.config.get("max_distance", 1000)
        self.max_speed = self.config.get("max_speed", 104)
        self.bot_file = self.config.get('bot_file', 'data/rare_pokemons.json')
        self.should_clean = self.config.get('clean_bot_file', True)
        self.should_return_after = self.config.get('should_return_after', True)
        self.orig_position = None

        # Larpas > Snorlex > Dragonite > Exeggutor > Arcanine > Dratini
        self.catch_priority = [131,143,149,103,59,147]

    def load_rare_list(self):
        if not os.path.isfile(self.bot_file):
            self.emit_event('catch_rare_error',
                formatted='[x] Error loading pokemon locations')
            return []

        with open(self.bot_file) as f:
            rare_pokemons = json.load(f)

        return rare_pokemons

    def process_rare_pokemons(self, rare_pokemons):
        # Dedup - validate - and process
        hash = {}
        for rare_pokemon in rare_pokemons:
            rare_pokemon['expired_time_object'] = dateutil.parser.parse(rare_pokemon['expire'])
            if rare_pokemon['expired_time_object'] < datetime.now():
                continue

            position = self.bot.get_pos_by_name(rare_pokemon['location'])
            rare_pokemon['latitude'] = position[0]
            rare_pokemon['longitude'] = position[1]

            dist = distance(
                    self.bot.position[0],
                    self.bot.position[1],
                    rare_pokemon.get('latitude'),
                    rare_pokemon['longitude']
            )
            seconds_left = (rare_pokemon['expired_time_object'] - datetime.now()).total_seconds()

            # Time it takes to get to pokemon in seconds
            time_to_dist_in_seconds = dist / self.max_speed / 1000 * 60 * 60
            rare_pokemon['dist'] = dist
            rare_pokemon['time_to_dist_in_seconds'] = time_to_dist_in_seconds
            rare_pokemon['seconds_left_to_catch'] = seconds_left - time_to_dist_in_seconds

            # Calculate priority based on config
            rare_pokemon['priority'] = self.catch_priority.index(rare_pokemon['pokemon_id'])

            # Add only if it in catchable distance
            if rare_pokemon['seconds_left_to_catch'] > 20:
                key = rare_pokemon['location'] + "-" + rare_pokemon['name']
                hash[key] = rare_pokemon

        trimmed_rare_pokemons = []
        rare_pokemons = hash.values()
        for rare_pokemon in rare_pokemons:
            trimmed_rare_pokemons.append({
                'pokemon_id': rare_pokemon.get('pokemon_id', -1),
                'name': rare_pokemon['name'],
                'location': rare_pokemon['location'],
                'expire': rare_pokemon['expire']
            })

        # Update file with active pokemons
        if self.should_clean:
            with open(self.bot_file, 'w') as outfile:
                json.dump(trimmed_rare_pokemons, outfile)

        # sort by distance - to do catch S rank first
        rare_pokemons.sort(key=lambda x: (x['priority'], x['seconds_left_to_catch']))

        return rare_pokemons

    def save_catch_file(self):
        return 'data/rare-%s.json' % (self.bot.config.username)

    def reset_saved_catches(self):
        user_snapshot = self.save_catch_file()
        with open(user_snapshot, 'w') as outfile:
            json.dump({}, outfile, indent=2)

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
        rare_pokemons = self.process_rare_pokemons(rare_pokemons)

        for rare_pokemon in rare_pokemons:
            if (self.had_caught(rare_pokemon)):
                continue

            return rare_pokemon
        return None

    def work(self):
        rare_pokemon = self.get_reachable_pokemon()
        if not (rare_pokemon is None):
            seconds_left_to_catch = rare_pokemon['time_to_dist_in_seconds']
            unit = self.bot.config.distance_unit

            result = {
                'dist': format_dist(rare_pokemon['dist'], unit),
                'time': format_time(seconds_left_to_catch),
                'name': rare_pokemon['name'],
                'location': rare_pokemon['location']
            }

            self.emit_event(
                    'found_rare_pokemon',
                    formatted='Driving {dist} for {time} to catch {name} at {location}',
                    data=result
            )

            self.orig_position = self.bot.position

            # Improve??? log off and log back in?
            action_delay(seconds_left_to_catch, seconds_left_to_catch + 2)

            self.bot.api.set_position(rare_pokemon['latitude'], rare_pokemon['longitude'], 0)
            self.bot.heartbeat()

            # Update the cell - scan near by for pokemons
            self.bot.get_meta_cell()
            action_delay(self.bot.config.action_wait_min, self.bot.config.action_wait_max)

            catch_pokemon = CatchVisiblePokemon(
                    self.bot,
                    self.bot.config
            )

            catch_pokemon.work()
            self.update_saved_catches(rare_pokemon)

            # Lets go back to previous location
            if self.should_return_after and not (self.orig_position is None):
                msg = 'Driving back to {}... at {}/km per hours'.format(
                        "{}, {}".format(self.orig_position[0], self.orig_position[1]),
                        self.max_speed)

                self.emit_event('catch_rare_update',
                                formatted=msg)
                action_delay(seconds_left_to_catch, seconds_left_to_catch + 2)

                self.bot.api.set_position(
                        self.orig_position[0],
                        self.orig_position[0],
                        0)
                self.bot.heartbeat()

                # Update the cell - scan near by for pokemons
                self.bot.get_meta_cell()


        else:
            self.emit_event('catch_rare_update',
                            formatted='No rare pokemons to catch')

        return WorkerResult.SUCCESS
