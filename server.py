"""SS OIL local read-only API. No database writes."""
import os, json, hmac, logging, re, sqlite3, threading, time, uuid
from decimal import Decimal
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit, parse_qs, unquote
import pyodbc

HOST=os.getenv('SSOIL_HOST','0.0.0.0')
PORT=int(os.getenv('SSOIL_PORT','8766'))
TOKEN=os.environ['SSOIL_API_TOKEN']
ODBC=os.environ['SSOIL_ODBC_CONNECTION']
DATE_COL=os.getenv('SSOIL_SALES_DATE_COLUMN','').strip()
BROJ_COL=os.getenv('SSOIL_SALES_BROJ_COLUMN','Broj').strip()
FUEL_MAP=json.loads(os.getenv('SSOIL_FUEL_ART_IDS','{}'))
# Optional separate SQLite dopuna databases. Paths and field names are set in
# environment variables, so existing SQL Server and Android settings stay intact.
# SQLite connections are opened in immutable read-only mode.
DOPUNA_CONFIG={
    'mtel': {'path':os.getenv('SSOIL_MTEL_DB',r'\\192.168.100.50\Local2\Local.db3').strip(),
             'table':os.getenv('SSOIL_MTEL_TABLE','').strip(),
             'date':os.getenv('SSOIL_MTEL_DATE_COLUMN','').strip(),
             'amount':os.getenv('SSOIL_MTEL_AMOUNT_COLUMN','').strip(),
             'status':os.getenv('SSOIL_MTEL_STATUS_COLUMN','').strip(),
             'status_value':os.getenv('SSOIL_MTEL_STATUS_VALUE','').strip()},
    'aero': {'path':os.getenv('SSOIL_AERO_DB',r'\\192.168.100.50\Local\Local.db3').strip(),
             'table':os.getenv('SSOIL_AERO_TABLE','').strip(),
             'date':os.getenv('SSOIL_AERO_DATE_COLUMN','').strip(),
             'amount':os.getenv('SSOIL_AERO_AMOUNT_COLUMN','').strip(),
             'status':os.getenv('SSOIL_AERO_STATUS_COLUMN','').strip(),
             'status_value':os.getenv('SSOIL_AERO_STATUS_VALUE','').strip()},
}


def ident(value):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',value):
        raise ValueError('Invalid SQL column name')
    return '['+value+']'

def num(value):
    if value is None: return 0.0
    return float(value)

def query(sql,params=()):
    if not sql.lstrip().upper().startswith('SELECT ') or ';' in sql:
        raise ValueError('Read-only SELECT queries required')
    with pyodbc.connect(ODBC,timeout=10,autocommit=True) as db:
        return db.cursor().execute(sql,tuple(params)).fetchall()

def snapshot():
    rows=query('SELECT Art_ID,Naziv,PCena,Kolicina FROM dbo.ART')
    products={str(r[0]):{'id':str(r[0]),'name':str(r[1] or ''),'price':num(r[2]),'stock':num(r[3]),'barcodes':[]} for r in rows}
    for aid,code in query('SELECT Art_ID,BKod_ID FROM dbo.ART_BK'):
        item=products.get(str(aid))
        b=str(code or '').strip()
        if item is not None and b and b not in item['barcodes']:
            item['barcodes'].append(b)
    return {'products':list(products.values()),'updated_at':datetime.now().isoformat(timespec='seconds')}

def _table_columns(table):
    # Metadata only; no SQL changes.
    schema,name=table.split('.')
    rows=query("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=? AND TABLE_NAME=?",(schema,name))
    return {str(r[0]).lower():str(r[0]) for r in rows}

