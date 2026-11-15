import cos.premy.mines.data.*;
import java.nio.file.*;
import java.util.*;
public class ExportLevelReview {
 public static void main(String[] args)throws Exception{StringBuilder out=new StringBuilder("[");for(int level=0;level<3;level++){BoardDefinition b=new BoardDefinition("escape",5,level==0?2:3,new int[]{4,9,8}[level],level,new long[]{1500,2505,3508}[level],"");boolean[] truth=b.mineLayout(b.start);int[] cells=b.clues(truth);for(int i=0;i<cells.length;i++)if(truth[i])cells[i]=-1;int[] prev=new int[cells.length];Arrays.fill(prev,-1);ArrayDeque<Integer> q=new ArrayDeque<>();q.add(b.start);prev[b.start]=b.start;while(!q.isEmpty()){int id=q.remove();for(int n:b.neighbors(id))if(!truth[n]&&prev[n]<0){prev[n]=id;q.add(n);}}List<Integer> path=new ArrayList<>();for(int id=b.exit;;id=prev[id]){path.add(id);if(id==b.start)break;}Collections.reverse(path);if(level>0)out.append(',');out.append("{\"level\":").append(level).append(",\"layers\":").append(b.layers).append(",\"seed\":").append(b.seed).append(",\"start\":").append(b.start).append(",\"exit\":").append(b.exit).append(",\"cells\":").append(Arrays.toString(cells)).append(",\"shortestSafeRoute\":").append(path).append('}');}out.append(']');Files.write(Paths.get(args[0]),out.toString().getBytes("UTF-8"));}
}

