"""CineCloud: stub educativo. No usar como servidor de producción."""
import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class Store:
    def __init__(self, path):
        self.path = path
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS shows (
                  id INTEGER PRIMARY KEY, movie TEXT NOT NULL, starts TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS reservations (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  show_id INTEGER NOT NULL REFERENCES shows(id),
                  seat TEXT NOT NULL, UNIQUE(show_id,seat));
                INSERT OR IGNORE INTO shows VALUES
                  (1,'Viaje a las estrellas','2026-12-01T18:00:00-05:00'),
                  (2,'El misterio del faro','2026-12-01T20:30:00-05:00');
            """)
    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()
    def shows(self):
        with self.connect() as db:
            return [dict(id=r[0],movie=r[1],starts=r[2]) for r in db.execute('SELECT * FROM shows ORDER BY id')]
    def seats(self, show_id):
        with self.connect() as db:
            if not db.execute('SELECT 1 FROM shows WHERE id=?',(show_id,)).fetchone():
                raise LookupError('Función no encontrada')
            taken={r[0] for r in db.execute('SELECT seat FROM reservations WHERE show_id=?',(show_id,))}
        return [dict(seat=f'{row}{col}',available=f'{row}{col}' not in taken) for row in 'ABCDE' for col in range(1,11)]
    def reserve(self, data):
        if not isinstance(data,dict) or set(data) != {'show_id','seat'}:
            raise ValueError('Se requieren únicamente show_id y seat')
        sid,seat=data['show_id'],data['seat']
        if type(sid) is not int or not isinstance(seat,str):
            raise ValueError('Tipos inválidos')
        if seat not in {f'{r}{c}' for r in 'ABCDE' for c in range(1,11)}:
            raise ValueError('Asiento inválido')
        with self.connect() as db:
            if not db.execute('SELECT 1 FROM shows WHERE id=?',(sid,)).fetchone():
                raise LookupError('Función no encontrada')
            try:
                cur=db.execute('INSERT INTO reservations(show_id,seat) VALUES (?,?)',(sid,seat))
                return dict(id=cur.lastrowid,show_id=sid,seat=seat,status='confirmed')
            except sqlite3.IntegrityError:
                raise FileExistsError('Asiento ya reservado') from None

def handler(store):
    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, data, content_type='application/json; charset=utf-8'):
            body=json.dumps(data,ensure_ascii=False).encode() if not isinstance(data,bytes) else data
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('X-Content-Type-Options','nosniff')
            self.end_headers();self.wfile.write(body)
        def do_GET(self):
            route=self.path.split('?',1)[0]
            if route=='/':
                return self.reply(200,Path(__file__).with_name('index.html').read_bytes(),'text/html; charset=utf-8')
            if route=='/health':
                with store.connect() as db: db.execute('SELECT 1')
                return self.reply(200,{'status':'ok','service':'CineCloud API'})
            if route=='/shows': return self.reply(200,store.shows())
            parts=route.strip('/').split('/')
            if len(parts)==3 and parts[0]=='shows' and parts[2]=='seats':
                try: return self.reply(200,store.seats(int(parts[1])))
                except ValueError: return self.reply(400,{'error':'Identificador inválido'})
                except LookupError as e: return self.reply(404,{'error':str(e)})
            self.reply(404,{'error':'Ruta no encontrada'})
        def do_POST(self):
            if self.path!='/reservations': return self.reply(404,{'error':'Ruta no encontrada'})
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':
                return self.reply(415,{'error':'Use application/json'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 4096: return self.reply(413,{'error':'Tamaño inválido'})
                data=json.loads(self.rfile.read(length))
                self.reply(201,store.reserve(data))
            except (ValueError,UnicodeDecodeError) as e: self.reply(400,{'error':str(e)})
            except LookupError as e: self.reply(404,{'error':str(e)})
            except FileExistsError as e: self.reply(409,{'error':str(e)})
    return Handler

if __name__=='__main__':
    db_path=os.environ.get('DB_PATH','cinecloud.db')
    Path(db_path).parent.mkdir(parents=True,exist_ok=True)
    server=ThreadingHTTPServer(('0.0.0.0',int(os.environ.get('PORT','8080'))),handler(Store(db_path)))
    print('CineCloud API en puerto '+str(server.server_port),flush=True)
    server.serve_forever()