def _dated_sales_sql(days):
    s_cols=_table_columns('dbo.SmP_S')
    z_cols=_table_columns('dbo.SmP_Z')
    cutoff=datetime.now()-timedelta(days=days)
    if DATE_COL:
        col=DATE_COL.lower()
        if col not in s_cols:raise ValueError('Configured sales date column does not exist in SmP_S')
        return ('SELECT s.Art_ID,SUM(s.Kolicina) FROM dbo.SmP_S s WHERE s.'+ident(s_cols[col])+' >= ? GROUP BY s.Art_ID',[cutoff])
    for candidate in ('datume','datum','date','createdat'):
        if candidate in s_cols:
            return ('SELECT s.Art_ID,SUM(s.Kolicina) FROM dbo.SmP_S s WHERE s.'+ident(s_cols[candidate])+' >= ? GROUP BY s.Art_ID',[cutoff])
    if 'broj' not in s_cols or 'broj' not in z_cols or 'datume' not in z_cols:
        raise ValueError('Cannot link SmP_S to dated receipts in SmP_Z')
    # EXISTS prevents multiplication of sales lines when receipt numbers repeat.
    joins=['z.[Broj]=s.[Broj]']
    if 'kasa_id' in s_cols and 'kasa_id' in z_cols:
        joins.append('z.[Kasa_ID]=s.[Kasa_ID]')
    else:
        # Without a unique receipt identifier, dates may be ambiguous.
        check=query('SELECT TOP 1 Broj FROM dbo.SmP_Z GROUP BY Broj HAVING COUNT(DISTINCT CONVERT(date,DatumE))>1')
        if check:raise ValueError('SmP_Z receipt numbers repeat across dates; Kasa_ID join required for reliable sales')
    sql=('SELECT s.Art_ID,SUM(s.Kolicina) FROM dbo.SmP_S s WHERE EXISTS '
         '(SELECT 1 FROM dbo.SmP_Z z WHERE '+' AND '.join(joins)+' AND z.[DatumE]>=? AND z.[DatumE]<?) GROUP BY s.Art_ID')
    return sql,[cutoff,datetime.now()+timedelta(days=1)]

def sales(days=None):
    if days is None:
        rows=query('SELECT Art_ID,SUM(Kolicina) FROM dbo.SmP_S GROUP BY Art_ID')
        return {'sales':{str(r[0]):num(r[1]) for r in rows}}
    sql,params=_dated_sales_sql(days)
    return {'period_days':days,'sales':{str(r[0]):num(r[1]) for r in query(sql,params)}}

def product(aid):
    if not aid.isdigit(): raise ValueError('Invalid product ID')
    rows=query('SELECT Art_ID,PCena,Kolicina FROM dbo.ART WHERE Art_ID=?',(int(aid),))
    if not rows:return None
    r=rows[0]
    sold=query('SELECT COALESCE(SUM(Kolicina),0) FROM dbo.SmP_S WHERE Art_ID=?',(int(aid),))[0][0]
    base=num(r[2]); qty=num(sold)
    return {'id':str(r[0]),'price':num(r[1]),'stock':base-qty,'art_stock':base,'sales':qty}

def sqlite_ident(name):
    return '"' + str(name).replace('"', '""') + '"'


def _dopuna_candidates(kind):
    cfg=DOPUNA_CONFIG[kind]
    if cfg['path']:
        return [os.path.abspath(cfg['path'])]
    # PcPos installations can store transactions in Local.db3 or Global.db3.
    # Search local folders only; never connect to or modify another program.
    roots=[os.path.dirname(os.path.abspath(__file__)), os.getcwd()]
    for key in ('SSOIL_DOPUNA_DIR','SSOIL_PCPOS_DIR'):
        if os.getenv(key): roots.append(os.path.abspath(os.getenv(key)))
    found=[]
    for root in dict.fromkeys(roots):
        for name in ('Local.db3','Global.db3','local.db3','global.db3'):
            path=os.path.join(root,name)
            if os.path.isfile(path) and path not in found:found.append(path)
    return found


def _field(cols, candidates):
    indexed={c.lower():c for c in cols}
    for name in candidates:
        if name.lower() in indexed:return indexed[name.lower()]
    return None


def _amount(value):
    if value is None:return None
    if isinstance(value,(int,float,Decimal)):return float(value)
    raw=str(value).strip().replace(' ','').replace('KM','')
    if ',' in raw:raw=raw.replace('.','').replace(',','.')
    try:return float(raw)
    except ValueError:return None


def _date_matches(value,day):
    if value is None:return False
    text=str(value).strip()
    expected=datetime.strptime(day,'%Y-%m-%d')
    # ISO, PcPos DD.MM.YYYY, and UNIX seconds/milliseconds.
    if text.startswith(day) or text.startswith(expected.strftime('%d.%m.%Y')):return True
    if isinstance(value,(int,float)):
        try:
            ts=float(value)
            if ts>1e11:ts/=1000
            return datetime.fromtimestamp(ts).date()==expected.date()
        except (ValueError,OverflowError,OSError):return False
    return False


def _success(value):
    if value is None:return False
    status=str(value).strip().lower()
    # Accept (00) Uspjesno / Uspješno or exact numeric success code 00.
    return bool(re.match(r'^\(?00\)?(?:\s|$)',status)) or status in ('0','00','uspjesno','uspješno')


