from datetime import datetime
from pathlib import Path
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import history_database as db
import history_manager as manager
import history_storage as storage
import game_analysis
import gerador_loterias as lottery


class ManagedHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        for replacement in (patch.dict(os.environ, {'DATABASE_URL': ''}),
                            patch.object(db, 'HISTORY_DB_PATH', str(Path(self.tmp.name)/'history.sqlite3')),
                            patch.object(lottery, 'OUTPUT_DIR', self.tmp.name)):
            replacement.start(); self.addCleanup(replacement.stop)
        self.filename = 'megasena_resultados_2026-11-24_12-00-00.csv'
        self.games = [[1,2,3,4,5,6], [1,2,3,4,7,8]]
        db.save_history_record(self.filename, 'megasena', self.games, owner_key='user:1')
        db.save_history_record(self.filename, 'megasena', [[10,11,12,13,14,15]], owner_key='user:2')
        self.draws = ((100, '24/11/2026', (1,2,3,4,5,6), None),)
        self.reader = patch.object(game_analysis, 'load_validated_history', return_value=(self.draws, 0, type('Stat', (), {'st_mtime_ns': 1})()))
        self.reader.start(); self.addCleanup(self.reader.stop)

    def update(self, index=0, **changes):
        return manager.update_game('megasena', 'user:1', {'filename': self.filename, 'index': index, **changes})

    def test_only_effective_games_are_ever_checked(self):
        with patch.object(manager, 'game_payload', side_effect=AssertionError('Must not check generated-only games')):
            result = manager.list_games('megasena', 'user:1', {})
        self.assertEqual(result['summary']['checked'], 0)
        self.assertTrue(all(item['check']['status'] == 'not_effective' for item in result['items']))
        self.update(effective=True, contest=100)
        result = manager.list_games('megasena', 'user:1', {})
        self.assertEqual(result['summary']['prizes'], 1)
        self.assertEqual(result['summary']['effective'], 1)
        self.update(effective=False, contest=None)
        self.assertEqual(manager.list_games('megasena', 'user:1', {})['summary']['checked'], 0)

    def test_favorites_filters_and_individual_delete_are_owner_scoped(self):
        self.update(favorite=True)
        self.assertEqual(manager.list_games('megasena', 'user:1', {'favorite':'1'})['matched'], 1)
        self.assertEqual(manager.list_games('megasena', 'user:2', {'favorite':'1'})['matched'], 0)
        self.assertEqual(manager.list_games('megasena', 'user:1', {'numbers':'7 8'})['matched'], 1)
        self.assertEqual(manager.list_games('megasena', 'user:1', {'from':'2026-11-25'})['matched'], 0)
        self.update(deleted=True)
        self.assertEqual(storage.read_history_file(self.filename, 'user:1'), [self.games[1]])
        self.assertEqual(storage.read_history_file(self.filename, 'user:2'), [[10,11,12,13,14,15]])
        self.assertFalse(self.update(favorite=False))
        self.assertEqual(manager.list_games('megasena', 'user:1', {})['matched'], 1)

    def test_actual_prize_tiers_and_month_are_adapted(self):
        for kind, hits in [('megasena',4), ('quina',2), ('lotofacil',11), ('diadesorte',4)]:
            config = lottery.LOTTERY_CONFIGS[kind]; count = config['NUM_BALLS_TO_DRAW']
            game = list(range(1,count+1))
            draw = tuple(list(range(1,hits+1))+list(range(count+1, count+1+count-hits)))
            if kind == 'diadesorte': game.append('Junho')
            result = manager.check_game(kind, game, {'effective':True,'contest':1}, {1:(1,'24/11/2026',draw,1)}, 1)
            self.assertEqual(result['status'], 'prize', kind)
            self.assertEqual(result['hits'], hits)
        month_only = manager.check_game('diadesorte', [1,2,3,4,5,6,7,'Junho'], {'effective':True,'contest':1}, {1:(1,'24/11/2026',(20,21,22,23,24,25,26),6)},1)
        self.assertEqual(month_only['hits'],0); self.assertTrue(month_only['month_hit']); self.assertEqual(month_only['status'],'prize')
        unknown_month = manager.check_game('diadesorte', [1,2,3,4,5,6,7,'Junho'], {'effective':True,'contest':1}, {1:(1,'24/11/2026',(20,21,22,23,24,25,26),None)},1)
        self.assertEqual(unknown_month['status'],'incomplete')

    def test_missing_results_never_mean_lost_and_changes_refresh(self):
        self.update(effective=True, contest=101)
        self.assertEqual(manager.list_games('megasena','user:1',{'effective':'yes'})['items'][0]['check']['status'],'waiting')
        with patch.object(game_analysis,'load_validated_history',return_value=(((101,'25/11/2026',(1,2,3,4,5,6),None),),0,type('Stat',(),{'st_mtime_ns':2})())):
            result = manager.list_games('megasena','user:1',{'effective':'yes'})
            self.assertEqual(result['items'][0]['check']['status'],'prize'); self.assertEqual(result['source']['version'],'2')
        self.update(effective=True, contest=99)
        self.assertEqual(manager.list_games('megasena','user:1',{'effective':'yes'})['items'][0]['check']['status'],'unavailable')

    def test_strict_validation_pagination_and_cascade(self):
        for changes in ({'effective':True}, {'effective':'yes'}, {'favorite':1}, {'contest':100}, {'deleted':False}):
            with self.assertRaises(ValueError): self.update(**changes)
        with self.assertRaises(ValueError): self.update(index=True, favorite=True)
        for filters in ({'numbers':'61'}, {'page':'-1'}, {'status':'win'}, {'from':'2026-12-01','to':'2026-11-01'}):
            with self.assertRaises(ValueError): manager.list_games('megasena','user:1',filters)
        self.update(favorite=True)
        storage.clear_history('megasena','user:1')
        self.assertEqual(db.game_settings(self.filename,'user:1'),{})
        self.assertEqual(len(db.read_history_file(self.filename,'user:2')),1)

    def test_routes_require_session_csrf_and_cannot_cross_owners(self):
        import app
        client = app.app.test_client()
        self.assertEqual(client.get('/history_games/megasena').status_code,401)
        with patch.object(app,'current_access_payload',return_value={'id':1,'is_guest':False}):
            self.assertEqual(client.post('/history_game/megasena',json={'filename':self.filename,'index':0,'favorite':True}).status_code,403)
            with client.session_transaction() as session: session['csrf_token']='test-token'
            headers={'X-CSRF-Token':'test-token'}
            self.assertEqual(client.post('/history_game/megasena',headers=headers,json={'filename':self.filename,'index':0,'favorite':True}).status_code,200)
            response=client.get('/history_games/megasena?favorite=1')
            self.assertEqual(response.json['matched'],1); self.assertIn('no-store',response.headers['Cache-Control'])
            self.assertEqual(client.post('/history_clear/megasena',headers=headers,json={'confirm':'quina'}).status_code,400)
        with patch.object(app,'current_access_payload',return_value={'id':3,'is_guest':False}):
            self.assertEqual(client.post('/history_game/megasena',headers=headers,json={'filename':self.filename,'index':0,'favorite':True}).status_code,404)
            self.assertEqual(client.get('/history_games/megasena').json['summary']['total'],0)


if __name__ == '__main__': unittest.main()
