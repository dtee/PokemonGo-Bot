import unittest
import re

from datetime import datetime
from mock import MagicMock, patch
from pokemongo_bot.cell_workers.catch_rare_pokemon import CatchRarePokemon

NORMALIZED_LAT_LNG_DISTANCE_STEP = 6.3593e-6

class TestCatchRarePokemon(unittest.TestCase):
    def setUp(self):
        self.patcherSleep = patch('pokemongo_bot.step_walker.sleep')
        self.patcherRandomLat = patch('pokemongo_bot.step_walker.random_lat_long_delta', return_value=0)
        self.patcherSleep.start()
        self.patcherRandomLat.start()

        self.bot = MagicMock()
        self.bot.position = [37.793785, -122.4061541, 0]
        self.bot.api = MagicMock()
        self.config = MagicMock()
        self.bot.config.distance_unit = 'mi'
        self.bot.config.username = 'dtee'

        self.lat, self.lng, self.alt = 0, 0, 0

        def default_config(*args, **kwargs):
            if args[0] == 'clean_bot_file':
                return False
            if args[0] == 'bot_file':
                return 'data/rare_pokemons.json.example'
            return args[1]

        self.config.get = MagicMock(side_effect=default_config)

        # let us get back the position set by the StepWalker
        def api_set_position(lat, lng, alt):
            self.lat, self.lng, self.alt = lat, lng, alt
        self.bot.api.set_position = api_set_position

        def parse_loc(*args, **kwargs):
            location_name = args[0]
            if ',' in location_name:
                possible_coordinates = re.findall(
                        "[-]?\d{1,3}[.]\d{6,7}", location_name
                )
                if len(possible_coordinates) == 2:
                    return float(possible_coordinates[0]), float(possible_coordinates[1]), float("0.0")

        self.bot.get_pos_by_name = MagicMock(side_effect=parse_loc)
        self.catch_rare_pokemon = CatchRarePokemon(self.bot, self.config)
        self.mock_pokemons = self.catch_rare_pokemon.load_rare_list()
        self.catch_rare_pokemon.reset_saved_catches()

    def tearDown(self):
        self.patcherSleep.stop()
        self.patcherRandomLat.stop()

    @patch('pokemongo_bot.cell_workers.catch_rare_pokemon.action_delay')
    @patch('pokemongo_bot.cell_workers.catch_rare_pokemon.datetime')
    def test_work(self, action_delay, mock_datetime):
        action_delay.return_value = 1
        mock_datetime.now.return_value = datetime(year=2016, month=8, day=02, hour=1, minute=2)
        self.catch_rare_pokemon.work()
        self.assertEqual(len(self.catch_rare_pokemon.load_saved_catches().keys()), 1)

        mock_datetime.now.return_value = datetime(year=2016, month=8, day=02, hour=1, minute=12)
        self.catch_rare_pokemon.work()
        self.assertEqual(len(self.catch_rare_pokemon.load_saved_catches().keys()), 2)

        mock_datetime.now.return_value = datetime(year=2016, month=8, day=02, hour=1, minute=12)
        self.catch_rare_pokemon.work()
        self.assertEqual(len(self.catch_rare_pokemon.load_saved_catches().keys()), 2)
'''
    @patch('pokemongo_bot.cell_workers.catch_rare_pokemon.action_delay')
    @patch('pokemongo_bot.cell_workers.catch_rare_pokemon.datetime')
    def test_catchable(self, mock_datetime, action_delay):
        action_delay.return_value = 1
        mock_datetime.now.return_value = datetime(year=2016, month=8, day=02, hour=1, minute=2)
        data = self.catch_rare_pokemon.get_reachable_pokemon()
        self.assertIsNotNone(data)
        self.assertEqual(data['dist'], 9115.696871798786)
        self.assertEqual(data['rare_pokemon']['name'], self.mock_pokemons[0]['name'])

    @patch('pokemongo_bot.cell_workers.catch_rare_pokemon.action_delay')
    @patch('pokemongo_bot.cell_workers.catch_rare_pokemon.datetime')
    def test_too_late_for_first(self, mock_datetime, action_delay):
        action_delay.return_value = 1
        mock_datetime.now.return_value = datetime(year=2016, month=8, day=02, hour=1, minute=12)
        data = self.catch_rare_pokemon.get_reachable_pokemon()
        self.assertIsNotNone(data)
        self.assertEqual(data['dist'], 3947.926329796451)
        self.assertEqual(data['rare_pokemon']['name'], self.mock_pokemons[1]['name'])

    @patch('pokemongo_bot.cell_workers.catch_rare_pokemon.action_delay')
    @patch('pokemongo_bot.cell_workers.catch_rare_pokemon.datetime')
    def test_unreachable(self, mock_datetime, action_delay):
        action_delay.return_value = 1
        mock_datetime.now.return_value = datetime(year=2016, month=8, day=02, hour=1, minute=24)
        self.assertIsNone(self.catch_rare_pokemon.get_reachable_pokemon())

'''