"""Mines3D rules v1. Private truth never leaves project(); no network or database side effects.

Same six-neighbour topology as Android BoardDefinition. All timestamps are server seconds.
The persistence layer serializes commands and stores the complete state atomically.
"""
from collections import deque
from datetime import datetime, timezone, timedelta
import copy
import hashlib
import hmac
import random
import secrets

VERSION = 1
MODES = ('coop', 'hunt', 'puzzle', 'fault', 'daily', 'race', 'team')
ROLES = ('miner', 'scout', 'medic')
TURN_SECONDS = 15
GRACE = 60


class RuleError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def require(test, code):
    if not test:
        raise RuleError(code)


def neighbors(layout, cell):
    n, layers = layout['size'], layout['layers']
    if not 0 <= cell < n*n*layers or not layout['present'][cell]:
        return []
    x, y, z = cell % n, cell//n % n, cell//(n*n)
    out = []
    for dx, dy, dz in ((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1)):
        a,b,c=x+dx,y+dy,z+dz
        if 0<=a<n and 0<=b<n and 0<=c<layers:
            p=(c*n+b)*n+a
            if layout['present'][p]: out.append(p)
    return out


def route(layout, allowed, start=None, end=None):
    start = layout['start'] if start is None else start
    end = layout['exit'] if end is None else end
    allowed=set(allowed)
    if start not in allowed: return [], []
    previous={start:None}; queue=deque([start])
    while queue:
        p=queue.popleft()
        for q in neighbors(layout,p):
            if q in allowed and q not in previous:
                previous[q]=p;queue.append(q)
    path=[]
    if end in previous:
        p=end
        while p is not None:
            path.append(p);p=previous[p]
        path.reverse()
    return path, sorted(previous)


def deduction(layout, visible, flags=(), confirmed=()):
    """Public clues only. Flags are UI suggestions, never mathematical premises."""
    proven=set(confirmed); safe=set(); flagged=set(flags)
    for _ in range(len(visible)+1):
        constraints=[]
        for i,number in enumerate(visible):
            if number<0: continue
            near=set(neighbors(layout,i)); unknown={j for j in near if visible[j]==-1}
            left=number-len(near & proven)
            unknown-=proven|safe
            if left<0 or left>len(unknown): return None
            if unknown: constraints.append((frozenset(unknown),left,{i},False))
        unknown={i for i,v in enumerate(visible) if v==-1}-proven-safe
        left=layout['count']-len(proven)
        if unknown and 0<=left<=len(unknown): constraints.append((frozenset(unknown),left,set(),False))
        advanced=False
        for cells,left,sources,subset in constraints:
            if left==0 or left==len(cells):
                mine=left>0
                for cell in sorted(cells):
                    if not mine or cell not in flagged:
                        return {'cell':cell,'mine':mine,'sources':sorted(sources),
                                'remaining':left,'unknown':len(cells),'subset':subset}
                if mine: proven.update(cells);advanced=True
        if advanced: continue
        # Local constraints have at most six cells; bounded pairwise subset elimination.
        for a,an,sa,_ in constraints:
            for b,bn,sb,_ in constraints:
                if a<b:
                    cells=b-a;left=bn-an
                    if left==0 or left==len(cells):
                        mine=left>0
                        for cell in sorted(cells):
                            if not mine or cell not in flagged:
                                return {'cell':cell,'mine':mine,'sources':sorted(sa|sb),
                                        'remaining':left,'unknown':len(cells),'subset':True}
                        if mine: proven.update(cells);advanced=True
        if not advanced: return None
    return None


def verify_puzzle(layout):
    visible=[-1 if p else -2 for p in layout['present']]
    for i in layout['initial']:visible[i]=layout['clues'][i]
    flags=set(); mines=set(layout['mines'])
    for _ in range(len(visible)*2):
        hint=deduction(layout,visible,flags)
        if hint is None:return flags==mines
        if (hint['cell'] in mines)!=hint['mine']:raise AssertionError('Unsound public deduction')
        if hint['mine']:flags.add(hint['cell'])
        else:visible[hint['cell']]=layout['clues'][hint['cell']]
    return False


