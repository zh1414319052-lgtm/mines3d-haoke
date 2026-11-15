package cos.premy.mines.data;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Random;

/** Immutable, versioned topology. Array layer zero is physically the deepest deck. */
public final class BoardDefinition {
    public static final int VERSION=1;
    public static final String CLASSIC="classic", ESCAPE="escape", PUZZLE="puzzle",
            FAULT="fault", SCAN="scan", DAILY="daily";
    public final String mode,day;
    public final int size,layers,mines,level,start,exit;
    public final long seed;
    public final boolean[] present;
    public BoardDefinition(String mode,int size,int layers,int mines,int level,long seed,String day) {
        this.mode=validMode(mode);this.size=size;this.layers=layers;this.mines=mines;
        this.level=Math.max(0,Math.min(2,level));this.seed=seed;this.day=day==null?"":day;
        present=new boolean[size*size*layers];java.util.Arrays.fill(present,true);
        if(FAULT.equals(mode)||ESCAPE.equals(mode)&&this.level==2) {
            for(int z=0;z<layers;z++)for(int y=0;y<size;y++)for(int x=0;x<size;x++) {
                boolean hole;
                if(ESCAPE.equals(mode))hole=x==size/2 && (z!=1||y!=size/2);
                else if(this.level==0)hole=(x<2&&y>=size-2)||(x>=size-2&&y<2);
                else if(this.level==1)hole=x==size/2&&y==size/2;
                else hole=(z%2==0?x==0:x==size-1);
                present[index(x,y,z)]=!hole;
            }
        }
        int first=index(0,0,layers-1);
        if(ESCAPE.equals(mode)&&this.level==0)first=index(size/2,size/2,layers-1);
        if(ESCAPE.equals(mode)&&this.level==1)first=index(0,size/2,layers-1);
        while(!present[first])first++;
        start=first;
        int last=ESCAPE.equals(mode)&&this.level<2?index(size-1,size/2,0):size*size-1;while(!present[last])last--;exit=last;
        int count=0;for(boolean p:present)if(p)count++;
        if(size<5||size>15||layers<2||layers>8||mines<1||mines>=count-1)
            throw new IllegalArgumentException("Invalid board definition");
    }
    public static String validMode(String mode){
        return ESCAPE.equals(mode)||PUZZLE.equals(mode)||FAULT.equals(mode)||SCAN.equals(mode)||DAILY.equals(mode)?mode:CLASSIC;
    }
    public int index(int x,int y,int z){return(z*size+y)*size+x;}
    public MineCoord coord(int index){return new MineCoord(index%size,index/size%size,index/(size*size));}
    public int[] neighbors(int id){
        if(!present[id])return new int[0];
        MineCoord c=coord(id);int[] a=new int[6];int n=0;
        for(int[] d:new int[][]{{1,0,0},{-1,0,0},{0,1,0},{0,-1,0},{0,0,1},{0,0,-1}}){
            int x=c.x+d[0],y=c.y+d[1],z=c.z+d[2];
            if(x>=0&&x<size&&y>=0&&y<size&&z>=0&&z<layers&&present[index(x,y,z)])a[n++]=index(x,y,z);
        }return java.util.Arrays.copyOf(a,n);
    }
    public boolean fixedStart(){return PUZZLE.equals(mode)||DAILY.equals(mode)||ESCAPE.equals(mode);}
    public boolean routeWin(){return ESCAPE.equals(mode);}
    public boolean autoFlood(){return PUZZLE.equals(mode)||DAILY.equals(mode);}
    public boolean[] mineLayout(int safe){
        List<Integer> candidates=new ArrayList<>();
        boolean[] excluded=new boolean[present.length];excluded[safe]=true;
        // Fixed starts have an initial zero clue; classic retains its original density/rule.
        if(fixedStart())for(int n:neighbors(safe))excluded[n]=true;
        if(routeWin())excluded[exit]=true;
        for(int i=0;i<present.length;i++)if(present[i]&&!excluded[i])candidates.add(i);
        if(candidates.size()<mines)throw new IllegalArgumentException("Not enough safe candidates");
        Collections.shuffle(candidates,new Random(seed));boolean[] result=new boolean[present.length];
        for(int i=0;i<mines;i++)result[candidates.get(i)]=true;return result;
    }
    public int[] clues(boolean[] layout){int[] c=new int[present.length];for(int i=0;i<c.length;i++){if(!present[i])c[i]=-2;else for(int n:neighbors(i))if(layout[n])c[i]++;}return c;}
    public boolean connected(boolean[] opened){
        if(!opened[start]||!opened[exit])return false;
        boolean[] seen=new boolean[present.length];java.util.ArrayDeque<Integer> q=new java.util.ArrayDeque<>();q.add(start);seen[start]=true;
        while(!q.isEmpty()){int p=q.removeFirst();if(p==exit)return true;for(int n:neighbors(p))if(opened[n]&&!seen[n]){seen[n]=true;q.add(n);}}return false;
    }
    public static long dailySeed(String day){long h=0xcbf29ce484222325L;for(char c:("Mines3D-v1/"+day).toCharArray()){h^=c;h*=0x100000001b3L;}return h;}
}
