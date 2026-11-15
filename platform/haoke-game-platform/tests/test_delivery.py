import json
import time
from backend.rooms import Hub
from test_platform import app, client, signin, write, game_data


def test_invitation_is_readonly_private_and_checks_game_full_expired(app):
    owner,_=signin(app,'invite@example.com')
    room=owner.post('/api/rooms',json={'game_id':'liquid-wars'}).json()['room']
    visitor=client(app)
    with app.state.db.connect() as conn:
        counts=[conn.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in ('users','members','profiles','events')]
    for _ in range(3):
        result=visitor.get('/api/invitations/'+room['code']+'?game_id=liquid-wars')
        assert result.status_code==200
        data=result.json()
        assert data['join_location']=='game' and data['member_count']==1
        assert 'members' not in data and 'host_id' not in data and 'email' not in data
    with app.state.db.connect() as conn:
        assert counts==[conn.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in ('users','members','profiles','events')]
    assert visitor.get('/api/invitations/'+room['code']+'?game_id=wrong').json()['error']['code']=='GAME_MISMATCH'
    for i in range(5):
        player,_=signin(app,f'invite-join{i}@example.com')
        player.post('/api/rooms/'+room['code']+'/join',json={'game_id':'liquid-wars'})
    assert visitor.get('/api/invitations/'+room['code']).json()['full'] is True
    with app.state.db.connect(write=True) as conn:
        conn.execute('UPDATE rooms SET expires_at=0 WHERE id=?',(room['id'],))
    assert visitor.get('/api/invitations/'+room['code']).status_code==410
    assert visitor.get('/api/invitations/UNKNOWN').status_code==404


def test_lab_gate_and_offline_api_reference(app):
    anonymous=client(app)
    assert anonymous.get('/api/admin/integration-lab').status_code==401
    player,_=signin(app,'not-admin@example.com')
    assert player.get('/api/admin/integration-lab').status_code==403
    admin,_=signin(app,'owner@haoke.local')
    assert admin.get('/api/admin/integration-lab').json()['enabled'] is True
    html=anonymous.get('/api/docs')
    assert html.status_code==200 and '/api-reference.js' in html.text
    assert 'cdn.' not in html.text
    schema=anonymous.get('/api/openapi.json').json()
    operation=schema['paths']['/api/admin/settings']['put']
    assert operation['security']
    assert any(p['name']=='Idempotency-Key' and p['required'] for p in operation['parameters'])
    assert 'security' not in schema['paths']['/api/invitations/{code}']['get']
    app.state.config.env='production'
    assert admin.get('/api/admin/integration-lab').status_code==404


def test_request_logs_include_denial_key_identity_and_no_secrets(app):
    anonymous=client(app)
    anonymous.get('/api/admin/settings')
    owner,_=signin(app,'owner@haoke.local')
    key=write(owner,'POST','/api/admin/keys',{'name':'request-audit','scope':'admin:read','expires_days':1}).json()
    ai=client(app);ai.headers['Authorization']='Bearer '+key['token']
    assert ai.get('/api/admin/stats').status_code==200
    settings=owner.get('/api/admin/settings').json()['settings']
    assert write(ai,'PUT','/api/admin/settings',settings).status_code==403
    write(owner,'POST','/api/admin/keys/'+key['key']['id']+'/revoke')
    assert ai.get('/api/admin/stats').status_code==401
    logs=owner.get('/api/admin/requests').json()['entries']
    assert any(r['actor']=='anonymous' and r['status']==401 for r in logs)
    assert {200,403,401}.issubset({r['status'] for r in logs if r['actor']=='key:'+key['key']['id']})
    assert key['token'] not in json.dumps(logs)


def test_account_lifecycle_revokes_realtime_and_publishes_host_transfer(app):
    class RecordingHub(Hub):
        def __init__(self):
            super().__init__();self.revoked=[];self.events=[]
        async def revoke_user(self,uid):self.revoked.append(uid)
        async def send(self,users,event):self.events.append((users,event))
    hub=RecordingHub();app.state.hub=hub
    admin,_=signin(app,'owner@haoke.local')
    host,u1=signin(app,'host-life@example.com');guest,u2=signin(app,'guest-life@example.com')
    room=host.post('/api/rooms',json={'game_id':'liquid-wars'}).json()['room']
    guest.post('/api/rooms/'+room['code']+'/join',json={'game_id':'liquid-wars'})
    result=write(admin,'PATCH','/api/admin/users/'+u1['id'],{'nickname':'paused','role':'user','status':'suspended'})
    assert result.status_code==200 and u1['id'] in hub.revoked
    users,event=hub.events[-1]
    assert u2['id'] in users and event['room']['host_id']==u2['id']
    assert len(event['room']['members'])==1
    guest.post('/api/realtime-ticket')
    recovered,_=signin(app,'guest-life@example.com',purpose='recovery')
    assert u2['id'] in hub.revoked and recovered.get('/api/me').json()['user']
    with app.state.db.connect() as conn:
        assert conn.execute('SELECT count(*) FROM ws_tickets WHERE user_id=?',(u2['id'],)).fetchone()[0]==0


def test_migration_and_game_trends_preserve_real_counts(app):
    admin,_=signin(app,'owner@haoke.local')
    write(admin,'POST','/api/admin/games',game_data('second-game'))
    player,user=signin(app,'trend@example.com')
    player.get('/api/games/liquid-wars');player.get('/api/games')
    assert player.get('/api/me').json()['profiles']==[]
    player.post('/api/games/second-game/enter')
    player.post('/api/games/second-game/enter')
    stats=admin.get('/api/admin/stats').json()
    games={g['id']:g for g in stats['games']}
    assert games['liquid-wars']['active_users']==0
    assert games['second-game']['active_users']==1
    assert sum(d['first_entries'] for d in games['second-game']['trend'])==1
    assert sum(d['active_users'] for d in games['second-game']['trend'])==1
    settings=admin.get('/api/admin/settings').json()['settings']
    settings['announcement']='Owner custom text must survive migrations'
    write(admin,'PUT','/api/admin/settings',settings)
    app.state.db.initialize()
    assert client(app).get('/api/config').json()['site']['announcement']==settings['announcement']
    with app.state.db.connect() as conn:
        assert [r[0] for r in conn.execute('SELECT version FROM migrations ORDER BY version')]==[1,2,3,4,5,6,7]
