package cos.premy.mines;

import android.content.Context;
import android.os.Bundle;

import cos.premy.mines.data.MinesContainer;
import cos.premy.mines.data.*;
import java.util.BitSet;

/** Activity-owned session; a saved Android task can recreate it without the old process. */
public final class LoadedGame {
    public final GameStatus status;
    public final MinesContainer board;
    public final BoardDefinition definition;
    public int scansLeft=2,hintsUsed;
    private int[] scanned={-1,-1};
    public LogicSolver.Hint pendingHint;
    public BitSet hintSources=new BitSet();
    public int hintTarget=-1;

    public LoadedGame(Context context, int size, int layers, int mines, Bundle state) {
        this(context,GameSetup.read(state,size,layers,mines),state);
    }
    public LoadedGame(Context context,BoardDefinition definition,Bundle state){
        this.definition=definition;
        int size=definition.size,layers=definition.layers,mines=definition.mines;
        MinesContainer restored = state == null ? null : MinesContainer.restore(definition,
                state.getBoolean("generated"), state.getByteArray("cells"));
        if (restored == null) {
            board = new MinesContainer(size, size, layers, mines);
            board.configure(definition);
            status = new GameStatus(context, layers, layers-1, 0, 0);
            if(definition.fixedStart())new BoardMoves(board,status).open(definition.coord(definition.start));
        } else {
            board = restored;
            status = new GameStatus(context, layers, state.getInt("layer"),
                    state.getLong("elapsed"), state.getInt("outcome"));
            status.explosion.restore(state);
            scansLeft=Math.max(0,Math.min(2,state.getInt("scansLeft",2)));
            hintsUsed=Math.max(0,state.getInt("hintsUsed"));
            board.wrongFlagActions=Math.max(0,state.getInt("wrongFlags"));
            int[] savedScans=state.getIntArray("scanned");if(savedScans!=null&&savedScans.length==2)scanned=savedScans;
            if(state.getBoolean("hintPending")){pendingHint=findHint();if(pendingHint!=null){hintSources=(BitSet)pendingHint.sources.clone();hintTarget=pendingHint.cell;}}
        }
    }

    public void save(Bundle state) {
        GameSetup.save(definition,state);
        state.putInt("scansLeft",scansLeft);state.putInt("hintsUsed",hintsUsed);state.putInt("wrongFlags",board.wrongFlagActions);state.putIntArray("scanned",scanned);state.putBoolean("hintPending",pendingHint!=null);
        status.explosion.save(state);
        state.putBoolean("generated", board.getFactorized());
        state.putByteArray("cells", board.saveCells());
        state.putInt("layer", status.getLevel());
        state.putLong("elapsed", status.elapsedMillis());
        state.putInt("outcome", status.outcome());
    }
    public int[] scan(MineCoord cell){
        if(cell==null||cell.z!=status.getLevel()||!status.stillPlaying()||!BoardDefinition.SCAN.equals(definition.mode)||!board.present(cell.z,cell.y,cell.x))return null;
        Mine m=board.getMine(cell.z,cell.y,cell.x);if(m.getStatus()!=MineStatus.OPENED||m.getIsReal()||m.getNeighbors()==0)return null;
        int id=definition.index(cell.x,cell.y,cell.z);boolean used=scanned[0]==id||scanned[1]==id;
        if(!used){if(scansLeft==0)return null;scanned[2-scansLeft]=id;scansLeft--;}
        int same=0,adjacent=0;for(MineCoord n:m.getAllNeighborCoords())if(board.getMine(n.z,n.y,n.x).getIsReal()){if(n.z==cell.z)same++;else adjacent++;}
        return new int[]{same,adjacent};
    }
    public LogicSolver.Hint findHint(){
        if(!status.stillPlaying()||!board.getFactorized())return null;
        int[] visible=new int[definition.present.length];boolean[] flags=new boolean[visible.length];
        for(int i=0;i<visible.length;i++){MineCoord c=definition.coord(i);Mine m=board.getMine(c.z,c.y,c.x);visible[i]=!definition.present[i]?-2:m.getStatus()==MineStatus.OPENED&&!m.getIsReal()?m.getNeighbors():-1;flags[i]=m.getStatus()==MineStatus.BLOCKED;}
        return LogicSolver.next(definition,visible,flags);
    }
    public boolean beginHint(){pendingHint=findHint();if(pendingHint==null)return false;hintsUsed++;hintSources=(BitSet)pendingHint.sources.clone();hintTarget=pendingHint.cell;return true;}
    public void clearHint(){pendingHint=null;hintSources.clear();hintTarget=-1;}
}
