import copy,json,time,uuid
from datetime import datetime,timezone,timedelta
from concurrent.futures import ThreadPoolExecutor
import pytest
from test_mines import live,account,prepare,settings,match
from backend import mines_engine as e
from test_platform import signin,write

def truth(app,mid):
    with app.state.db.connect() as conn:return json.loads(conn.execute('SELECT state FROM mines_matches WHERE id=?',(mid,)).fetchone()[0])
def sync(c,code,h):return c.post(f'/api/mines/rooms/{code}/sync',headers=h,json={}).json()['match']
def move(c,code,h,m,action,cell=None,**extra):
    body={'match_id':m['id'],'version':m['version'],'command_id':uuid.uuid4().hex,'action':action,**extra}
    if cell is not None:body['cell']=cell
    r=c.post(f'/api/mines/rooms/{code}/command',headers=h,json=body)
    assert r.status_code==200,r.text
    return r.json()['match'],body

@pytest.mark.parametrize('mode,n',[(mode,n) for mode in e.MODES for n in range(2,7) if mode!='team' or n==6])
def test_all_modes_counts_full_win_result_again_and_old_commands(live,mode,n):
    c,app,_=live;ps=[account(c,i) for i in range(n)];code=prepare(c,ps,mode);m=sync(c,code,ps[0][0]);private=truth(app,m['id']);layout=private['layout'];last=None
    if mode=='hunt':
        for _ in range(n*3):
            uid=m['turn_player'];h=next(h for h,i in ps if i==uid)
            if uid==ps[0][1]:action='confirm';cell=next(i for i in layout['mines'] if m['cells'][i]==7)
            else:action='open';cell=next(i for i,v in enumerate(m['cells']) if v==7 and i not in layout['mines'])
            m,last=move(c,code,h,m,action,cell)
            if m['ended'] is not None:break
    elif mode=='puzzle':
        for _ in range(len(m['cells'])*2):
            visible=[v if 0<=v<=6 else -1 if v!= -2 else -2 for v in m['cells']]
            hint=e.deduction(layout,visible,set(map(int,m['flags'])))
            assert hint is not None
            m,last=move(c,code,ps[0][0],m,'flag' if hint['mine'] else 'open',hint['cell'])
            if m['ended'] is not None:break
    else:
        path,_=e.route(layout,set(range(len(m['cells'])))-set(layout['mines']))
        for i in path:
            if m['cells'][i]==7:m,last=move(c,code,ps[0][0],m,'open',i)
            if m['ended'] is not None:break
    assert m['ended'] is not None and ps[0][1] in m['winners']
    for h,_ in ps:assert sync(c,code,h)['winners']==m['winners']
    records=c.get('/api/mines/records',headers=ps[0][0]).json()['records'];assert len(records)==1
    assert records[0]['players']==n and records[0]['settings']==settings(mode)
    with app.state.db.connect() as conn:assert conn.execute('SELECT count(*) FROM mines_results WHERE match_id=?',(m['id'],)).fetchone()[0]==n
    again=c.post(f'/api/mines/rooms/{code}/again',headers=ps[0][0],json={'revision':1});assert again.status_code==200
    for h,_ in ps:assert c.post(f'/api/mines/rooms/{code}/ready',headers=h,json={'ready':True,'revision':2}).status_code==200
    assert c.post(f'/api/mines/rooms/{code}/start',headers=ps[0][0],json={'revision':2}).status_code==200
    new=sync(c,code,ps[0][0]);assert new['id']!=m['id']
    rejected=c.post(f'/api/mines/rooms/{code}/command',headers=ps[0][0],json=last)
    assert rejected.status_code==409 and rejected.json()['error']['code']=='STALE_MATCH'

def test_simultaneous_open_dedupe_and_payload_reuse(live):
    c,app,_=live;ps=[account(c,i) for i in range(2)];code=prepare(c,ps);m=sync(c,code,ps[0][0]);private=truth(app,m['id'])
    cell=private['layout']['mines'][0]
    body={'match_id':m['id'],'version':m['version'],'command_id':uuid.uuid4().hex,'action':'open','cell':cell}
    with ThreadPoolExecutor(2) as pool:responses=list(pool.map(lambda h:c.post(f'/api/mines/rooms/{code}/command',headers=h,json=body),[p[0] for p in ps]))
    assert sorted(r.status_code for r in responses)==[200,409]
    winner=next(i for i,r in enumerate(responses) if r.status_code==200)
    again=c.post(f'/api/mines/rooms/{code}/command',headers=ps[winner][0],json=body)
    assert again.json()['duplicate'] and again.json()['match']['safety']==2
    bad=c.post(f'/api/mines/rooms/{code}/command',headers=ps[winner][0],json={**body,'cell':cell+1})
    assert bad.json()['error']['code']=='COMMAND_REUSED'
    assert len([v for v in sync(c,code,ps[1-winner][0])['events'] if v['kind']=='blast'])==1

