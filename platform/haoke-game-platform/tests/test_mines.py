"""Synthetic accounts, explicit temporary databases, development mailbox only."""
import copy
import json
import time
import uuid
import pytest
from fastapi.testclient import TestClient
from backend.app import create_app
from backend.config import Settings
from backend import mines_engine as e


def settings(mode='coop',**more):return {'mode':mode,'difficulty':0,'map':0,'size':5,'layers':0,**more}
def players(n):return [{'id':str(i),'name':f'Tester {i}','role':('miner','scout','medic')[i%3]} for i in range(n)]
def match(mode='coop',n=2,**more):return e.new_match(settings(mode,**more),players(n),'m'*32,1000,'isolated-test-secret')


@pytest.mark.parametrize('n',range(2,7))
@pytest.mark.parametrize('mode',['coop','hunt','puzzle','fault','daily','race'])
def test_modes_counts_public_projection(n,mode):
    m=match(mode,n)
    assert len(m['players'])==n
    for p in m['players']:
        public=e.project(m,p['id'],1000)
        assert 'layout' not in public and 'seed' not in public and 'mines' not in public
        assert len(public['cells'])==m['layout']['size']**2*m['layout']['layers']
        for i in m['layout']['mines']:assert public['cells'][i]==7
    if mode not in ('hunt','puzzle'):
        path,_=e.route(m['layout'],set(range(len(m['layout']['present'])))-set(m['layout']['mines']))
        assert path


@pytest.mark.parametrize('level',range(3))
def test_public_puzzle_proofs(level):
    m=match('puzzle',map=level)
    assert e.verify_puzzle(m['layout'])
    board=m['boards']['shared'];layout=m['layout']
    for _ in range(400):
        if m['ended'] is not None:break
        e.apply(m,'0','hint',None,None,1001)
        h=board['hint']
        e.apply(m,'0','flag' if h['mine'] else 'open',h['cell'],None,1001)
    assert m['winners']==['0','1']


@pytest.mark.parametrize('shape',range(4))
def test_fault_topology_and_routes(shape):
    m=match('fault',4,map=shape)
    layout=m['layout'];assert not all(layout['present'])
    for i,present in enumerate(layout['present']):
        if not present:assert e.neighbors(layout,i)==[]
        else:assert layout['clues'][i]==sum(n in layout['mines'] for n in e.neighbors(layout,i))
    path,_=e.route(layout,{i for i,p in enumerate(layout['present']) if p and i not in layout['mines']})
    for i in path:
        if i not in m['boards']['shared']['opened']:e.apply(m,'0','open',i,None,1001)
    assert m['winners']==['0','1','2','3']


def test_hunt_turn_wrong_claim_timeout_and_reconnect_clock():
    m=match('hunt',3);board=m['boards']['shared'];layout=m['layout']
    cell=next(i for i in range(len(layout['present'])) if i not in board['opened'] and i not in layout['mines'])
    with pytest.raises(e.RuleError,match='NOT_YOUR_TURN'):e.apply(m,'1','open',cell,None,1001)
    e.apply(m,'0','confirm',cell,None,1001)
    assert m['players'][0]['status']=='out' and m['turn']==1
    e.apply(m,'1','open',layout['mines'][0],None,1002)
    assert m['winners']==['2']
    m=match('hunt',3)
    for p in m['players']:p['seen']=1100
    e.tick(m,1046)
    assert [p['misses'] for p in m['players']]==[1,1,1]
    assert m['deadline']==1060
    m=match('hunt',2);e.tick(m,1100)
    assert m['reason']=='all_disconnected' and m['winners']==[]


def test_hunt_claim_target_and_exposed_mines_finish():
    m=match('hunt',2);mines=m['layout']['mines']
    for i in range(5):e.apply(m,str(i%2),'confirm',mines[i],None,1001+i)
    assert m['winners']==['0'] and m['reason']=='target'
    before=copy.deepcopy(m)
    with pytest.raises(e.RuleError):e.apply(m,'0','confirm',mines[0],None,1010)
    assert m==before


def test_coop_rescue_scans_marks_and_fixed_truth():
    m=match('coop',3);layout=copy.deepcopy(m['layout']);board=m['boards']['shared']
    e.apply(m,'0','open',layout['mines'][0],None,1001)
    assert m['players'][0]['status']=='down' and board['safety']==2
    e.apply(m,'2','rescue',None,'0',1002)
    assert m['players'][0]['status']=='active'
    targets=[i for i,c in enumerate(layout['clues']) if c>0 and i not in layout['mines']]
    for i in targets[:2]:
        if i not in board['opened']:e.apply(m,'0','open',i,None,1003)
        e.apply(m,'0','scan',i,None,1004)
        assert sum(board['scans'][str(i)])==layout['clues'][i]
    assert board['scans_left']==0
    e.apply(m,'0','scan',targets[0],None,1005)
    assert board['scans_left']==0
    assert m['layout']==layout


def test_daily_fixed_by_date_count_and_race_team_visibility():
    a=match('daily',3);b=match('daily',3);assert a['layout']==b['layout']
    assert a['layout']!=match('daily',4)['layout']
    m=match('race',3);i=next(i for i in range(len(m['layout']['present'])) if i not in m['boards']['0']['opened'] and i not in m['layout']['mines'])
    e.apply(m,'0','open',i,None,1001)
    assert e.project(m,'0',1002)['cells'][i]<7
    assert e.project(m,'1',1002,watch='0')['cells'][i]==7
    assert not e.project(m,'1',1002)['events']
    t=match('team',6);assert len(t['boards'])==2
    with pytest.raises(e.RuleError,match='TEAM_REQUIRES_SIX'):match('team',5)


