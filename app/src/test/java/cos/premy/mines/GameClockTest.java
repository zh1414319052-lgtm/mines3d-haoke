package cos.premy.mines;

import org.junit.Test;

import static org.junit.Assert.assertEquals;

public class GameClockTest {
    @Test
    public void pausedAndRestoredSessionsExcludeBackgroundTime() {
        GameClock clock = new GameClock(0);
        clock.resume(1000);
        clock.resume(1300);
        clock.pause(2500);
        clock.pause(4000);
        assertEquals(1500, clock.elapsed(12000));
        GameClock restored = new GameClock(clock.elapsed(12000));
        restored.resume(13000);
        assertEquals(2000, restored.elapsed(13500));
    }
}
