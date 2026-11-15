package cos.premy.mines;

/** Tracks foreground play using a monotonic time source supplied by the activity. */
public final class GameClock {
    private long elapsed;
    private long startedAt = -1;

    public GameClock(long elapsed) {
        this.elapsed = Math.max(0, elapsed);
    }

    public void resume(long now) {
        if (startedAt < 0) startedAt = now;
    }

    public void pause(long now) {
        elapsed = elapsed(now);
        startedAt = -1;
    }

    public long elapsed(long now) {
        return elapsed + (startedAt < 0 ? 0 : Math.max(0, now - startedAt));
    }
}