@pytest.fixture
def live(tmp_path):
    cfg=Settings(data_dir=tmp_path,secret='mines-isolated-test-only-secret-32',otp_cooldown=0)
    app=create_app(cfg)
    with TestClient(app,client=('127.0.0.1',1234)) as client:yield client,app,cfg


def account(c,i):
    challenge=c.post('/api/auth/code',json={'email':f'mines-{i}@example.com'}).json()['challenge_id']
    code=c.get('/api/dev/mailbox',params={'challenge_id':challenge}).json()['code']
    signed=c.post('/api/auth/verify',json={'challenge_id':challenge,'code':code,'client':'native'}).json()
    h={'Authorization':'Bearer '+signed['access_token']}
    assert c.post('/api/mines/enter',headers=h,json={'protocol':1,'build':19}).status_code==200
    return h,signed['user']['id']


def prepare(c,players,mode='coop'):
    response=c.post('/api/mines/rooms',headers=players[0][0],json={'settings':settings(mode)})
    assert response.status_code==200,response.text
    code=response.json()['room']['code']
    for h,_ in players[1:]:assert c.post(f'/api/mines/rooms/{code}/join',headers=h,json={}).status_code==200
    for h,_ in players:assert c.post(f'/api/mines/rooms/{code}/ready',headers=h,json={'ready':True,'revision':1}).status_code==200
    response=c.post(f'/api/mines/rooms/{code}/start',headers=players[0][0],json={'revision':1});assert response.status_code==200,response.text
    return code


@pytest.mark.parametrize('n',range(2,7))
def test_api_actual_counts_dedupe_host_leave_restart(live,n):
    c,app,cfg=live;ps=[account(c,i) for i in range(n)];code=prepare(c,ps)
    def sync(h):return c.post(f'/api/mines/rooms/{code}/sync',headers=h,json={}).json()
    public=sync(ps[0][0])['match']
    # Truth is read directly from the isolated DB by this test, never through an API.
    with app.state.db.connect() as conn:m=json.loads(conn.execute('SELECT state FROM mines_matches WHERE id=?',(public['id'],)).fetchone()[0])
    path,_=e.route(m['layout'],set(range(len(m['layout']['present'])))-set(m['layout']['mines']))
    cell=next(i for i in path if public['cells'][i]==7)
    command={'match_id':public['id'],'version':public['version'],'command_id':uuid.uuid4().hex,'action':'open','cell':cell}
    first=c.post(f'/api/mines/rooms/{code}/command',headers=ps[0][0],json=command);assert first.status_code==200,first.text
    again=c.post(f'/api/mines/rooms/{code}/command',headers=ps[0][0],json=command)
    assert again.json()['duplicate'] and again.json()['match']['version']==first.json()['match']['version']
    assert c.post(f'/api/mines/rooms/{code}/leave',headers=ps[0][0]).status_code==200
    after=sync(ps[1][0]);assert after['room']['host']==ps[1][1] and after['match']['cells'][cell]<7
    # A new app instance against the same isolated persistent database retains this match.
    other=create_app(cfg)
    with TestClient(other,client=('127.0.0.1',1234)) as restarted:
        r=restarted.post(f'/api/mines/rooms/{code}/sync',headers=ps[1][0],json={}).json()
        assert r['match']['id']==public['id'] and r['match']['cells'][cell]<7


def test_api_spectators_settings_matchmaking_and_stale(live):
    c,app,_=live;ps=[account(c,i) for i in range(7)]
    for h,_ in ps[:2]:assert c.post('/api/mines/matchmaking/enqueue',headers=h,json={'settings':settings('hunt')}).status_code==200
    q=c.post('/api/mines/matchmaking/poll',headers=ps[0][0]).json();code=q['room']['code']
    cancelled=c.post('/api/mines/matchmaking/cancel',headers=ps[1][0]).json();assert cancelled['room']['code']==code
    for h,_ in ps[2:6]:assert c.post(f'/api/mines/rooms/{code}/join',headers=h,json={}).status_code==200
    assert c.post(f'/api/mines/rooms/{code}/join',headers=ps[6][0],json={}).status_code==409
    for h,_ in ps[:6]:c.post(f'/api/mines/rooms/{code}/ready',headers=h,json={'ready':True,'revision':1})
    r=c.post(f'/api/mines/rooms/{code}/configure',headers=ps[0][0],json={'revision':1,'settings':settings('hunt',difficulty=1)});assert r.status_code==200
    assert not any(p['ready'] for p in r.json()['room']['players'])
    assert c.post(f'/api/mines/rooms/{code}/ready',headers=ps[1][0],json={'ready':True,'revision':1}).status_code==409
    for h,_ in ps[:6]:c.post(f'/api/mines/rooms/{code}/ready',headers=h,json={'ready':True,'revision':2})
    assert c.post(f'/api/mines/rooms/{code}/start',headers=ps[0][0],json={'revision':2}).status_code==200
    assert c.post(f'/api/mines/rooms/{code}/watch',headers=ps[6][0]).status_code==200
    state=c.post(f'/api/mines/rooms/{code}/sync',headers=ps[6][0],json={}).json()
    assert state['room']['spectators']==1 and len(state['room']['players'])==6
    m=state['match'];payload={'match_id':m['id'],'version':m['version'],'command_id':uuid.uuid4().hex,'action':'confirm','cell':0}
    assert c.post(f'/api/mines/rooms/{code}/command',headers=ps[6][0],json=payload).status_code==403
    assert 'layout' not in m and 'mines' not in m and 'seed' not in m
