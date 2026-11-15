package cos.premy.mines;

import android.os.Bundle;
import cos.premy.mines.data.BoardDefinition;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;

/** Definition serialization is shared by launch, retry, task recreation and local Continue. */
public final class GameSetup {
    public static String recordKey(BoardDefinition d){return "cos.premy.mines."+d.mode+"."+d.level+"."+d.day+"."+d.size+"."+d.size+"."+d.layers+"."+d.mines;}
    public static BoardDefinition create(String mode,int size,int layers,int mines,int level){
        mode=BoardDefinition.validMode(mode);level=Math.max(0,Math.min(2,level));String day="";long seed=System.nanoTime();
        if(BoardDefinition.PUZZLE.equals(mode)){size=5;layers=level==0?2:3;mines=new int[]{7,11,14}[level];seed=new long[]{1500,2500,3501}[level];}
        if(BoardDefinition.ESCAPE.equals(mode)){size=5;layers=level==0?2:3;mines=new int[]{4,9,8}[level];seed=new long[]{1500,2505,3508}[level];}
        if(BoardDefinition.FAULT.equals(mode)){size=5;layers=level==2?3:2;mines=new int[]{6,7,9}[level];}
        if(BoardDefinition.DAILY.equals(mode)){size=5;layers=3;mines=10;day=new SimpleDateFormat("yyyy-MM-dd",Locale.ROOT).format(new Date());seed=BoardDefinition.dailySeed(day);}
        return new BoardDefinition(mode,size,layers,mines,level,seed,day);
    }
    public static void save(BoardDefinition d,Bundle b){b.putInt("definitionVersion",BoardDefinition.VERSION);b.putString("mode",d.mode);b.putInt("size",d.size);b.putInt("layers",d.layers);b.putInt("mines",d.mines);b.putInt("levelId",d.level);b.putLong("seed",d.seed);b.putString("day",d.day);}
    public static BoardDefinition read(Bundle b,int size,int layers,int mines){
        if(b==null||!b.containsKey("definitionVersion"))return create(BoardDefinition.CLASSIC,size,layers,mines,0);
        if(b.getInt("definitionVersion")!=BoardDefinition.VERSION)throw new IllegalArgumentException("Unsupported board version");
        return new BoardDefinition(b.getString("mode",BoardDefinition.CLASSIC),b.getInt("size",size),b.getInt("layers",layers),b.getInt("mines",mines),b.getInt("levelId"),b.getLong("seed"),b.getString("day",""));
    }
}