def _kind_matches(kind,value):
    if value is None:return False
    text=str(value).casefold()
    if kind=='mtel':return 'm:tel' in text or 'mtel' in text
    return 'aero' in text


def _dopuna_read(path,kind,day,cfg):
    # Verified PcPos Local.db3 schema: txes(date, amount, statusId, productId).
    # Amount is stored in minor currency units (100 = 1 KM).
    from pathlib import Path
    uri=Path(path).as_uri()+'?mode=ro'
    with sqlite3.connect(uri,uri=True,timeout=5) as db:
        db.execute('PRAGMA query_only=ON')
        cols={r[1].lower() for r in db.execute('PRAGMA table_info("txes")')}
        if not {'date','amount','statusid'}.issubset(cols):
            return {'total':None,'count':None,'status':'unexpected_pcpos_schema'}
        target=datetime.strptime(day,'%Y-%m-%d').date()
        total_minor=0;count=0
        for stamp,amount,status in db.execute('SELECT "date","amount","statusId" FROM "txes" WHERE "statusId"=?',('00',)):
            # PcPos uses both 08.10.2026 and 08.10.2026. timestamps.
            m=re.match(r'^(\d{2})\.(\d{2})\.(\d{4})',str(stamp or ''))
            if not m:continue
            try:dt=datetime(int(m[3]),int(m[2]),int(m[1])).date()
            except ValueError:continue
            if dt!=target:continue
            if amount is None:continue
            total_minor+=int(amount);count+=1
        return {'total':round(total_minor/100,2),'count':count,'status':'ok','source':os.path.basename(path),'table':'txes'}

def dopuna_one(kind,day):
    cfg=DOPUNA_CONFIG[kind]
    paths=_dopuna_candidates(kind)
    if not paths:return {'total':None,'count':None,'status':'database_not_found','hint':'Set SSOIL_'+kind.upper()+'_DB to the PcPos database path'}
    results=[]
    for path in paths:
        if not os.path.isfile(path):continue
        try:
            result=_dopuna_read(path,kind,day,cfg)
            if result['status']=='ok':results.append(result)
            elif result['status']=='ambiguous_tables':return result
        except (sqlite3.Error,ValueError,OSError) as exc:
            logging.warning('Dopuna %s %s: %s',kind,path,exc)
    if len(results)==1:return results[0]
    if len(results)>1:return {'total':None,'count':None,'status':'ambiguous_databases'}
    return {'total':None,'count':None,'status':'schema_or_date_not_verified'}

def dopuna(day=None):
    if day is None:day=datetime.now().date().isoformat()
    datetime.strptime(day,'%Y-%m-%d')
    mtel=dopuna_one('mtel',day);aero=dopuna_one('aero',day)
    total=(mtel['total']+aero['total']) if mtel['total'] is not None and aero['total'] is not None else None
    return {'date':day,'mtel':mtel,'aero':aero,'total':total}

def kasa(day=None):
    if day is None: day=datetime.now().date().isoformat()
    try: start=datetime.strptime(day,'%Y-%m-%d')
    except ValueError: raise ValueError('date must be YYYY-MM-DD')
    end=start+timedelta(days=1)
    rows=query('SELECT COALESCE(SUM(Iznos),0),COALESCE(SUM(Gotovina),0),COALESCE(SUM(Kartica),0),COALESCE(SUM(Povracaj),0),COUNT(*) FROM dbo.SmP_Z WHERE DatumE>=? AND DatumE<?',(start,end))
    r=rows[0]
    d=dopuna(day)
    return {'date':day,'total':num(r[0]),'cash':num(r[1])-num(r[3])+(d['total'] or 0) if d['total'] is not None else None,'cash_smpsz':num(r[1])-num(r[3]),'card':num(r[2]),'refund':num(r[3]),'receipt_count':int(r[4]),'dopuna':d,
            'mtel_dopuna':d['mtel']['total'],'aero_dopuna':d['aero']['total']}

def fuel_transactions():
    ids={str(aid):name for name,items in FUEL_MAP.items() for aid in items}
    if not ids:raise ValueError('SSOIL_FUEL_ART_IDS not configured')
    if len(ids)>500:raise ValueError('Too many fuel IDs')
    placeholders=','.join('?' for _ in ids)
    sql='SELECT '+ident(BROJ_COL)+',Art_ID,SUM(Kolicina) FROM dbo.SmP_S WHERE Art_ID IN ('+placeholders+') GROUP BY '+ident(BROJ_COL)+',Art_ID'
    result={}
    for broj,aid,liters in query(sql,[int(aid) for aid in ids]):
        if broj is None:continue
        key=str(broj); item=result.setdefault(key,{'broj':key,'liters':{},'total_liters':0})
        label=ids[str(aid)]; qty=num(liters)
        item['liters'][label]=item['liters'].get(label,0)+qty
        item['total_liters']+=qty
    return {'transactions':list(result.values())}

