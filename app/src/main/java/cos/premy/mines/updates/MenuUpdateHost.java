// SPDX-License-Identifier: GPL-3.0-only
package cos.premy.mines.updates;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.net.Uri;
import android.widget.*;
import cos.premy.mines.BuildConfig;
import cos.premy.mines.MineTheme;
import cos.premy.mines.R;

/** Owned only by the menu and settings. No game/lobby lifecycle is involved. */
public final class MenuUpdateHost implements HaokeUpdateUi.Host {
    private final Activity activity;
    private final boolean automatic;
    private final HaokeUpdateUi updates;
    private boolean resumed;
    public MenuUpdateHost(Activity activity, boolean automatic) {
        this.activity=activity; this.automatic=automatic;
        updates=BuildConfig.DEBUG ? null : new HaokeUpdateUi(activity,this);
    }
    public void resume(){resumed=true;if(updates!=null)updates.resume();}
    public void pause(){resumed=false;if(updates!=null)updates.pause();}
    public void close(){if(updates!=null)updates.close();}
    public void focus(boolean focused){if(focused&&resumed&&updates!=null)updates.refresh();}
    public boolean isSafeForUpdates(boolean manual){return resumed&&activity.hasWindowFocus()&&(automatic||manual);}
    public void onDialogShown(AlertDialog dialog){
        dialog.getWindow().getDecorView().setBackground(MineTheme.shape(activity,MineTheme.PANEL,0xff344857,16));
        MineTheme.fonts(dialog.getWindow().getDecorView());
        TextView message=dialog.findViewById(android.R.id.message);
        if(message!=null)message.setTextColor(MineTheme.INK);
        for(int id:new int[]{-1,-2,-3}){
            Button button=dialog.getButton(id);
            if(button!=null){button.setTextColor(MineTheme.GOLD);button.setMinHeight(MineTheme.dp(activity,48));}
        }
    }
    public void addAboutControls(LinearLayout parent){
        add(parent,MineTheme.text(activity,MineTheme.tr(activity,"关于与版本","About & updates"),21,MineTheme.GOLD),25);
        add(parent,MineTheme.text(activity,"Mines3D "+BuildConfig.VERSION_NAME,14,MineTheme.INK),12);
        add(parent,MineTheme.text(activity,MineTheme.tr(activity,
            "基于 Přemysl Šťastný 的 Mines3D，按 GPL-3.0-only 发布。浩科版增加立体矿井、原创声画及多人玩法。",
            "Based on Mines3D by Přemysl Šťastný, distributed under GPL-3.0-only. This Haoke edition adds a 3D mine, original audiovisual assets and multiplayer modes."),13,MineTheme.MUTED),10);
        add(parent,MineTheme.text(activity,activity.getString(R.string.updates_privacy),13,MineTheme.MUTED),10);
        Button check=MineTheme.button(activity,activity.getString(R.string.updates_check),false);
        check.setOnClickListener(v->{if(updates!=null)updates.manual();else Toast.makeText(activity,R.string.updates_unregistered,Toast.LENGTH_SHORT).show();});add(parent,check,12);
        link(parent,activity.getString(R.string.haoke_tools),"https://www.haoke.org/");
        link(parent,MineTheme.tr(activity,"对应源码与开源许可","Corresponding source & licence"),"https://www.haoke.org/software/491ec4cb67f1146b");
    }
    private void link(LinearLayout parent,String label,String url){
        Button button=MineTheme.button(activity,label,false);
        button.setOnClickListener(v->{try{activity.startActivity(new Intent(Intent.ACTION_VIEW,Uri.parse(url)));}
            catch(android.content.ActivityNotFoundException unavailable){Toast.makeText(activity,R.string.updates_browser_unavailable,Toast.LENGTH_SHORT).show();}});add(parent,button,8);
    }
    private void add(LinearLayout parent,android.view.View view,int gap){
        LinearLayout.LayoutParams params=new LinearLayout.LayoutParams(-1,-2);params.topMargin=MineTheme.dp(activity,gap);parent.addView(view,params);
    }
}
