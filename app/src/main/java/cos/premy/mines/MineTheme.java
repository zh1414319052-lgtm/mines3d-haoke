package cos.premy.mines;

import android.app.AlertDialog;
import android.content.Context;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;
import android.widget.Button;

/** Original mine UI. Noto Sans SC Medium, SIL OFL 1.1, bundled for commercial use. */
public final class MineTheme {
    public static final int BACK=0xff0b131c,PANEL=0xff142330,INK=0xffe8f0ee,MUTED=0xff9aafbd,GOLD=0xffedb56e,CYAN=0xff8ed7de;
    private static Typeface font;
    public static Typeface font(Context c){if(font==null)font=Typeface.createFromAsset(c.getAssets(),"mine/NotoSansSC-Medium.ttf");return font;}
    public static int dp(Context c,float n){return Math.round(n*c.getResources().getDisplayMetrics().density);}
    public static GradientDrawable shape(Context c,int color,int border,int radius){GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(dp(c,radius));d.setStroke(dp(c,1),border);return d;}
    public static TextView text(Context c,String value,float size,int color){TextView t=new TextView(c);t.setText(value);t.setTextSize(size);t.setTextColor(color);t.setTypeface(font(c));t.setIncludeFontPadding(false);return t;}
    public static Button button(Context c,String label,boolean primary){Button b=new Button(c);b.setText(label);b.setTypeface(font(c));b.setTextSize(15);b.setAllCaps(false);b.setTextColor(primary?BACK:INK);b.setMinHeight(dp(c,50));b.setMinimumHeight(dp(c,50));b.setPadding(dp(c,12),dp(c,8),dp(c,12),dp(c,8));b.setBackground(shape(c,primary?GOLD:PANEL,primary?GOLD:0xff344857,12));return b;}
    public static void fonts(View v){if(v instanceof TextView)((TextView)v).setTypeface(font(v.getContext()));if(v instanceof ViewGroup){ViewGroup g=(ViewGroup)v;for(int i=0;i<g.getChildCount();i++)fonts(g.getChildAt(i));}}
    public static void dialog(AlertDialog d){d.show();d.getWindow().setBackgroundDrawableResource(android.R.color.transparent);d.getWindow().getDecorView().setBackground(shape(d.getContext(),PANEL,0xff344857,16));fonts(d.getWindow().getDecorView());for(int id:new int[]{AlertDialog.BUTTON_POSITIVE,AlertDialog.BUTTON_NEGATIVE,AlertDialog.BUTTON_NEUTRAL})if(d.getButton(id)!=null)d.getButton(id).setTextColor(GOLD);}
    public static boolean zh(Context c){return "zh".equals(c.getResources().getConfiguration().locale.getLanguage());}
    public static String tr(Context c,String zh,String en){return zh(c)?zh:en;}
    public static String mode(Context c,String id){switch(id){case "escape":return tr(c,"矿井撤离","Mine escape");case "puzzle":return tr(c,"无猜解谜","Logic expedition");case "fault":return tr(c,"断层矿井","Faulted shafts");case "scan":return tr(c,"有限扫描","Limited scans");case "daily":return tr(c,"每日同图","Daily mine");default:return tr(c,"经典扫雷","Classic mines");}}
    public static String level(Context c,String mode,int n){
        if("escape".equals(mode))return tr(c,new String[]{"01 · 竖井初探","02 · 路线取舍","03 · 断层绕行"}[n],new String[]{"01 · First descent","02 · Descent choices","03 · Fault detour"}[n]);
        if("fault".equals(mode))return tr(c,new String[]{"缺角矿板","中央竖井","错层矿道"}[n],new String[]{"Cut corners","Central void","Offset decks"}[n]);
        return tr(c,new String[]{"01 · 相邻的线索","02 · 三层回声","03 · 交叉排除"}[n],new String[]{"01 · Neighbouring clues","02 · Three-deck echoes","03 · Elimination"}[n]);
    }
}


