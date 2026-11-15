package cos.premy.mines.graphics;

/** A pointer sequence that has become a drag or pinch cannot turn back into a tap. */
final class BoardTouch {
    private final float slopSquared;
    private boolean started, dragged, multiple;
    private float originX, originY, lastX, lastY;
    float dx, dy;

    BoardTouch(float slop) {
        slopSquared = slop * slop;
    }

    void down(float x, float y) {
        started = true;
        dragged = multiple = false;
        originX = lastX = x;
        originY = lastY = y;
    }

    void multiplePointers() { multiple = true; }

    boolean drag(float x, float y) {
        if (!started || multiple || (!dragged && withinSlop(x, y))) return false;
        dragged = true;
        dx = x - lastX;
        dy = y - lastY;
        lastX = x;
        lastY = y;
        return true;
    }

    boolean up(float x, float y) {
        boolean tap = started && !multiple && !dragged && withinSlop(x, y);
        cancel();
        return tap;
    }

    void cancel() { started = false; }

    private boolean withinSlop(float x, float y) {
        float dx = x - originX;
        float dy = y - originY;
        return dx * dx + dy * dy <= slopSquared;
    }
}
