import time
from concurrent.futures import ThreadPoolExecutor
from test_platform import app,client,signin

PASSWORD='娴嬭瘯璐﹀彿 long password 185'

def challenge(c,email,purpose='password'):
    d=c.post('/api/auth/code',json={'email':email,'purpose':purpose}).json()
    code=c.get('/api/dev/mailbox',params={'challenge_id':d['challenge_id']}).json()['code']
    return {'challenge_id':d['challenge_id'],'code':code,'password':PASSWORD,'client':'web'}

def test_set_login_reset_revoke_and_no_secret_leak(app):
    first,user=signin(app,'pwd@example.com');native,_=signin(app,'pwd@example.com','native')
    assert first.get('/api/me').json()['user']['has_password'] is False
    c=client(app);body=challenge(c,'pwd@example.com')
    reset=c.post('/api/auth/password/reset',json=body)
    assert reset.status_code==200,reset.text
    assert first.get('/api/me').json()['user'] is None
    assert native.get('/api/me').json()['user'] is None
    assert c.get('/api/me').json()['user']['has_password'] is True
    assert c.post('/api/auth/password/reset',json=body).status_code==400
    n=client(app);good=n.post('/api/auth/password/login',json={'email':'PWD@example.com','password':PASSWORD,'client':'native'})
    assert good.status_code==200 and good.json()['access_token']
    n.headers['Authorization']='Bearer '+good.json()['access_token']
    assert n.get('/api/me').json()['user']['id']==user['id']
    with app.state.db.connect() as conn:
        stored=conn.execute('SELECT encoded FROM passwords').fetchone()[0]
        assert stored.startswith('scrypt-v1$') and PASSWORD not in stored
    assert stored not in c.get('/api/me').text and 'encoded' not in reset.text
    body=challenge(c,'pwd@example.com');body['password']='new password with spaces 185 '
    assert c.post('/api/auth/password/reset',json=body).status_code==200
    assert n.get('/api/me').json()['user'] is None
    assert client(app).post('/api/auth/password/login',json={'email':'pwd@example.com','password':PASSWORD}).status_code==400
    assert client(app).post('/api/auth/password/login',json={'email':'pwd@example.com','password':body['password'].strip()}).status_code==400
    assert client(app).post('/api/auth/password/login',json={'email':'pwd@example.com','password':body['password']}).status_code==200
    assert signin(app,'pwd@example.com')[1]['id']==user['id']

def test_password_challenges_are_scoped_and_expire(app):
    c,_=signin(app,'scoped@example.com')
    regular=challenge(c,'scoped@example.com','signin')
    assert c.post('/api/auth/password/reset',json=regular).status_code==400
    password=challenge(c,'scoped@example.com')
    assert c.post('/api/auth/verify',json={k:v for k,v in password.items() if k!='password'}).status_code==400
    wrong={**password,'code':'111111' if password['code']!='111111' else '222222'}
    for _ in range(5):assert c.post('/api/auth/password/reset',json=wrong).status_code==400
    assert c.post('/api/auth/password/reset',json=password).status_code==400
    expired=challenge(c,'scoped@example.com')
    with app.state.db.connect(write=True) as conn:conn.execute('UPDATE challenges SET expires_at=0 WHERE id=?',(expired['challenge_id'],))
    assert c.post('/api/auth/password/reset',json=expired).status_code==400
    unknown=challenge(c,'unregistered@example.com')
    assert c.post('/api/auth/password/reset',json=unknown).json()['error']['code']=='ACCOUNT_NOT_FOUND'
    with app.state.db.connect() as conn:assert conn.execute('SELECT count(*) FROM passwords').fetchone()[0]==0

def test_password_limits_disabled_account_and_atomic_reset(app):
    c,u=signin(app,'limit@example.com');body=challenge(c,'limit@example.com')
    for invalid in ('short',' '*10,'a\nvery-long-password','x'*129):
        assert c.post('/api/auth/password/reset',json={**body,'password':invalid}).status_code==422
    with ThreadPoolExecutor(2) as pool:
        codes=list(pool.map(lambda _:client(app).post('/api/auth/password/reset',json=body).status_code,range(2)))
    assert sorted(codes)==[200,400]
    for _ in range(8):
        assert client(app).post('/api/auth/password/login',json={'email':u['email'],'password':'incorrect'}).status_code==400
    assert client(app).post('/api/auth/password/login',json={'email':u['email'],'password':PASSWORD}).status_code==429
    # Proving mailbox ownership resets the password-login throttle and old sessions.
    assert c.post('/api/auth/password/reset',json=challenge(c,u['email'])).status_code==200
    with app.state.db.connect(write=True) as conn:conn.execute("UPDATE users SET status='suspended' WHERE id=?",(u['id'],))
    assert client(app).post('/api/auth/password/login',json={'email':u['email'],'password':PASSWORD}).status_code==400
    assert c.post('/api/auth/password/reset',json=challenge(c,u['email'])).status_code==400