def java_shuffle(values, seed):
    """Exact java.util.Random / Collections.shuffle for the three verified solo puzzles."""
    state=(seed ^ 0x5DEECE66D)&((1<<48)-1)
    def next_int(bound):
        nonlocal state
        while True:
            state=(state*0x5DEECE66D+11)&((1<<48)-1);bits=state>>17
            if bound & (bound-1)==0:return (bound*bits)>>31
            value=bits%bound
            if bits-value+(bound-1)<(1<<31):return value
    for i in range(len(values),1,-1):
        j=next_int(i);values[i-1],values[j]=values[j],values[i-1]


def make_layout(settings, count, private_seed):
    mode=settings['mode']; level=settings.get('map',0)
    n=settings.get('size',5); layers=settings.get('layers',0) or max(3,count)
    difficulty=settings.get('difficulty',0)
    if mode=='puzzle':n=5;layers=2 if level==0 else 3
    length=n*n*layers
    layout={'size':n,'layers':layers,'present':[True]*length}
    shape=level if mode=='fault' else -1
    for i in range(length):
        x,y,z=i%n,i//n%n,i//(n*n)
        # Offset decks rotate around a missing core: neighbouring half-decks
        # overlap at alternating corners, with no shaft spanning all four decks.
        offset_hole=((z%4==0 and x>=n//2) or (z%4==1 and y>=n//2) or
                     (z%4==2 and x<=n//2) or (z%4==3 and y<=n//2))
        hole=(shape==0 and ((x<2 and y>=n-2) or (x>=n-2 and y<2))) or (shape==1 and x==n//2 and y==n//2) or (shape==2 and offset_hole) or (shape==3 and x==n//2 and (z!=layers//2 or y!=n//2))
        layout['present'][i]=not hole
    present={i for i,p in enumerate(layout['present']) if p}
    layout['start']=min(i for i in present if i>=n*n*(layers-1))
    layout['exit']=max(i for i in present if i<n*n)
    rng=random.Random(private_seed)
    previous={layout['start']:None};queue=deque([layout['start']])
    while queue:
        at=queue.popleft();near=neighbors(layout,at);rng.shuffle(near)
        for q in near:
            if q not in previous:previous[q]=at;queue.append(q)
    path=[];at=layout['exit']
    if at in previous:
        while at is not None:path.append(at);at=previous[at]
    require(bool(path),'INVALID_TOPOLOGY')
    excluded=set([layout['start']]+neighbors(layout,layout['start']))
    if mode not in ('hunt','puzzle'):excluded.update(path)
    candidates=sorted(present-excluded)
    if mode=='puzzle':
        seed=[1500,2500,3501][min(2,level)];java_shuffle(candidates,seed)
        total=[7,11,14][min(2,level)]
    else:
        rng.shuffle(candidates);total=max(7,int(len(present)*(.14+.04*difficulty)))
    total=min(total,len(candidates));mines=set(candidates[:total])
    layout['mines']=sorted(mines);layout['count']=total
    layout['clues']=[sum(q in mines for q in neighbors(layout,i)) if i in present else -2 for i in range(length)]
    layout['initial']=sorted(set([layout['start']]+neighbors(layout,layout['start']))-mines)
    layout['quests']={}
    quest_candidates=sorted(present-mines-set(layout['initial'])-set(path))
    rng.shuffle(quest_candidates)
    for j,cell in enumerate(quest_candidates[:max(2,count)]):layout['quests'][str(cell)]='miner' if j%3==0 else 'ore'
    if mode=='puzzle':require(verify_puzzle(layout),'PUZZLE_NOT_VERIFIED')
    return layout


def board_key(match, player):
    return str(player['team']) if match['mode']=='team' else player['id'] if match['mode']=='race' else 'shared'


def new_match(settings, players, match_id, now, secret):
    require(2<=len(players)<=6,'NOT_ENOUGH_PLAYERS')
    require(settings['mode']!='team' or len(players)==6,'TEAM_REQUIRES_SIX')
    day=datetime.fromtimestamp(now,timezone(timedelta(hours=8))).date().isoformat()
    if settings['mode']=='daily':
        identity=f"mines-v1/{day}/{len(players)}/{settings['difficulty']}/{settings['map']}/{settings['size']}/{settings['layers']}"
        seed=int.from_bytes(hmac.new(secret.encode(),identity.encode(),hashlib.sha256).digest(),'big')
    else:seed=secrets.randbits(128)
    layout=make_layout(settings,len(players),seed)
    if settings['mode']=='hunt':
        # A playable opening has a provable action from public clues, not an obligatory guess.
        for retry in range(64):
            visible=[layout['clues'][i] if i in layout['initial'] else -1 if p else -2 for i,p in enumerate(layout['present'])]
            if deduction(layout,visible):break
            layout=make_layout(settings,len(players),seed+retry+1)
        require(deduction(layout,visible) is not None,'OPENING_GENERATION_FAILED')
    match={'id':match_id,'rule_version':VERSION,'version':1,'seq':0,'events':[],
           'settings':dict(settings),'mode':settings['mode'],'day':day if settings['mode']=='daily' else '',
           'created':now,'ended':None,'winners':[],'reason':'','layout':layout,'players':[],
           'boards':{},'turn':0,'deadline':now+TURN_SECONDS,'target':min(3,layout['count']),
           'initial_players':len(players)}
    for i,p in enumerate(players):
        item={'id':p['id'],'name':p['name'],'avatar':p.get('avatar',0),'role':p.get('role','miner'),
              'team':i%2,'status':'active','left':False,'seen':now,'score':0,'opened':0,'route_cells':0,'rescues':0,
              'assists':0,'hints':0,'misses':0,'extra_scan':int(p.get('role')=='scout'),
              'extra_rescue':int(p.get('role')=='medic'),'finished':None}
        match['players'].append(item)
        key=board_key(match,item)
        if key not in match['boards']:
            match['boards'][key]={'opened':list(layout['initial']),'opened_by':{},'flags':{},'claimed':{},'scans':{},
                                  'safety':3,'scans_left':2,'rescues_left':max(1,(3 if match['mode']=='team' else len(players))-1),
                                  'collected':{},'marks':[],'failed':False}
    return match


def event(match, kind, now, **fields):
    match['seq']+=1
    match['events'].append({'id':match['seq'],'kind':kind,'at':now,**fields})
    match['events']=match['events'][-48:]


def finish(match, winners, reason, now):
    if match['ended'] is not None:return
    match.update(ended=now,winners=list(winners),reason=reason)
    event(match,'result',now,winners=list(winners),reason=reason)


def survivors(match):return [p for p in match['players'] if p['status']!='out' and not p['left']]


def next_turn(match, now):
    for _ in match['players']:
        match['turn']=(match['turn']+1)%len(match['players'])
        if match['players'][match['turn']]['status']=='active':break
    match['deadline']=now+TURN_SECONDS


def evaluate(match, now):
    if match['ended'] is not None:return
    mode=match['mode']; active=survivors(match); layout=match['layout'];mines=set(layout['mines'])
    if not active:finish(match,[],'no_survivors',now);return
    if mode=='hunt':
        reached=[p['id'] for p in active if p['score']>=match['target']]
        if reached:finish(match,reached,'target',now);return
        if len(active)==1:
            # A completely disconnected room has no awarded offline winner.
            if now-active[0]['seen']<=10:finish(match,[active[0]['id']],'last_survivor',now)
            return
        board=match['boards']['shared']
        exposed=set(map(int,board['claimed']))|set(board['opened'])
        if mines<=exposed:
            best=max(p['score'] for p in active);finish(match,[p['id'] for p in active if p['score']==best],'all_mines',now)
        return
    for key,board in match['boards'].items():
        team=[p for p in active if board_key(match,p)==key]
        _,connected=route(layout,set(board['opened'])-mines)
        for p in match['players']:
            if board_key(match,p)==key:p['route_cells']=sum(board.get('opened_by',{}).get(str(c))==p['id'] for c in connected)
        if board['safety']<=0 or not any(p['status']=='active' for p in team):
            board['failed']=True
            for p in team:p['status']='out'
            continue
        if mode=='puzzle':won=set(map(int,board['flags']))==mines
        else:won=bool(route(layout,set(board['opened'])-mines)[0])
        if won:
            winners=[p['id'] for p in team]
            for p in team:p['finished']=now
            finish(match,winners,'puzzle_complete' if mode=='puzzle' else 'escaped',now);return
    alive=survivors(match)
    if not alive:finish(match,[],'expedition_failed',now)
    elif mode in ('race','team'):
        groups={board_key(match,p) for p in alive}
        if len(groups)==1 and any(now-p['seen']<=10 for p in alive):finish(match,[p['id'] for p in alive],'last_team' if mode=='team' else 'last_survivor',now)


def tick(match, now):
    """Resolve elapsed deadlines in chronological order; restart does not grant fresh turns."""
    if match['ended'] is not None:return False
    old=(match['seq'],match['turn'])
    if all(now-p['seen']>GRACE for p in survivors(match)):
        for p in match['players']:p['status']='out'
        finish(match,[],'all_disconnected',now)
    else:
        for p in match['players']:
            if p['status']!='out' and now-p['seen']>GRACE:
                p['status']='out';p['left']=True;event(match,'disconnect',now,player=p['id'])
        evaluate(match,now)
    if match['mode']=='hunt':
        if match['ended'] is None and now<match['deadline'] and match['players'][match['turn']]['status']=='out':next_turn(match,now)
        for _ in range(24):
            if match['ended'] is not None or now<match['deadline']:break
            at=match['deadline'];p=match['players'][match['turn']]
            if p['status']=='active':
                p['misses']+=1
                if p['misses']>=3:p['status']='out'
                event(match,'timeout',at,player=p['id'],eliminated=p['status']=='out')
            evaluate(match,at);next_turn(match,at)
    changed=(match['seq'],match['turn'])!=old
    if changed:match['version']+=1
    return changed


def leave(match, uid, now):
    p=next((p for p in match['players'] if p['id']==uid),None)
    if not p or p['left']:return
    was_turn=match['players'][match['turn']]['id']==uid
    p['left']=True;p['status']='out';event(match,'leave',now,player=uid)
    evaluate(match,now)
    if was_turn and match['mode']=='hunt' and match['ended'] is None:next_turn(match,now)
    match['version']+=1


def apply(match, uid, action, cell, target, now):
    require(match['ended'] is None,'MATCH_FINISHED')
    player=next((p for p in match['players'] if p['id']==uid),None)
    require(player is not None and player['status']=='active' and not player['left'],'CANNOT_ACT')
    layout=match['layout'];board=match['boards'][board_key(match,player)];mode=match['mode']
    turn_action=action in ('open','confirm')
    if mode=='hunt':
        require(action in ('open','confirm'),'HUNT_ACTION_ONLY')
        require(match['players'][match['turn']]['id']==uid,'NOT_YOUR_TURN')
        require(now<match['deadline'],'TURN_EXPIRED')
    elif action=='confirm':raise RuleError('NOT_HUNT_MODE')
    if action in ('open','flag','confirm','scan','danger','safe','help'):
        require(type(cell) is int and 0<=cell<len(layout['present']) and layout['present'][cell],'INVALID_CELL')
    mines=set(layout['mines']);key=str(cell)
    if action=='open':
        require(cell not in board['opened'] and key not in board['flags'] and key not in board['claimed'],'CELL_CHANGED')
        board['opened'].append(cell)
        if cell in mines:
            player['status']='out' if mode in ('hunt','race') else 'down'
            board['safety']-=1
            event(match,'blast',now,player=uid,cell=cell,board=board_key(match,player))
        else:
            player['opened']+=1
            board.setdefault('opened_by',{})[key]=uid
            if key in layout['quests'] and mode!='hunt':board['collected'][key]=uid
            for mark in board['marks']:
                if mark['cell']==cell and mark['kind']=='safe' and mark['player']!=uid:
                    helper=next((p for p in match['players'] if p['id']==mark['player']),None)
                    if helper:helper['assists']+=1
            board['marks']=[m for m in board['marks'] if m['cell']!=cell]
            event(match,'open',now,player=uid,cell=cell,board=board_key(match,player))
    elif action=='confirm':
        require(cell not in board['opened'] and key not in board['claimed'],'CELL_CHANGED')
        if cell in mines:
            board['claimed'][key]=uid;player['score']+=1
            event(match,'claim',now,player=uid,cell=cell,board=board_key(match,player))
        else:
            player['status']='out';board['opened'].append(cell)
            event(match,'wrong_claim',now,player=uid,cell=cell)
    elif action=='flag':
        require(cell not in board['opened'],'CELL_CHANGED')
        if key in board['flags']:del board['flags'][key]
        else:board['flags'][key]=uid
        event(match,'flag',now,player=uid,cell=cell,board=board_key(match,player))
    elif action=='scan':
        require(cell in board['opened'] and cell not in mines and layout['clues'][cell]>0,'SCAN_NEEDS_NUMBER')
        if key not in board['scans']:
            require(board['scans_left']>0 or player['extra_scan']>0,'NO_SCANS')
            if board['scans_left']>0:board['scans_left']-=1
            else:player['extra_scan']-=1
            z=cell//(layout['size']**2);same=sum(q in mines and q//(layout['size']**2)==z for q in neighbors(layout,cell))
            board['scans'][key]=[same,layout['clues'][cell]-same]
        event(match,'scan',now,player=uid,cell=cell,board=board_key(match,player))
    elif action=='rescue':
        other=next((p for p in match['players'] if p['id']==target),None)
        require(other is not None and other['status']=='down' and board_key(match,other)==board_key(match,player),'INVALID_RESCUE')
        require(board['rescues_left']>0 or player['extra_rescue']>0,'NO_RESCUES')
        if board['rescues_left']>0:board['rescues_left']-=1
        else:player['extra_rescue']-=1
        other['status']='active';player['rescues']+=1
        event(match,'rescue',now,player=uid,target=target,board=board_key(match,player))
    elif action in ('danger','safe','help'):
        board['marks']=[m for m in board['marks'] if m['player']!=uid]
        board['marks'].append({'cell':cell,'kind':action,'player':uid,'at':now})
        event(match,'mark',now,player=uid,cell=cell,board=board_key(match,player))
    elif action=='hint':
        require(mode=='puzzle','HINT_PUZZLE_ONLY')
        exposed_mines=mines & set(board['opened'])
        visible=[layout['clues'][i] if i in board['opened'] and i not in mines else -1 if present else -2 for i,present in enumerate(layout['present'])]
        hint=deduction(layout,visible,set(map(int,board['flags']))|exposed_mines,exposed_mines)
        require(hint is not None,'NO_PROVABLE_HINT')
        board['hint']=hint;player['hints']+=1
        event(match,'hint',now,player=uid,board=board_key(match,player))
    else:raise RuleError('INVALID_ACTION')
    player['misses']=0
    if action in ('open','flag','confirm'):board.pop('hint',None)
    match['version']+=1
    evaluate(match,now)
    if mode=='hunt' and turn_action and match['ended'] is None:next_turn(match,now)


def project(match, uid, now, watch=None):
    """Explicit allowlist. Never return layout, mines, clues of closed cells, RNG or secrets."""
    player=next((p for p in match['players'] if p['id']==uid),None)
    if player:chosen=player
    else:chosen=next((p for p in match['players'] if p['id']==watch),match['players'][0])
    key=board_key(match,chosen);board=match['boards'][key];layout=match['layout']
    opened=set(board['opened']);mines=set(layout['mines']);cells=[]
    for i,present in enumerate(layout['present']):
        value=-2 if not present else 9 if i in opened and i in mines else layout['clues'][i] if i in opened else 8 if str(i) in board['flags'] or str(i) in board['claimed'] else 7
        cells.append(value)
    public_players=[]
    for p in match['players']:
        item={k:p[k] for k in ('id','name','avatar','role','team','status','left','score','opened','rescues','assists','hints','misses','extra_scan','extra_rescue','finished')}
        item['online']=now-p['seen']<10;public_players.append(item)
        item['route_cells']=p.get('route_cells',0)
    _,connected=route(layout,opened-mines)
    events=[dict(e) for e in match['events'] if 'board' not in e or e['board']==key]
    return {'id':match['id'],'rule_version':VERSION,'version':match['version'],'seq':match['seq'],
            'mode':match['mode'],'settings':dict(match['settings']),'day':match['day'],
            'created':match['created'],'ended':match['ended'],'winners':list(match['winners']),'reason':match['reason'],
            'server_now':now,'deadline':match['deadline'],'turn_player':match['players'][match['turn']]['id'],
            'target':match['target'],'players':public_players,'viewer':chosen['id'],'spectator':player is None or player['status']=='out',
            'size':layout['size'],'layers':layout['layers'],'mine_count':layout['count'],'start':layout['start'],'exit':layout['exit'],
            'cells':cells,'route':connected,'flags':dict(board['flags']),'claimed':dict(board['claimed']),
            'scans':copy.deepcopy(board['scans']),'safety':board['safety'],'scans_left':board['scans_left'],
            'rescues_left':board['rescues_left'],'collected':dict(board['collected']),
            'quest_total':len(layout['quests']),'quests':{k:layout['quests'][k] for k in board['collected']},
            'marks':copy.deepcopy(board['marks']),'hint':copy.deepcopy(board.get('hint')),'events':events}
