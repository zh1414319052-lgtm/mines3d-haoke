package cos.premy.mines;

import android.os.Bundle;
import android.os.SystemClock;
import cos.premy.mines.data.MineCoord;

/** One authoritative effect clock, independent of the stopped game timer. */
public final class ExplosionState {
    interface Clock {long now();}
    private final Clock clock;
    public ExplosionState(){this(SystemClock::elapsedRealtime);}
    ExplosionState(Clock clock){this.clock=clock;}
    public static final long DURATION=10000;
    private long elapsed,anchor;
    private boolean running;
    public MineCoord cell;
    public boolean trigger(MineCoord hit){if(cell!=null)return false;cell=new MineCoord(hit.x,hit.y,hit.z);elapsed=0;anchor=clock.now();return true;}
    /** New public server event, already deduplicated by the online controller. */
    public void networkEvent(MineCoord hit,long ageMs){cell=new MineCoord(hit.x,hit.y,hit.z);elapsed=Math.max(0,Math.min(DURATION,ageMs));anchor=clock.now();}
    /** Online games continue on the server; suspended clients never resume an old attack. */
    public void finishNetworkEvent(){elapsed=DURATION;anchor=clock.now();}
    public long elapsed(){return Math.min(DURATION,elapsed+(running&&cell!=null?Math.max(0,clock.now()-anchor):0));}
    public void active(boolean value){if(running==value)return;if(!value)elapsed=elapsed();anchor=clock.now();running=value;}
    public boolean animating(){return cell!=null&&elapsed()<DURATION;}
    public void save(Bundle out){out.putLong("blast.elapsed",elapsed());if(cell!=null){out.putInt("blast.x",cell.x);out.putInt("blast.y",cell.y);out.putInt("blast.z",cell.z);}}
    public void restore(Bundle in){if(in!=null&&in.containsKey("blast.x")){cell=new MineCoord(in.getInt("blast.x"),in.getInt("blast.y"),in.getInt("blast.z"));elapsed=Math.max(0,Math.min(DURATION,in.getLong("blast.elapsed",DURATION)));}}
}