# Separate application-owned SQLite database. The POS SQL Server remains read-only.
CENTRAL_DB=os.getenv('SSOIL_CENTRAL_DB',os.path.join(os.path.dirname(__file__),'SSOIL_MERKEZ.db'))
CENTRAL_LOCK=threading.RLock()
SHARED_SECTIONS={'labels','orders','suppliers','supplierOf','minimum'}

def central_connect():
    db=sqlite3.connect(CENTRAL_DB,timeout=15)
    db.execute('PRAGMA busy_timeout=15000')
    return db

def central_init():
    with CENTRAL_LOCK,central_connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS shared (section TEXT NOT NULL, item_key TEXT NOT NULL, value_json TEXT, revision INTEGER NOT NULL DEFAULT 0, changed_at TEXT NOT NULL, PRIMARY KEY(section,item_key))')
        db.execute('CREATE TABLE IF NOT EXISTS changes (revision INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE, section TEXT NOT NULL, item_key TEXT NOT NULL, value_json TEXT, changed_at TEXT NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS sales_totals (art_id TEXT PRIMARY KEY, cumulative REAL NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS sales_daily (sale_day TEXT NOT NULL, art_id TEXT NOT NULL, quantity REAL NOT NULL, PRIMARY KEY(sale_day,art_id))')
        db.execute('CREATE TABLE IF NOT EXISTS sales_poll (id INTEGER PRIMARY KEY CHECK(id=1), checked_at TEXT, error TEXT)')

def shared_changes(since=0):
    with CENTRAL_LOCK,central_connect() as db:
        rows=db.execute('SELECT revision,section,item_key,value_json FROM changes WHERE revision>? ORDER BY revision LIMIT 2000',(since,)).fetchall()
        latest=db.execute('SELECT COALESCE(MAX(revision),0) FROM changes').fetchone()[0]
    return {'revision':latest,'changes':[{'revision':r,'section':sec,'key':key,'value':json.loads(val) if val is not None else None} for r,sec,key,val in rows], 'has_more':bool(rows and rows[-1][0]<latest)}

def shared_write(body):
    sec=body.get('section');key=str(body.get('key',''));event=str(body.get('event_id',''))
    if sec not in SHARED_SECTIONS or not key or len(key)>200 or len(event)<8:raise ValueError('Invalid shared event')
    value=body.get('value'); payload=None if value is None else json.dumps(value,ensure_ascii=False)
    now=datetime.now().isoformat(timespec='seconds')
    with CENTRAL_LOCK,central_connect() as db:
        old=db.execute('SELECT revision FROM changes WHERE event_id=?',(event,)).fetchone()
        if old:return {'revision':old[0],'duplicate':True}
        cur=db.execute('INSERT INTO changes(event_id,section,item_key,value_json,changed_at) VALUES(?,?,?,?,?)',(event,sec,key,payload,now))
        rev=cur.lastrowid
        db.execute('INSERT INTO shared(section,item_key,value_json,revision,changed_at) VALUES(?,?,?,?,?) ON CONFLICT(section,item_key) DO UPDATE SET value_json=excluded.value_json,revision=excluded.revision,changed_at=excluded.changed_at',(sec,key,payload,rev,now))
    return {'revision':rev}

def sales_poll_once():
    # Cumulative quantities are sampled by PC clock. Missing historical days cannot be reconstructed.
    today=datetime.now().date().isoformat()
    totals=sales()['sales']
    with CENTRAL_LOCK,central_connect() as db:
        for aid,raw in totals.items():
            current=float(raw)
            row=db.execute('SELECT cumulative FROM sales_totals WHERE art_id=?',(aid,)).fetchone()
            if row is not None:
                delta=max(0,current-row[0])
                if delta>0:
                    db.execute('INSERT INTO sales_daily(sale_day,art_id,quantity) VALUES(?,?,?) ON CONFLICT(sale_day,art_id) DO UPDATE SET quantity=quantity+excluded.quantity',(today,aid,delta))
            db.execute('INSERT INTO sales_totals(art_id,cumulative) VALUES(?,?) ON CONFLICT(art_id) DO UPDATE SET cumulative=excluded.cumulative',(aid,current))
        db.execute('DELETE FROM sales_daily WHERE sale_day<?',((datetime.now()-timedelta(days=6)).date().isoformat(),))
        db.execute('INSERT INTO sales_poll(id,checked_at,error) VALUES(1,?,NULL) ON CONFLICT(id) DO UPDATE SET checked_at=excluded.checked_at,error=NULL',(datetime.now().isoformat(timespec='seconds'),))

