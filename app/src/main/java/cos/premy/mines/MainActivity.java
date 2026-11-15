package cos.premy.mines;

import android.app.AlertDialog;
import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.*;
import cos.premy.mines.data.BoardDefinition;
import cos.premy.mines.graphics.GameActivity;

public class MainActivity extends LocalizedActivity {
    private LinearLayout column;
    private cos.premy.mines.updates.MenuUpdateHost updates;
    @Override protected void onCreate(Bundle state){super.onCreate(state);build();
        if(state==null&&getIntent().getBooleanExtra("showcase",false)&&(getApplicationInfo().flags&android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE)!=0)
            startActivity(GameActivity.newIntent(this,5,2,8).putExtra("showcase",true));
    }
    @Override protected void onResume(){super.onResume();build();if(updates==null)updates=new cos.premy.mines.updates.MenuUpdateHost(this,true);updates.resume();}
    @Override protected void onPause(){if(updates!=null)updates.pause();super.onPause();}
    @Override protected void onDestroy(){if(updates!=null)updates.close();super.onDestroy();}
    @Override public void onWindowFocusChanged(boolean focused){super.onWindowFocusChanged(focused);if(updates!=null)updates.focus(focused);}
    private String t(String zh,String en){return MineTheme.tr(this,zh,en);}
    private void build(){
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);scroll.setBackgroundColor(MineTheme.BACK);
        column=new LinearLayout(this);column.setOrientation(LinearLayout.VERTICAL);column.setPadding(dp(22),dp(24),dp(22),dp(28));scroll.addView(column);
        add(MineTheme.text(this,"DEEP SECTOR  /  MINES 3D",11,MineTheme.GOLD),0);
        add(MineTheme.text(this,t("三维扫雷","Mines 3D"),32,MineTheme.INK),8);
        add(MineTheme.text(this,t("深入矿井，让每一层线索彼此照亮。","Read the clues. Find your way through the depths."),14,MineTheme.MUTED),10);
        LinearLayout hero=new LinearLayout(this);hero.setOrientation(LinearLayout.VERTICAL);hero.setPadding(dp(17),dp(18),dp(17),dp(18));hero.setBackground(MineTheme.shape(this,MineTheme.PANEL,0xff365063,18));
        hero.addView(MineTheme.text(this,t("探索前须知","FIELD NOTES"),13,MineTheme.GOLD));
        TextView note=MineTheme.text(this,t("上下左右 + 相邻上下层\n每格最多 6 个邻格，线索可以跨层推理。","Four neighbours on your deck + one above and below.\nUp to six neighbours; every layer matters."),14,MineTheme.INK);note.setPadding(0,dp(10),0,0);hero.addView(note);add(hero,22);
        Bundle saved=SessionStore.read(this);
        Button online=MineTheme.button(this,t("联机探矿 · 2–6 人","Online expedition · 2–6 players"),true);
        online.setOnClickListener(v->startActivity(new Intent(this,cos.premy.mines.online.OnlineActivity.class)));add(online,18);
        if(saved!=null){Button resume=MineTheme.button(this,t("继续上次对局","Continue expedition"),true);resume.setId(R.id.resume_game);resume.setOnClickListener(v->startActivity(new Intent(this,GameActivity.class).putExtra("resumeSession",true)));add(resume,18);}
        card("classic",t("熟悉的规则，全新的立体矿井。","The original rules, with a new sense of depth."),()->chooseSize("classic"));
        card("escape",t("打开安全路线，从入口抵达最底层出口。","Connect the entrance to the deepest exit."),()->chooseLevel("escape"));
        card("puzzle",t("三组经过推理验证的固定关卡。","Three verified puzzles. Every move has a reason."),()->chooseLevel("puzzle"));
        card("fault",t("缺角、空洞与错层，重新认识邻接。","Missing corners, hollow shafts and offset decks."),()->chooseLevel("fault"));
        card("scan",t("只有两次扫描，将线索拆成本层与跨层。","Two scans split a clue into this deck and adjacent decks."),()->chooseSize("scan"));
        card("daily",t("每天同一矿井，重试仍是同一局面。","One mine each day. Retry the same arrangement."),this::daily);
        LinearLayout foot=new LinearLayout(this);Button settings=MineTheme.button(this,t("声音与设置","Settings"),false),help=MineTheme.button(this,t("操作说明","How to play"),false);
        settings.setOnClickListener(v->startActivity(new Intent(this,OptionActivity.class)));help.setOnClickListener(v->MineTheme.dialog(new AlertDialog.Builder(this).setTitle(R.string.how_to_play).setMessage(R.string.how_to_play_3d).setPositiveButton(R.string.close_dialog,null).create()));
        foot.addView(settings,new LinearLayout.LayoutParams(0,-2,1));LinearLayout.LayoutParams hp=new LinearLayout.LayoutParams(0,-2,1);hp.leftMargin=dp(8);foot.addView(help,hp);add(foot,22);
        add(MineTheme.text(this,(BuildConfig.DEBUG?"QA · ":"")+BuildConfig.VERSION_NAME+" · "+t("单机与联网独立存档","SEPARATE SOLO AND ONLINE PROGRESS"),11,MineTheme.MUTED),18);
        setContentView(scroll);SystemBarsPadding.apply(this);
    }
    private void card(String mode,String subtitle,Runnable action){LinearLayout card=new LinearLayout(this);card.setOrientation(LinearLayout.VERTICAL);card.setPadding(dp(17),dp(16),dp(17),dp(16));card.setBackground(MineTheme.shape(this,MineTheme.PANEL,0xff293c4b,14));card.addView(MineTheme.text(this,MineTheme.mode(this,mode)+"  ›",19,"classic".equals(mode)?MineTheme.GOLD:MineTheme.INK));TextView description=MineTheme.text(this,subtitle,13,MineTheme.MUTED);description.setPadding(0,dp(7),0,0);card.addView(description);card.setContentDescription(MineTheme.mode(this,mode));card.setOnClickListener(v->action.run());add(card,12);}
    private void chooseSize(String mode){String[] sizes={"5 × 5","8 × 8","10 × 10","12 × 12","15 × 15"};MineTheme.dialog(new AlertDialog.Builder(this).setTitle(MineTheme.mode(this,mode)).setItems(sizes,(d,i)->{int layers=GameStatus.preferredLayers(this);boolean hard=getSharedPreferences(GameStatus.SETTINGS,0).getBoolean("hardcore",false);int mines=(int)(new int[]{7,16,25,50,90}[i]*(hard?1.5f:1)*layers/2);launch(GameSetup.create(mode,new int[]{5,8,10,12,15}[i],layers,mines,0));}).setNegativeButton(R.string.close_dialog,null).create());}
    private void chooseLevel(String mode){String[] choices=new String[3];for(int i=0;i<3;i++){boolean won=getSharedPreferences("mine-records",0).getBoolean(mode+"."+i,false);choices[i]=(won?"✓  ":"")+MineTheme.level(this,mode,i);}MineTheme.dialog(new AlertDialog.Builder(this).setTitle(MineTheme.mode(this,mode)).setItems(choices,(d,i)->launch(GameSetup.create(mode,5,2,7,i))).setNegativeButton(R.string.close_dialog,null).create());}
    private void launch(BoardDefinition definition){startActivity(GameActivity.newIntent(this,definition));}
    private void daily(){BoardDefinition d=GameSetup.create("daily",5,3,10,0);android.content.SharedPreferences p=getSharedPreferences(GameSetup.recordKey(d),0);String stats=t("本地日期：","Local date: ")+d.day+t("\n固定安全起点 · 当天重试保持同图","\nFixed safe start · Same board on every retry");if(p.contains("lastElapsed"))stats+=t("\n\n上次用时：","\n\nLast time: ")+String.format(java.util.Locale.ROOT,"%.1f s",p.getLong("lastElapsed",0)/1000.0)+t("\n误标：","\nIncorrect flags: ")+p.getInt("lastWrongFlags",0)+t(" · 提示："," · Hints: ")+p.getInt("lastHints",0)+t("\n最佳通关：","\nBest win: ")+(p.getFloat("lowestTime",-1)<0?"—":String.format(java.util.Locale.ROOT,"%.1f s",p.getFloat("lowestTime",0)));MineTheme.dialog(new AlertDialog.Builder(this).setTitle(MineTheme.mode(this,"daily")).setMessage(stats).setPositiveButton(t("进入今日矿井","Enter today's mine"),(dialog,which)->launch(d)).setNegativeButton(R.string.close_dialog,null).create());}
    private int dp(int n){return MineTheme.dp(this,n);}
    private void add(View v,int top){LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.topMargin=dp(top);column.addView(v,p);}
}

