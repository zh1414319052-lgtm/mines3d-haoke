import cos.premy.mines.data.*;
/** Offline authoring helper. Search once; ship only fixed, tested seeds. */
public class VerifyLevels {
 public static void main(String[] args){
  for(String mode:new String[]{BoardDefinition.PUZZLE,BoardDefinition.ESCAPE})for(int level=0;level<3;level++){
   int layers=level==0?2:3,mines=mode.equals(BoardDefinition.PUZZLE)?new int[]{7,11,14}[level]:new int[]{4,9,8}[level];
   for(long seed=1500+level*1000;seed<100000;seed++){
    BoardDefinition b=new BoardDefinition(mode,5,layers,mines,level,seed,"");boolean[] truth=b.mineLayout(b.start),safe=new boolean[truth.length];
    for(int i=0;i<safe.length;i++)safe[i]=b.present[i]&&!truth[i];
    if((!b.routeWin()||b.connected(safe))&&!(b.routeWin()&&level==1&&zeroRoute(b,truth))&&LogicSolver.verifies(b)){System.out.println(mode+" "+level+" layers="+layers+" mines="+mines+" seed="+seed);break;}
   }
  }
 }
 static boolean zeroRoute(BoardDefinition b,boolean[] truth){int[] clues=b.clues(truth);boolean[] seen=new boolean[truth.length];java.util.ArrayDeque<Integer> q=new java.util.ArrayDeque<>();q.add(b.start);seen[b.start]=true;while(!q.isEmpty()){int id=q.remove();if(id==b.exit)return true;if(clues[id]!=0)continue;for(int n:b.neighbors(id))if(!seen[n]){seen[n]=true;q.add(n);}}return false;}
}
