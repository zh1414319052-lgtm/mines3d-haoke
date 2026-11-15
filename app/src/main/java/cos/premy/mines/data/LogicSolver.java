package cos.premy.mines.data;

import java.util.ArrayList;
import java.util.BitSet;
import java.util.List;

/** Only accepts publicly opened numbers and topology. Hidden mine arrays cannot enter a deduction. */
public final class LogicSolver {
    public static final class Hint {
        public final int cell;public final boolean mine;public final BitSet sources;
        public final int remaining,unknown;public final boolean subset;
        Hint(int c,boolean m,BitSet s,int r,int u,boolean sub){cell=c;mine=m;sources=(BitSet)s.clone();remaining=r;unknown=u;subset=sub;}
    }
    private static final class Constraint {
        final BitSet cells,sources;final int remaining;final boolean subset;
        Constraint(BitSet c,int r,BitSet s,boolean sub){cells=c;remaining=r;sources=s;subset=sub;}
    }
    /** visible: -2 void, -1 concealed, 0..6 public clue. Player flags are never premises. */
    public static Hint next(BoardDefinition board,int[] visible,boolean[] flags){
        BitSet provenMines=new BitSet(),provenSafe=new BitSet();
        List<Constraint> knowledge=new ArrayList<>();
        for(int i=0;i<visible.length;i++)if(visible[i]>=0){BitSet c=new BitSet(),s=new BitSet();s.set(i);for(int n:board.neighbors(i))if(visible[n]==-1)c.set(n);knowledge.add(new Constraint(c,visible[i],s,false));}
        BitSet all=new BitSet();for(int i=0;i<visible.length;i++)if(visible[i]==-1)all.set(i);
        knowledge.add(new Constraint(all,board.mines,new BitSet(),false));
        for(int pass=0;pass<visible.length+1;pass++){
            List<Constraint> normalized=new ArrayList<>();boolean progress=false;
            for(Constraint raw:knowledge){
                BitSet c=(BitSet)raw.cells.clone(),known=(BitSet)c.clone();known.and(provenMines);int left=raw.remaining-known.cardinality();
                c.andNot(provenMines);c.andNot(provenSafe);
                if(left<0||left>c.cardinality())return null;
                if(c.isEmpty())continue;
                if(left==0||left==c.cardinality()){
                    boolean mine=left>0;
                    for(int cell=c.nextSetBit(0);cell>=0;cell=c.nextSetBit(cell+1)) {
                        if(!mine||!flags[cell])return new Hint(cell,mine,raw.sources,left,c.cardinality(),raw.subset);
                        provenMines.set(cell);progress=true;
                    }
                }else normalized.add(new Constraint(c,left,raw.sources,raw.subset));
            }
            if(progress){knowledge=normalized;continue;}
            // Pairwise subset elimination, bounded by six-neighbor constraints + a global total.
            int initial=normalized.size();
            outer:for(int i=0;i<initial;i++)for(int j=0;j<initial;j++)if(i!=j){
                Constraint a=normalized.get(i),b=normalized.get(j);if(a.cells.cardinality()>=b.cells.cardinality())continue;
                BitSet extra=(BitSet)a.cells.clone();extra.andNot(b.cells);if(!extra.isEmpty())continue;
                BitSet difference=(BitSet)b.cells.clone();difference.andNot(a.cells);int left=b.remaining-a.remaining;
                if(left<0||left>difference.cardinality())return null;
                BitSet sources=(BitSet)a.sources.clone();sources.or(b.sources);
                if(left==0||left==difference.cardinality()){
                    boolean mine=left>0;
                    for(int cell=difference.nextSetBit(0);cell>=0;cell=difference.nextSetBit(cell+1)){
                        if(!mine||!flags[cell])return new Hint(cell,mine,sources,left,difference.cardinality(),true);
                        provenMines.set(cell);progress=true;
                    }
                    if(progress)break outer;
                }
            }
            if(!progress)return null;
            knowledge=normalized;
        }return null;
    }
    /** Offline verification harness; truth is used only to expose a proven safe cell and audit soundness. */
    public static boolean verifies(BoardDefinition board){
        boolean[] truth=board.mineLayout(board.start),flags=new boolean[truth.length];int[] clues=board.clues(truth),visible=new int[truth.length];
        for(int i=0;i<visible.length;i++)visible[i]=board.present[i]?-1:-2;visible[board.start]=clues[board.start];
        for(int step=0;step<truth.length*2;step++){
            Hint hint=next(board,visible,flags);if(hint==null){for(int i=0;i<truth.length;i++)if(truth[i]&&!flags[i])return false;return true;}
            if(truth[hint.cell]!=hint.mine)throw new AssertionError("Unsound deduction");
            if(hint.mine)flags[hint.cell]=true;else visible[hint.cell]=clues[hint.cell];
        }return false;
    }
}
