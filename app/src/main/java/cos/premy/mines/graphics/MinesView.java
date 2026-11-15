package cos.premy.mines.graphics;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.os.SystemClock;
import android.util.DisplayMetrics;
import android.util.TypedValue;
import android.view.GestureDetector;
import android.view.MotionEvent;
import android.view.View;

import cos.premy.mines.LoadedGame;

public class MinesView extends View {
    private final LoadedGame game;
    private final Grid grid;
    private final SwitchButton switchButton;
    private final StatusLabel statusLabel;
    private final GestureDetector detector;
    private boolean active;
    private long animateUntil;
    private final Runnable refresh = this::invalidate;

    public MinesView(Context context, LoadedGame game) {
        super(context);
        this.game = game;
        grid = new Grid(game.board, game.status);
        switchButton = new SwitchButton(context, game.status);
        statusLabel = new StatusLabel(context, game.board, game.status);

        detector = new GestureDetector(context, new GestureDetector.SimpleOnGestureListener() {
            @Override
            public boolean onDown(MotionEvent event) {
                switchButton.sendTap((int) event.getX(), (int) event.getY());
                redrawInteraction();
                return true;
            }

            @Override
            public void onLongPress(MotionEvent event) {
                grid.sendLongTap((int) event.getX(), (int) event.getY());
                redrawInteraction();
            }

            @Override
            public boolean onDoubleTap(MotionEvent event) {
                grid.sendDoubleTap((int) event.getX(), (int) event.getY());
                redrawInteraction();
                return true;
            }
        });
    }

    void setActive(boolean active) {
        this.active = active;
        removeCallbacks(refresh);
        if (active) invalidate();
        else {
            long now = SystemClock.uptimeMillis();
            MotionEvent cancel = MotionEvent.obtain(now, now, MotionEvent.ACTION_CANCEL, 0, 0, 0);
            detector.onTouchEvent(cancel);
            cancel.recycle();
        }
    }

    private void redrawInteraction() {
        animateUntil = SystemClock.uptimeMillis() + 220;
        invalidate();
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        return active && game.status.stillPlaying() && detector.onTouchEvent(event);
    }

    @Override
    protected void onDetachedFromWindow() {
        setActive(false);
        super.onDetachedFromWindow();
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        canvas.drawColor(Color.BLACK);
        grid.draw(canvas);
        switchButton.draw(canvas);
        statusLabel.draw(canvas);

        removeCallbacks(refresh);
        if (active) {
            if (SystemClock.uptimeMillis() < animateUntil) postDelayed(refresh, 16);
            else if (game.status.stillPlaying()) {
                postDelayed(refresh, 1000 - game.status.elapsedMillis() % 1000);
            }
        }
    }

    @Override
    protected void onSizeChanged(int w, int h, int oldw, int oldh) {
        super.onSizeChanged(w, h, oldw, oldh);
        DisplayMetrics metrics = getResources().getDisplayMetrics();
        int gap = Math.round(12 * metrics.density);
        int controlSize = Math.round(48 * metrics.density);
        float textSize = TypedValue.applyDimension(TypedValue.COMPLEX_UNIT_SP, 16, metrics);
        int lineHeight = (int) Math.ceil(textSize * 1.35);
        MinesLayoutComputor layout = new MinesLayoutComputor(w, h, gap, controlSize, lineHeight);
        grid.setPosition(layout.gridX, layout.gridSize, layout.gridY, layout.gridSize);
        switchButton.setMetrics(layout.landscape, textSize);
        switchButton.setPosition(layout.buttonX, layout.buttonWidth, layout.buttonY, layout.buttonHeight);
        statusLabel.setPosition(layout.statusX, layout.statusY, lineHeight, textSize);
    }
}
