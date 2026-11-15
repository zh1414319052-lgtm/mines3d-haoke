package cos.premy.mines;
import org.junit.Test;
import cos.premy.mines.data.MineCoord;
import static org.junit.Assert.*;
public class ExplosionStateTest {
 @Test public void effectIsOneShotAndFreezesInBackground(){long[] now={100};ExplosionState fx=new ExplosionState(()->now[0]);fx.active(true);MineCoord cell=new MineCoord(4,3,0);assertTrue(fx.trigger(cell));cell.x=1;now[0]+=340;assertEquals(340,fx.elapsed());fx.active(false);now[0]+=90000;assertEquals(340,fx.elapsed());assertFalse(fx.trigger(new MineCoord(0,0,0)));assertEquals(4,fx.cell.x);fx.active(true);now[0]+=1000;assertEquals(1340,fx.elapsed());now[0]+=10000;assertEquals(10000,fx.elapsed());assertFalse(fx.animating());}
}