def test_admin_close_cannot_continue_and_qa_results_excluded(live):
    c,app,_=live;ps=[account(c,i) for i in range(2)];code=prepare(c,ps);m=sync(c,code,ps[0][0])
    with app.state.db.connect(write=True) as conn:
        for _,uid in ps:conn.execute('INSERT INTO mines_test_users VALUES(?)',(uid,))
    admin,_=signin(app,'owner@haoke.local');assert write(admin,'POST',f'/api/admin/rooms/{code}/close').status_code==200
    assert c.post(f'/api/mines/rooms/{code}/sync',headers=ps[0][0],json={}).status_code==410
    after=truth(app,m['id']);assert after['ended'] is not None and after['reason']=='room_closed' and after['winners']==[]
    with app.state.db.connect() as conn:assert conn.execute('SELECT count(*) FROM mines_results').fetchone()[0]==0
    stats=admin.get('/api/admin/stats');assert stats.status_code==200,stats.text
    mines=next(g for g in stats.json()['games'] if g['id']=='mines3d');assert mines['matches']==0

def test_all_down_stability_exhaustion_timeouts_tie_and_daily_midnight():
    m=match('coop',2)
    for i in range(2):e.apply(m,str(i),'open',m['layout']['mines'][i],None,1001+i)
    assert m['ended'] is not None and m['winners']==[]
    m=match('coop',4)
    for i in range(3):e.apply(m,str(i),'open',m['layout']['mines'][i],None,1001+i)
    assert m['boards']['shared']['safety']==0 and not m['winners'] and m['ended'] is not None
    m=match('hunt',2)
    for p in m['players']:p['seen']=1200
    e.tick(m,1076);assert m['ended'] is not None and m['reason']=='last_survivor'
    m=match('hunt',3);m['target']=99
    for i,cell in enumerate(m['layout']['mines']):
        uid=str(m['turn']);e.apply(m,uid,'confirm',cell,None,1001+i)
        if m['ended'] is not None:break
    best=max(p['score'] for p in m['players']);assert m['winners']==[p['id'] for p in m['players'] if p['score']==best] and m['reason']=='all_mines'
    cfg=settings('daily');players=[{'id':str(i),'name':str(i)} for i in range(2)];midnight=datetime(2026,11,16,tzinfo=timezone(timedelta(hours=8))).timestamp()
    a=e.new_match(cfg,players,'a',midnight-1,'test');b=e.new_match(cfg,players,'b',midnight-10,'test');assert a['layout']==b['layout']
    original=copy.deepcopy(a['layout']);e.tick(a,midnight+1);assert a['layout']==original and a['day']==b['day']
    tomorrow=e.new_match(cfg,players,'c',midnight+1,'test');assert tomorrow['day']!=a['day'] and tomorrow['layout']!=a['layout']

def test_commands_refresh_activity_and_invitation_does_not_join(live,monkeypatch):
    c,app,_=live;ps=[account(c,i) for i in range(2)];code=prepare(c,ps);m=sync(c,code,ps[0][0]);original=truth(app,m['id']);now=original['created']+30
    monkeypatch.setattr('backend.mines.time.time',lambda:now)
    public=c.get(f'/api/invitations/{code}?game_id=mines3d').json()
    assert public['status']=='playing' and public['member_count']==2 and public['spectators']==0
    cell=next(i for i,v in enumerate(m['cells']) if v==7)
    m,body=move(c,code,ps[0][0],m,'danger',cell)
    assert truth(app,m['id'])['players'][0]['seen']==now
    now+=5
    r=c.post(f'/api/mines/rooms/{code}/command',headers=ps[0][0],json=body)
    assert r.json()['duplicate'] and truth(app,m['id'])['players'][0]['seen']==now
    assert c.get(f'/api/invitations/{code}?game_id=mines3d').json()['member_count']==2

def test_offline_survivor_cannot_win_and_disconnected_turn_is_skipped():
    m=match('hunt',2);m['players'][1]['status']='out';e.tick(m,1011)
    assert m['ended'] is None
    m=match('hunt',3);m['players'][1]['seen']=1061;m['players'][2]['seen']=1061;m['deadline']=1070
    e.tick(m,1061);assert m['turn']!=0 and m['ended'] is None

def test_hunt_openings_maximum_and_private_projection():
    for n in range(2,7):
        m=match('hunt',n,size=15,layers=8);p=e.project(m,'0',1000)
        visible=[v if 0<=v<=6 else -1 for v in p['cells']]
        assert e.deduction(m['layout'],visible) is not None
        assert len(p['cells'])==1800 and max(m['layout']['clues'])<=6
        for viewer in ['0','observer']:
            encoded=json.dumps(e.project(m,viewer,1001));assert '"seed"' not in encoded and '"mines"' not in encoded and '"layout"' not in encoded
