import concurrent.futures
import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from pathlib import Path
from main import Store, handler

class CineCloudTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=str(Path(self.tmp.name)/'test.db')
        self.store=Store(self.path)
    def tearDown(self): self.tmp.cleanup()
    def test_catalog_and_capacity(self):
        self.assertEqual(len(self.store.shows()),2)
        self.assertEqual(len(self.store.seats(1)),50)
    def test_reservation_persists(self):
        self.store.reserve({'show_id':1,'seat':'A1'})
        self.assertFalse(Store(self.path).seats(1)[0]['available'])
    def test_duplicate_rejected(self):
        self.store.reserve({'show_id':1,'seat':'A1'})
        with self.assertRaises(FileExistsError): self.store.reserve({'show_id':1,'seat':'A1'})
    def test_different_shows(self):
        for sid in (1,2): self.store.reserve({'show_id':sid,'seat':'A1'})
    def test_validation(self):
        for data in ({},[],{'show_id':True,'seat':'A1'},{'show_id':1,'seat':'Z5'},{'show_id':1,'seat':"A1';DROP TABLE shows;"}):
            with self.subTest(data=data), self.assertRaises(ValueError): self.store.reserve(data)
    def test_unknown_show(self):
        with self.assertRaises(LookupError): self.store.reserve({'show_id':99,'seat':'A1'})
    def test_concurrent_same_seat(self):
        def reserve(_):
            try: self.store.reserve({'show_id':1,'seat':'B2'});return 'ok'
            except FileExistsError: return 'conflict'
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results=list(pool.map(reserve,range(8)))
        self.assertEqual(results.count('ok'),1)
        self.assertEqual(results.count('conflict'),7)
    def test_http_contract(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),handler(self.store))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        def request(path,body=None,ctype='application/json'):
            req=urllib.request.Request(base+path,data=body,headers={'Content-Type':ctype})
            try:
                with urllib.request.urlopen(req,timeout=5) as r: return r.status,r.read()
            except urllib.error.HTTPError as e: return e.code,e.read()
        try:
            self.assertEqual(request('/health')[0],200)
            self.assertIn(b'CineCloud',request('/')[1])
            self.assertEqual(request('/shows/1/seats')[0],200)
            body=json.dumps({'show_id':1,'seat':'C3'}).encode()
            self.assertEqual(request('/reservations',body)[0],201)
            self.assertEqual(request('/reservations',body)[0],409)
            self.assertEqual(request('/reservations',b'{')[0],400)
            self.assertEqual(request('/reservations',b'{}','text/plain')[0],415)
            self.assertEqual(request('/reservations',b'x'*4097)[0],413)
            self.assertEqual(request('/missing')[0],404)
        finally: server.shutdown();server.server_close();thread.join()

if __name__=='__main__': unittest.main()