def poll_loop():
    while True:
        try:sales_poll_once()
        except Exception as exc:
            logging.warning('Sales poll failed: %s',exc)
            with CENTRAL_LOCK,central_connect() as db:
                db.execute('INSERT INTO sales_poll(id,checked_at,error) VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET error=excluded.error',(datetime.now().isoformat(timespec='seconds'),str(exc)[:300]))
        time.sleep(max(15,int(os.getenv('SSOIL_POLL_SECONDS','30'))))

def daily_sales():
    with CENTRAL_LOCK,central_connect() as db:
        rows=db.execute('SELECT sale_day,art_id,quantity FROM sales_daily ORDER BY sale_day').fetchall()
        status=db.execute('SELECT checked_at,error FROM sales_poll WHERE id=1').fetchone()
    result={}
    for day,aid,qty in rows:result.setdefault(day,{})[aid]=qty
    return {'daily':result,'last_checked':status[0] if status else None,'error':status[1] if status else 'not_started'}

class Handler(BaseHTTPRequestHandler):
    def respond(self,status,payload):
        data=json.dumps(payload,ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.end_headers();self.wfile.write(data)
    def do_GET(self):
        try:
            p=urlsplit(self.path); args=parse_qs(p.query)
            supplied=self.headers.get('X-SSOIL-Token','') or self.headers.get('X-API-Token','')
            if not hmac.compare_digest(supplied,TOKEN):return self.respond(401,{'error':'unauthorized'})
            if p.path=='/health':return self.respond(200,{'status':'ok','central_db':True})
            if p.path=='/shared':return self.respond(200,shared_changes(max(0,int(args.get('since',['0'])[0]))))
            if p.path=='/daily-sales':return self.respond(200,daily_sales())
            if p.path in ('/snapshot','/products'):return self.respond(200,snapshot())
            if p.path=='/sales':
                days=args.get('days',[None])[0]
                if days is not None:
                    days=int(days)
                    if not 1<=days<=3650:raise ValueError('days must be 1..3650')
                return self.respond(200,sales(days))
            if p.path.startswith('/product/'):
                aid=unquote(p.path[len('/product/'):]); item=product(aid)
                return self.respond(200,item) if item else self.respond(404,{'error':'not found'})
            if p.path=='/product':
                aid=args.get('id',[''])[0]; item=product(aid)
                return self.respond(200,item) if item else self.respond(404,{'error':'not found'})
            if p.path in ('/kasa','/cash','/cash-summary'):
                return self.respond(200,kasa(args.get('date',[None])[0]))
            if p.path in ('/dopuna','/dopuna-summary'):
                return self.respond(200,dopuna(args.get('date',[None])[0]))
            if p.path=='/fuel-transactions':return self.respond(200,fuel_transactions())
            return self.respond(404,{'error':'unknown endpoint'})
        except (ValueError,TypeError) as exc:return self.respond(400,{'error':str(exc)})
        except Exception:
            logging.exception('Request failed: %s',self.path)
            return self.respond(500,{'error':'server error; check server console'})
    def do_POST(self):
        try:
            if not hmac.compare_digest(self.headers.get('X-SSOIL-Token',''),TOKEN):return self.respond(401,{'error':'unauthorized'})
            if urlsplit(self.path).path!='/shared':return self.respond(404,{'error':'unknown endpoint'})
            length=int(self.headers.get('Content-Length','0'))
            if length<=0 or length>65536:return self.respond(413,{'error':'invalid payload size'})
            body=json.loads(self.rfile.read(length))
            if not isinstance(body,dict):raise ValueError('JSON object required')
            return self.respond(200,shared_write(body))
        except (ValueError,TypeError,json.JSONDecodeError) as exc:return self.respond(400,{'error':str(exc)})
        except Exception:
            logging.exception('Shared write failed')
            return self.respond(500,{'error':'server error'})
    def do_PUT(self):return self.respond(405,{'error':'read only'})
    def do_DELETE(self):return self.respond(405,{'error':'read only'})

if __name__=='__main__':
    central_init()
    threading.Thread(target=poll_loop,daemon=True).start()
    print('SS OIL API listening on %s:%s'%(HOST,PORT),flush=True)
    ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
