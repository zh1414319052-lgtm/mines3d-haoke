package cos.premy.mines.graphics;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;

import cos.premy.mines.GameStatus;
import cos.premy.mines.R;

/** Two clearly marked touch targets; the current layer is shown beside them. */
final class SwitchButton extends AbstractDrawable {
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final String previous;
    private final String next;
    private boolean vertical;

    SwitchButton(Context context, GameStatus status) {
        super(status);
        previous = context.getString(R.string.previous_layer);
        next = context.getString(R.string.next_layer);
        paint.setColor(Color.WHITE);
        paint.setTextAlign(Paint.Align.CENTER);
        paint.setStrokeWidth(context.getResources().getDisplayMetrics().density);
    }

    void setMetrics(boolean vertical, float textSize) {
        this.vertical = vertical;
        paint.setTextSize(textSize);
    }

    @Override
    public void draw(Canvas canvas) {
        if (width <= 0 || height <= 0) return;
        paint.setStyle(Paint.Style.STROKE);
        canvas.drawRect(x, y, x + width, y + height, paint);
        if (vertical) canvas.drawLine(x, y + height / 2f, x + width, y + height / 2f, paint);
        else canvas.drawLine(x + width / 2f, y, x + width / 2f, y + height, paint);
        paint.setStyle(Paint.Style.FILL);
        float baseline = -(paint.ascent() + paint.descent()) / 2;
        float firstX = x + width * (vertical ? .5f : .25f);
        float nextX = x + width * (vertical ? .5f : .75f);
        canvas.drawText(previous, firstX, y + height * (vertical ? .25f : .5f) + baseline, paint);
        canvas.drawText(next, nextX, y + height * (vertical ? .75f : .5f) + baseline, paint);
    }

    @Override
    protected void sendVerifiedTap(int x, int y) {
        if (vertical ? (y - this.y) * 2 < height : (x - this.x) * 2 < width) {
            gameStatus.decrementLevel();
        } else {
            gameStatus.incrementLevel();
        }
    }

    @Override
    protected void sendVerifiedLongTap(int x, int y) {}

    @Override
    protected void sendVerifiedDoubleTap(int x, int y) {}
}
