package cos.premy.mines.graphics;

import android.app.AlertDialog;
import android.content.Context;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.Gravity;
import android.view.View;
import android.widget.*;
import cos.premy.mines.*;
import cos.premy.mines.data.MineCoord;
import cos.premy.mines.online.OnlineText;
import org.json.*;
import java.util.*;

/** Reuses the actual mine renderer/picker; accepts public cells only, never a MinesContainer. */
public final class OnlineBoardPanel extends LinearLayout {
    public interface Actions{void send(String action,int cell,String target);void menu();}
    private final Actions actions;private final String uid,mode;private final int size,layers;
    private final GameStatus status;private final MineSound sound;private PlayableViewport viewport;
    private final FrameLayout surface;private JSONObject state;private byte[] cells;
    private final TextView title,players,label,turn,resources,layerLabel,feedback;
    private final Button open,flag,tool,note,rescue;
    private int layer,selected=-1;private boolean focused=true,active,pending;private long version=-1;private String hiddenHint="";
    private long syncUptime;private double serverAtSync;private final HashMap<Integer,String> notes=new HashMap<>();
    private final Runnable ticker=new Runnable(){public void run(){refreshHud();if(active)postDelayed(this,250);}};
    public OnlineBoardPanel(Context c,JSONObject initial,String uid,Actions actions,Bundle saved)throws JSONException{
        super(c);this.actions=actions;this.uid=uid;state=initial;mode=initial.getString("mode");size=initial.getInt("size");layers=initial.getInt("layers");
        layer=saved==null?layers-1:Math.max(0,Math.min(layers-1,saved.getInt("online.layer",layers-1)));focused=saved==null||saved.getBoolean("online.focus",true);
        selected=saved==null?-1:saved.getInt("online.selected",-1);status=new GameStatus(c,layers,layer,0,0);sound=new MineSound(c);
        if(saved!=null){try{JSONObject n=new JSONObject(saved.getString("online.notes","{}"));Iterator<String> it=n.keys();while(it.hasNext()){String k=it.next();notes.put(Integer.parseInt(k),n.getString(k));}}catch(Exception ignored){}}
        setOrientation(VERTICAL);setBackgroundColor(MineTheme.BACK);
        LinearLayout head=column();head.setPadding(dp(12),dp(8),dp(12),dp(8));head.setBackgroundColor(MineTheme.PANEL);
        LinearLayout nameRow=row();title=text(OnlineText.mode(c,mode),16,MineTheme.GOLD);nameRow.addView(title,new LayoutParams(0,-2,1));Button menu=button("⋯",false);menu.setContentDescription(t("菜单与规则","Menu and rules"));menu.setOnClickListener(v->actions.menu());nameRow.addView(menu,new LayoutParams(dp(52),dp(48)));head.addView(nameRow);
        turn=text("",14,MineTheme.CYAN);head.addView(turn);players=text("",12,MineTheme.MUTED);players.setPadding(0,dp(5),0,dp(5));head.addView(players);
        feedback=text("",12,MineTheme.GOLD);feedback.setVisibility(GONE);head.addView(feedback);
        LinearLayout decks=row();Button up=button("‹",false),down=button("›",false);up.setContentDescription(t("上一层","Previous deck"));down.setContentDescription(t("下一层","Next deck"));layerLabel=text("",15,MineTheme.INK);layerLabel.setGravity(Gravity.CENTER);decks.addView(up,new LayoutParams(dp(52),dp(48)));decks.addView(layerLabel,new LayoutParams(0,dp(48),1));decks.addView(down,new LayoutParams(dp(52),dp(48)));head.addView(decks);
        up.setOnClickListener(v->changeLayer((layer+1)%layers));down.setOnClickListener(v->changeLayer((layer+layers-1)%layers));
        LinearLayout cameras=row();Button overview=button(t("全局视图","Overview"),false),focus=button(t("当前层","Current deck"),false),reset=button(t("复位","Reset"),false);weighted(cameras,overview);weighted(cameras,focus);weighted(cameras,reset);head.addView(cameras);
        overview.setOnClickListener(v->{focused=false;scene();});focus.setOnClickListener(v->{focused=true;scene();});reset.setOnClickListener(v->viewport.resetCamera());addView(head,new LayoutParams(-1,-2));
        surface=new FrameLayout(c);addView(surface,new LayoutParams(-1,0,1));
        viewport=new BoardViewport(c,this::select,this::fallback);viewport.setStatus(status);viewport.restoreCamera(saved);surface.addView(viewport.view(),new FrameLayout.LayoutParams(-1,-1));
        LinearLayout foot=column();foot.setBackgroundColor(MineTheme.PANEL);foot.setPadding(dp(10),dp(7),dp(10),dp(9));resources=text("",12,MineTheme.MUTED);foot.addView(resources);label=text(t("点选矿板后操作","Select a tile to act"),14,MineTheme.INK);label.setPadding(0,dp(7),0,dp(7));foot.addView(label);
        LinearLayout primary=row();open=button(t("开格","Open"),true);flag=button("hunt".equals(mode)?t("确认地雷","Confirm mine"):t("插旗","Flag"),false);weighted(primary,open);weighted(primary,flag);foot.addView(primary);
        LinearLayout secondary=row();tool=button("puzzle".equals(mode)?t("推理提示","Hint"):t("扫描","Scan"),false);note=button("hunt".equals(mode)?t("个人笔记","Notes"):t("协作标记","Mark"),false);rescue=button(t("救援队友","Rescue"),false);weighted(secondary,tool);weighted(secondary,note);weighted(secondary,rescue);foot.addView(secondary);addView(foot,new LayoutParams(-1,-2));
        open.setOnClickListener(v->send("open",null));flag.setOnClickListener(v->{
            if("hunt".equals(mode))MineTheme.dialog(new AlertDialog.Builder(c).setTitle(t("确认这格是地雷？","Confirm a mine here?")).setMessage(t("判断错误将立即淘汰。普通疑似标记请用个人笔记。","A wrong confirmation eliminates you. Use Notes for a tentative guess.")).setPositiveButton(t("确认地雷","Confirm mine"),(d,w)->send("confirm",null)).setNegativeButton(t("取消","Cancel"),null).create());
            else{String owner=state.optJSONObject("flags").optString(String.valueOf(selected),"");if(!owner.isEmpty()&&!owner.equals(uid))MineTheme.dialog(new AlertDialog.Builder(c).setMessage(t("取消队友放置的旗帜？","Remove your teammate's flag?")).setPositiveButton(t("取消该旗帜","Remove flag"),(d,w)->send("flag",null)).setNegativeButton(t("保留","Keep"),null).create());else send("flag",null);}
        });
        tool.setOnClickListener(v->{if("puzzle".equals(mode))hint();else{JSONObject scans=state.optJSONObject("scans");JSONArray split=scans==null?null:scans.optJSONArray(String.valueOf(selected));if(split!=null)showScan(split);else send("scan",null);}});
        note.setOnClickListener(v->mark());rescue.setOnClickListener(v->rescue());
        if(getResources().getConfiguration().orientation==android.content.res.Configuration.ORIENTATION_LANDSCAPE){
            removeAllViews();setOrientation(HORIZONTAL);LinearLayout rail=column();rail.addView(head);rail.addView(foot);ScrollView scroll=new ScrollView(c);scroll.addView(rail);addView(scroll,new LayoutParams(dp(300),-1));addView(surface,new LayoutParams(0,-1,1));
        }
        update(initial);postDelayed(()->{if(active&&state.optDouble("server_now")-state.optDouble("created")<8)sound.play("start");},500);
    }
    private void fallback(){Bundle saved=new Bundle();viewport.saveCamera(saved);if(viewport instanceof BoardViewport)((BoardViewport)viewport).onPause();surface.removeAllViews();viewport=new FlatBoardViewport(getContext(),this::select);viewport.setStatus(status);surface.addView(viewport.view(),new FrameLayout.LayoutParams(-1,-1));viewport.setInputActive(active);scene();}
    public void setActive(boolean value){active=value;removeCallbacks(ticker);if(value){status.resume();sound.resume(status.explosion);if(viewport instanceof BoardViewport)((BoardViewport)viewport).onResume();post(ticker);}else{status.explosion.finishNetworkEvent();status.pause();sound.pause();if(viewport instanceof BoardViewport)((BoardViewport)viewport).onPause();}viewport.setInputActive(value);}
    public void dispose(){setActive(false);sound.release();}
    public void pending(boolean value){pending=value;refreshHud();}
    public void save(Bundle out){viewport.saveCamera(out);out.putInt("online.layer",layer);out.putInt("online.selected",selected);out.putBoolean("online.focus",focused);JSONObject n=new JSONObject();for(Map.Entry<Integer,String> e:notes.entrySet())try{n.put(String.valueOf(e.getKey()),e.getValue());}catch(JSONException ignored){}out.putString("online.notes",n.toString());}
    public void update(JSONObject value)throws JSONException{
        String previousTurn=state==null?"":state.optString("turn_player");
        state=value;syncUptime=SystemClock.elapsedRealtime();serverAtSync=value.getDouble("server_now");
        if(active&&"hunt".equals(mode)&&uid.equals(value.optString("turn_player"))&&!uid.equals(previousTurn))sound.play("turn");
        long incoming=value.getLong("version");if(incoming!=version){JSONArray values=value.getJSONArray("cells");if(values.length()!=size*size*layers)throw new JSONException("Invalid public board size");cells=new byte[values.length()];for(int i=0;i<cells.length;i++){int v=values.getInt(i);if(v!=-2&&(v<0||v>9))throw new JSONException("Invalid public cell");cells[i]=(byte)(v==-2?BoardScene.VOID:v);}version=incoming;scene();}
        JSONObject nextHint=value.optJSONObject("hint");String hintKey=nextHint==null?"":nextHint.toString();
        if(!hintKey.equals(hiddenHint)){hiddenHint=hintKey;if(nextHint!=null){JSONArray sources=nextHint.optJSONArray("sources");jump(sources!=null&&sources.length()>0?sources.optInt(0):nextHint.optInt("cell"));}}
        refreshHud();
    }
    public void event(JSONObject event){String kind=event.optString("kind");
        if("blast".equals(kind)||"wrong_claim".equals(kind)){
            int hit=event.optInt("cell",-1);feedback.setText(name(event.optString("player"))+" · "+("blast".equals(kind)?t("踩雷","Mine hit"):t("错判淘汰","Wrong claim"))+" · B"+(layers-hit/(size*size))+t("（点击定位）"," (tap to locate)"));feedback.setVisibility(VISIBLE);feedback.setOnClickListener(v->jump(hit));
        }
        if("blast".equals(kind)){int cell=event.optInt("cell",-1);long age=(long)((state.optDouble("server_now")-event.optDouble("at"))*1000);if(cell>=0&&age>=0&&age<1500){status.explosion.networkEvent(coord(cell),age);status.explosion.active(active);sound.networkBlast(status.explosion);scene();viewport.effectChanged();}}
        else if("open".equals(kind))sound.play("open");else if("claim".equals(kind)||"flag".equals(kind))sound.play("flag");else if("rescue".equals(kind))sound.play("rescue");else if("result".equals(kind)){boolean won=false;JSONArray winners=state.optJSONArray("winners");for(int i=0;i<winners.length();i++)won|=uid.equals(winners.optString(i));sound.play(won?"win":"lose");}else if("wrong_claim".equals(kind)||"timeout".equals(kind))sound.play("eliminated");
        if("hint".equals(kind)){JSONObject h=state.optJSONObject("hint");if(h!=null){JSONArray sources=h.optJSONArray("sources");jump(sources!=null&&sources.length()>0?sources.optInt(0):h.optInt("cell"));feedback.setText(t("相关线索已高亮，再点“推理提示”查看解释。","Evidence highlighted. Tap Hint again for the explanation."));feedback.setVisibility(VISIBLE);feedback.setOnClickListener(v->hint());}}
        if("scan".equals(kind)&&uid.equals(event.optString("player"))){JSONArray split=state.optJSONObject("scans").optJSONArray(String.valueOf(event.optInt("cell")));if(split!=null)showScan(split);}
    }
    private JSONObject me(){JSONArray p=state.optJSONArray("players");if(p!=null)for(int i=0;i<p.length();i++)if(uid.equals(p.optJSONObject(i).optString("id")))return p.optJSONObject(i);return new JSONObject();}
    private boolean canAct(){JSONObject p=me();return active&&!pending&&state.isNull("ended")&&"active".equals(p.optString("status"))&&!p.optBoolean("left")&&(!"hunt".equals(mode)||uid.equals(state.optString("turn_player")));}
    private void select(MineCoord c){if(c==null||c.z!=layer)return;selected=(c.z*size+c.y)*size+c.x;sound.play("select");scene();refreshHud();}
    private MineCoord coord(int id){return new MineCoord(id%size,id/size%size,id/(size*size));}
    private void changeLayer(int next){layer=next;selected=-1;status.setLevel(layer);sound.play("layer");scene();refreshHud();}
    private void scene(){if(cells==null)return;BitSet connected=new BitSet();if(!"hunt".equals(mode)&&!"puzzle".equals(mode)){JSONArray list=state.optJSONArray("route");if(list!=null)for(int i=0;i<list.length();i++)connected.set(list.optInt(i));}
        BoardScene s=BoardScene.online(size,layers,layer,focused,selected,cells,connected);s.entry=state.optInt("start");s.exit=state.optInt("exit");
        if(status.explosion.cell!=null){MineCoord c=status.explosion.cell;s.blastCell=(c.z*size+c.y)*size+c.x;}
        JSONObject hint=state.optJSONObject("hint");if(hint!=null){s.hintTarget=hint.optInt("cell",-1);JSONArray source=hint.optJSONArray("sources");if(source!=null)for(int i=0;i<source.length();i++)s.hintSources.set(source.optInt(i));}
        for(Integer cell:notes.keySet())s.hintSources.set(cell);
        JSONArray marks=state.optJSONArray("marks");if(marks!=null)for(int i=0;i<marks.length();i++)s.hintSources.set(marks.optJSONObject(i).optInt("cell"));
        JSONArray ps=state.optJSONArray("players");JSONObject flags=state.optJSONObject("flags"),claims=state.optJSONObject("claimed");
        for(int p=0;p<ps.length();p++){String id=ps.optJSONObject(p).optString("id");for(JSONObject owners:new JSONObject[]{flags,claims}){Iterator<String> keys=owners.keys();while(keys.hasNext()){String key=keys.next();if(id.equals(owners.optString(key)))s.owners.put(Integer.parseInt(key),p);}}}
        viewport.setScene(s);
    }
    private void refreshHud(){if(state==null||cells==null)return;JSONObject me=me();StringBuilder names=new StringBuilder();JSONArray ps=state.optJSONArray("players");
        for(int i=0;i<ps.length();i++){JSONObject p=ps.optJSONObject(i);if(i>0)names.append(i%3==0?'\n':' ');names.append("team".equals(mode)?"T"+(p.optInt("team")+1)+"/":"").append(i+1).append("·").append(p.optString("name")).append(uid.equals(p.optString("id"))?t("(我)","(you)"):"").append(" ").append(p.optInt("score"));if(!p.optBoolean("online"))names.append(t("[离线]","[offline]"));else if(!"active".equals(p.optString("status")))names.append("[").append(OnlineText.status(getContext(),p.optString("status"))).append("]");}
        android.text.SpannableString colored=new android.text.SpannableString(names);int offset=0;
        for(int i=0;i<ps.length();i++){String marker=(i+1)+"·"+ps.optJSONObject(i).optString("name");int at=names.indexOf(marker,offset);if(at>=0){float[] color=BoardScene.PLAYER_COLORS[i%6];colored.setSpan(new android.text.style.ForegroundColorSpan(android.graphics.Color.rgb((int)(color[0]*255),(int)(color[1]*255),(int)(color[2]*255))),at,at+marker.length(),0);offset=at+marker.length();}}
        players.setText(colored);players.setOnClickListener(v->teamDetails());layerLabel.setText("B"+(layers-layer)+" / "+layers+t(" 层"," decks"));
        if(!state.isNull("ended"))turn.setText(t("对局已结束 · 查看菜单结算","Match ended · Open menu for results"));
        else if("hunt".equals(mode)){double now=serverAtSync+(SystemClock.elapsedRealtime()-syncUptime)/1000.0;turn.setText((uid.equals(state.optString("turn_player"))?t("轮到你","Your turn"):name(state.optString("turn_player"))+t(" 的回合","'s turn"))+" · "+Math.max(0,(int)Math.ceil(state.optDouble("deadline")-now))+"s");}
        else turn.setText(me.length()==0?t("观战中","Spectating"):("team".equals(mode)?t("队伍 ","Team ")+(me.optInt("team")+1)+" · ":"")+OnlineText.role(getContext(),me.optString("role"))+" · "+OnlineText.status(getContext(),me.optString("status")));
        resources.setText("hunt".equals(mode)?t("目标：确认 ","Target: ")+state.optInt("target")+t(" 颗雷 · 错判淘汰"," mines · Wrong claim eliminates"):
                t("安全 ","Stability ")+state.optInt("safety")+"/3  · "+t("扫描 ","Scans ")+(state.optInt("scans_left")+me.optInt("extra_scan"))+"  · "+t("救援 ","Rescues ")+(state.optInt("rescues_left")+me.optInt("extra_rescue"))+"  · "+t("支线 ","Finds ")+state.optJSONObject("collected").length()+"/"+state.optInt("quest_total"));
        resources.append(t("\n全图地雷 ","\nTotal mines ")+state.optInt("mine_count")+t(" · 已标记 "," · Marked ")+(state.optJSONObject("flags").length()+state.optJSONObject("claimed").length()));
        int cell=selected>=0&&selected<cells.length?cells[selected]:-1;boolean act=canAct();open.setEnabled(act&&cell==7);flag.setEnabled(act&&(cell==7||cell==8&&!"hunt".equals(mode)));tool.setEnabled(act&&("puzzle".equals(mode)||cell>0&&cell<7));note.setEnabled(me.length()>0&&selected>=0&&state.isNull("ended")&&!me.optString("status").equals("out"));rescue.setEnabled(act&&!"hunt".equals(mode)&&!"race".equals(mode));
        if(!"hunt".equals(mode))flag.setText(cell==8?t("取消旗帜","Remove flag"):t("插旗","Flag"));
        if(selected<0)label.setText(pending?t("正在确认操作…","Confirming move…"):t("点选矿板后操作","Select a tile to act"));
        else{String value=cell==7?t("未开格","Closed"):cell==8?t("已标记","Flagged"):cell==9?t("爆点","Blast site"):t("数字 ","Clue ")+cell;String owner=state.optJSONObject("claimed").optString(String.valueOf(selected),state.optJSONObject("flags").optString(String.valueOf(selected),""));JSONObject quests=state.optJSONObject("quests");String quest=quests==null?"":quests.optString(String.valueOf(selected));if(!quest.isEmpty())value+= " · "+("miner".equals(quest)?t("矿工已获救","Miner rescued"):t("矿石已收集","Ore collected"));label.setText("B"+(layers-layer)+" · R"+(selected/size%size+1)+" C"+(selected%size+1)+" · "+value+(owner.isEmpty()?"":" · "+name(owner))+(notes.containsKey(selected)?" · "+notes.get(selected):""));}
    }
    private String name(String id){JSONArray p=state.optJSONArray("players");for(int i=0;i<p.length();i++)if(id.equals(p.optJSONObject(i).optString("id")))return p.optJSONObject(i).optString("name");return t("队友","Player");}
    private void send(String action,String target){if(canAct())actions.send(action,selected,target);}
    private void showScan(JSONArray split){MineTheme.dialog(new AlertDialog.Builder(getContext()).setTitle(t("扫描结果","Scan result")).setMessage(t("本层雷数：","This deck: ")+split.optInt(0)+t("\n相邻层雷数：","\nAdjacent decks: ")+split.optInt(1)).setPositiveButton(t("知道了","OK"),null).create());}
    private void hint(){JSONObject h=state.optJSONObject("hint");if(h==null){send("hint",null);return;}String message=h.optInt("unknown")+t(" 个候选格中还有 "," candidates contain ")+h.optInt("remaining")+t(" 个雷。\n"," mines.\n")+(h.optBoolean("subset")?t("依据相关数字相减排除。\n","Subtract the highlighted constraints.\n"):"")+(h.optBoolean("mine")?t("结论格必须是雷。","The target must be a mine."):t("结论格必定安全。","The target must be safe."));MineTheme.dialog(new AlertDialog.Builder(getContext()).setTitle(t("公开线索推理","Public-clue reasoning")).setMessage(message).setPositiveButton(t("定位结论格","Locate"),(d,w)->jump(h.optInt("cell"))).setNeutralButton(t("新提示","New hint"),(d,w)->send("hint",null)).setNegativeButton(t("关闭","Close"),null).create());}
    private void mark(){if(selected<0)return;String[] labels={t("疑似有雷","Suspected mine"),t("这里可尝试","Try here"),t("需要支援","Need help"),t("查看队友标记","Team markers")};MineTheme.dialog(new AlertDialog.Builder(getContext()).setTitle(t("格子标记","Tile markers")).setItems(labels,(d,w)->{if(w==3){JSONArray marks=state.optJSONArray("marks");String[] items=new String[marks.length()];for(int i=0;i<items.length;i++){JSONObject m=marks.optJSONObject(i);int id=m.optInt("cell");items[i]=name(m.optString("player"))+" · B"+(layers-id/(size*size))+" · "+("danger".equals(m.optString("kind"))?t("疑似有雷","Suspected mine"):"safe".equals(m.optString("kind"))?t("这里可尝试","Try here"):t("需要支援","Need help"));}MineTheme.dialog(new AlertDialog.Builder(getContext()).setItems(items,(a,b)->jump(marks.optJSONObject(b).optInt("cell"))).create());}else if("hunt".equals(mode)){if(notes.containsKey(selected))notes.remove(selected);else notes.put(selected,labels[w]);scene();refreshHud();}else send(new String[]{"danger","safe","help"}[w],null);}).create());}
    private void rescue(){JSONArray ps=state.optJSONArray("players");List<String> ids=new ArrayList<>(),names=new ArrayList<>();for(int i=0;i<ps.length();i++){JSONObject p=ps.optJSONObject(i);if("down".equals(p.optString("status"))&&(!"team".equals(mode)||p.optInt("team")==me().optInt("team"))){ids.add(p.optString("id"));names.add(p.optString("name"));}}if(ids.isEmpty()){Toast.makeText(getContext(),t("没有需要救援的队友","No teammate needs a rescue"),Toast.LENGTH_SHORT).show();return;}MineTheme.dialog(new AlertDialog.Builder(getContext()).setTitle(t("救援队友","Rescue teammate")).setItems(names.toArray(new String[0]),(d,w)->send("rescue",ids.get(w))).create());}
    private void teamDetails(){StringBuilder b=new StringBuilder();JSONArray ps=state.optJSONArray("players");for(int i=0;i<ps.length();i++){JSONObject p=ps.optJSONObject(i);b.append(i+1).append(" · ").append(p.optString("name")).append(" · ").append(OnlineText.role(getContext(),p.optString("role"))).append("\n").append(t("开格 ","Opened ")).append(p.optInt("opened")).append(t(" · 协助 "," · Assists ")).append(p.optInt("assists")).append(t(" · 救援 "," · Rescues ")).append(p.optInt("rescues")).append("\n\n");}MineTheme.dialog(new AlertDialog.Builder(getContext()).setTitle(t("队员与贡献","Crew and contributions")).setMessage(b).setPositiveButton(t("关闭","Close"),null).create());}
    private void jump(int id){if(id<0||id>=cells.length)return;layer=id/(size*size);status.setLevel(layer);selected=id;focused=true;scene();refreshHud();}
    private String t(String zh,String en){return OnlineText.tr(getContext(),zh,en);}private int dp(int n){return MineTheme.dp(getContext(),n);}
    private TextView text(String s,int size,int color){return MineTheme.text(getContext(),s,size,color);}private Button button(String s,boolean primary){Button b=MineTheme.button(getContext(),s,primary);b.setTextSize(13);b.setMinWidth(0);b.setMinimumWidth(0);return b;}
    private LinearLayout column(){LinearLayout l=new LinearLayout(getContext());l.setOrientation(VERTICAL);return l;}private LinearLayout row(){LinearLayout l=new LinearLayout(getContext());l.setGravity(Gravity.CENTER_VERTICAL);return l;}
    private void weighted(LinearLayout row,View v){LayoutParams p=new LayoutParams(0,dp(48),1);p.setMargins(dp(2),dp(3),dp(2),0);row.addView(v,p);}
}
