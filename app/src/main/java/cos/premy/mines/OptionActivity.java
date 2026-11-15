package cos.premy.mines;

import android.content.SharedPreferences;
import android.os.Bundle;
import android.widget.*;
import android.view.View;

public class OptionActivity extends LocalizedActivity {
    private SharedPreferences prefs;
    private LinearLayout column;
    private cos.premy.mines.updates.MenuUpdateHost updates;
    private String t(String zh,String en){return MineTheme.tr(this,zh,en);}
    @Override protected void onCreate(Bundle state){super.onCreate(state);prefs=getSharedPreferences(GameStatus.SETTINGS,0);
        ScrollView scroll=new ScrollView(this);scroll.setBackgroundColor(MineTheme.BACK);column=new LinearLayout(this);column.setOrientation(LinearLayout.VERTICAL);column.setPadding(dp(22),dp(20),dp(22),dp(28));scroll.addView(column);
        Button back=MineTheme.button(this,t("‹ 返回矿井大厅","‹ Back to the mine"),false);back.setOnClickListener(v->finish());add(back,0);
        add(MineTheme.text(this,t("声音与体验","Sound & experience"),27,MineTheme.INK),24);
        toggle(t("游戏音效与矿井环境声","Sound effects & ambience"),"sound",true);
        toggle(t("减弱闪光与震屏","Reduce flashes & screen shake"),"reducedEffects",false);
        add(MineTheme.text(this,t("经典 / 扫描棋盘","Classic / scan boards"),21,MineTheme.GOLD),25);
        toggle(t("高难度：1.5 倍地雷","Hard mode: 1.5× mines"),"hardcore",false);
        TextView layer=MineTheme.text(this,"",16,MineTheme.INK);add(layer,18);
        SeekBar slider=new SeekBar(this);slider.setMax(6);slider.setProgress(GameStatus.preferredLayers(this)-2);
        layer.setText(getString(R.string.selected_layer_count,slider.getProgress()+2));
        slider.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener(){public void onStartTrackingTouch(SeekBar b){}public void onStopTrackingTouch(SeekBar b){}public void onProgressChanged(SeekBar b,int n,boolean user){layer.setText(getString(R.string.selected_layer_count,n+2));if(user)prefs.edit().putInt("numLevels",n+2).apply();}});
        add(slider,12);
        add(MineTheme.text(this,t("线索显示","Clue display"),21,MineTheme.GOLD),25);
        toggle(t("用数字显示邻雷数","Number clues"),"numberType",true);
        toggle(t("用颜色辅助区分数字","Colour accents for clues"),"colored",false);
        toggle(t("自动展开零格（可跨层）","Expand zero cells across decks"),"flood",false);
        add(MineTheme.text(this,t("无猜与每日模式自动展开；撤离模式逐格开路。\n固定关卡不受棋盘尺寸和难度设置影响。","Logic and daily modes expand zero cells. Escape opens one cell at a time.\nFixed levels keep their own size and difficulty."),13,MineTheme.MUTED),16);
        add(MineTheme.text(this,t("字体 Noto Sans / Noto Sans SC · SIL OFL 1.1\n矿井模型、贴图与音效均保留原创可编辑源文件。","Noto Sans / Noto Sans SC · SIL OFL 1.1\nOriginal editable mine art, textures and sounds are included in the source."),12,MineTheme.MUTED),28);
        updates=new cos.premy.mines.updates.MenuUpdateHost(this,false);updates.addAboutControls(column);
        setContentView(scroll);SystemBarsPadding.apply(this);
    }
    @Override protected void onResume(){super.onResume();if(updates!=null)updates.resume();}
    @Override protected void onPause(){if(updates!=null)updates.pause();super.onPause();}
    @Override protected void onDestroy(){if(updates!=null)updates.close();super.onDestroy();}
    @Override public void onWindowFocusChanged(boolean focused){super.onWindowFocusChanged(focused);if(updates!=null)updates.focus(focused);}
    private void toggle(String label,String key,boolean value){Switch sw=new Switch(this);if("sound".equals(key))sw.setId(R.id.option_sound);if("reducedEffects".equals(key))sw.setId(R.id.option_reduced);sw.setText(label);sw.setTextColor(MineTheme.INK);sw.setTextSize(15);sw.setTypeface(MineTheme.font(this));sw.setMinHeight(dp(58));sw.setPadding(dp(12),dp(8),dp(12),dp(8));sw.setBackground(MineTheme.shape(this,MineTheme.PANEL,0xff293c4b,12));sw.setChecked(prefs.getBoolean(key,value));sw.setOnCheckedChangeListener((b,checked)->prefs.edit().putBoolean(key,checked).apply());add(sw,10);}
    private void add(View v,int top){LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.topMargin=dp(top);column.addView(v,p);}
    private int dp(int n){return MineTheme.dp(this,n);}
}


