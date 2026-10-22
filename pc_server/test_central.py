"""Run: python -m unittest test_central.py (from pc_server)."""
import os,sys,tempfile,types,unittest,importlib
sys.modules.setdefault('pyodbc',types.ModuleType('pyodbc'))
os.environ.setdefault('SSOIL_API_TOKEN','test-only-token')
os.environ.setdefault('SSOIL_ODBC_CONNECTION','test-only')
import server
class CentralTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();server.CENTRAL_DB=os.path.join(self.temp.name,'center.db');server.central_init()
    def tearDown(self):self.temp.cleanup()
    def test_changes_idempotent_and_deletion(self):
        x={'section':'labels','key':'123','value':{'name':'Pepsi'},'event_id':'device-event-123'}
        a=server.shared_write(x);self.assertEqual(a['revision'],1)
        self.assertTrue(server.shared_write(x)['duplicate'])
        self.assertEqual(len(server.shared_changes()['changes']),1)
        server.shared_write({'section':'labels','key':'123','value':None,'event_id':'device-event-456'})
        self.assertIsNone(server.shared_changes(1)['changes'][0]['value'])
    def test_reject_unknown_section(self):
        with self.assertRaises(ValueError):server.shared_write({'section':'pos','key':'1','value':{},'event_id':'device-event-999'})
    def test_sales_daily_deltas(self):
        server.sales=lambda:{'sales':{'12':10}}
        server.sales_poll_once();self.assertEqual(server.daily_sales()['daily'],{})
        server.sales=lambda:{'sales':{'12':13}}
        server.sales_poll_once();self.assertEqual(sum(x.get('12',0) for x in server.daily_sales()['daily'].values()),3)
        server.sales_poll_once();self.assertEqual(sum(x.get('12',0) for x in server.daily_sales()['daily'].values()),3)
if __name__=='__main__':unittest.main()
