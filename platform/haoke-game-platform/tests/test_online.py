from contextlib import ExitStack
import time
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from backend.app import create_app
from backend.config import Settings

def account(c, n):
    challenge=c.post('/api/auth/code',json={'email':f'online{n}@example.com'}).json()['challenge_id']
    code=c.get('/api/dev/mailbox',params={'challenge_id':challenge}).json()['code']
    signed=c.post('/api/auth/verify',json={'challenge_id':challenge,'code':code,'client':'native'}).json()
    headers={'Authorization':'Bearer '+signed['access_token']}
    assert c.post('/api/online/enter',headers=headers,json={'protocol':30,'build':53}).status_code==200
    return headers,signed['user']['id']

@pytest.fixture
def live(tmp_path):
    app=create_app(Settings(data_dir=tmp_path,secret='online-test-only-secret-32-characters',otp_cooldown=0))
    with TestClient(app,client=('127.0.0.1',1234)) as c:
        yield c,app

def room(c, players):
    code=c.post('/api/rooms',headers=players[0][0],json={'game_id':'liquid-wars'}).json()['room']['code']
    for headers,_ in players[1:]:
        assert c.post(f'/api/rooms/{code}/join',headers=headers,json={'game_id':'liquid-wars'}).status_code==200
    for headers,_ in players:
        assert c.post(f'/api/rooms/{code}/ready',headers=headers,json={'ready':True}).status_code==200
    assert c.post(f'/api/rooms/{code}/start',headers=players[0][0]).status_code==200
    return code

def ticket(c,code,headers):
    r=c.post(f'/api/online/rooms/{code}/ticket',headers=headers)
    assert r.status_code==200,r.text
    return r.json()['ticket']

def test_six_native_seats_relay_and_emotes(live):
    c,app=live
    players=[account(c,n) for n in range(7)]
    code=room(c,players[:6])
    assert c.post(f'/api/rooms/{code}/join',headers=players[6][0],json={'game_id':'liquid-wars'}).status_code==410
    assert c.post(f'/api/online/rooms/{code}/ticket',headers=players[6][0]).status_code==403
    with ExitStack() as stack:
        host_ticket=ticket(c,code,players[0][0])
        host=stack.enter_context(c.websocket_connect('/ws/game?ticket='+host_ticket))
        assert host.receive_json()=={'type':'connected','slot':0}
        guests=[]
        for i in range(1,6):
            guest=stack.enter_context(c.websocket_connect('/ws/game?ticket='+ticket(c,code,players[i][0])))
            assert guest.receive_json()=={'type':'connected','slot':i}
            assert host.receive_json()=={'type':'join','slot':i}
            guests.append(guest)
            guest.send_bytes(b'\x08\x00\x00\x00\x82\x00\x00\x00\x1e')
            assert host.receive_bytes()==bytes([i])+b'\x08\x00\x00\x00\x82\x00\x00\x00\x1e'
            host.send_bytes(bytes([i,4,0,0,0,i]))
            assert guest.receive_bytes()==bytes([4,0,0,0,i])
        result=c.post(f'/api/online/rooms/{code}/battle-start',headers=players[0][0])
        assert result.status_code==200,result.text
        battle=result.json()['battle_id']
        assert c.post(f'/api/online/rooms/{code}/battle-start',headers=players[0][0]).json()['battle_id']==battle
        assert c.post(f'/api/rooms/{code}/emotes',headers=players[1][0],json={'emote_id':'hello'}).status_code==200
        assert c.post(f'/api/rooms/{code}/emotes',headers=players[1][0],json={'emote_id':'hello','text':'forbidden'}).status_code==422
        assert c.post(f'/api/online/rooms/{code}/battle-end',headers=players[0][0],json={'battle_id':battle}).status_code==200
        with pytest.raises(WebSocketDisconnect):
            with c.websocket_connect('/ws/game?ticket='+host_ticket):pass
        # Session revocation must also close the native relay immediately.
        assert c.post('/api/auth/logout',headers=players[5][0]).status_code==200
        with pytest.raises(WebSocketDisconnect):guests[4].receive_bytes()

def test_atomic_queue_cancel_expiry_and_native_gate(live):
    c,app=live
    players=[account(c,n) for n in range(6)]
    body={'game_id':'liquid-wars','protocol':30,'build':53,'mode':1}
    assert c.post('/api/matchmaking/enqueue',json=body).status_code==401
    assert c.post('/api/matchmaking/enqueue',headers=players[0][0],json={**body,'protocol':29}).status_code==409
    assert c.post('/api/matchmaking/enqueue',headers=players[0][0],json=body).json()['state']=='queued'
    assert c.post('/api/matchmaking/cancel',headers=players[0][0]).json()['state']=='idle'
    for headers,_ in players:
        c.post('/api/matchmaking/enqueue',headers=headers,json=body)
    states=[c.get('/api/matchmaking/status',headers=h).json() for h,_ in players]
    assert len({s['room']['id'] for s in states})==1
    assert all(s['room']['status']=='playing' and s['room']['mode']==1 and len(s['room']['members'])==6 for s in states)
    assert c.post('/api/matchmaking/cancel',headers=players[0][0]).json()['state']=='room'
    with app.state.db.connect() as conn:assert conn.execute('SELECT count(*) FROM match_queue').fetchone()[0]==0
    host=states[0]['room']['host_id'];host_h=next(h for h,u in players if u==host)
    code=states[0]['room']['code']
    assert c.post(f'/api/rooms/{code}/leave',headers=host_h).status_code==200
    for h,_ in players:assert c.get('/api/matchmaking/status',headers=h).json()['state']=='idle'
    c.post('/api/matchmaking/enqueue',headers=players[0][0],json=body)
    with app.state.db.connect(write=True) as conn:conn.execute('UPDATE match_queue SET last_seen=0')
    assert c.get('/api/matchmaking/status',headers=players[0][0]).json()['state']=='idle'

def test_protocol_isolation_and_restart(live):
    c,app=live
    players=[account(c,n) for n in range(2)]
    code=room(c,players)
    with app.state.db.connect(write=True) as conn:
        conn.execute('UPDATE native_clients SET protocol=29 WHERE user_id=?',(players[1][1],))
    assert c.post(f'/api/online/rooms/{code}/ticket',headers=players[0][0]).status_code==409
    # Opening the same persisted state in a new service ends non-resumable host sessions.
    fresh=create_app(app.state.config)
    with TestClient(fresh,client=('127.0.0.1',1234)) as restarted:
        state=restarted.get(f'/api/rooms/{code}',headers=players[0][0]).json()
        assert state['room']['status']=='closed' and state['room']['members']==[]

def test_solo_match_fills_computers_without_fake_accounts(live):
    c,app=live
    player=account(c,1)
    queued=c.post('/api/matchmaking/enqueue',headers=player[0],json={'protocol':30,'build':53,'mode':0}).json()
    assert queued['state']=='queued'
    with app.state.db.connect(write=True) as conn:conn.execute('UPDATE match_queue SET queued_at=?',(time.time()-9,))
    result=c.get('/api/matchmaking/status',headers=player[0]).json()
    assert result['state']=='room'
    assert result['room']['human_count']==1 and result['room']['computer_count']==5
    with app.state.db.connect() as conn:assert conn.execute('SELECT count(*) FROM users').fetchone()[0]==1
    code=result['room']['code']
    with c.websocket_connect('/ws/game?ticket='+ticket(c,code,player[0])) as host:
        assert host.receive_json()['slot']==0
        assert c.post(f'/api/online/rooms/{code}/battle-start',headers=player[0]).status_code==200
