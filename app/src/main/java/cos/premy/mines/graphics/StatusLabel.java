package cos.premy.mines.graphics;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;

import java.util.Locale;

import cos.premy.mines.GameStatus;
import cos.premy.mines.R;
import cos.premy.mines.data.MinesContainer;

final class StatusLabel {
    private final MinesContainer board;
    private final GameStatus game;
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final String time, flags, layer;
    private int x, y, lineHeight;
    private long shownSeconds = -1;
    private String timeText;

    StatusLabel(Context context, MinesContainer board, GameStatus game) {
        this.board = board;
        this.game = game;
        time = context.getString(R.string.time);
        flags = context.getString(R.string.mines_blocked);
        layer = context.getString(R.string.level);
        paint.setColor(Color.WHITE);
    }

    void setPosition(int x, int y, int lineHeight, float textSize) {
        this.x = x;
        this.y = y;
        this.lineHeight = lineHeight;
        paint.setTextSize(textSize);
    }

    void draw(Canvas canvas) {
        long seconds = game.elapsedMillis() / 1000;
        if (shownSeconds != seconds) {
            shownSeconds = seconds;
            timeText = time + " " + (seconds >= 3600
                    ? String.format(Locale.ROOT, "%d:%02d:%02d", seconds / 3600, seconds / 60 % 60, seconds % 60)
                    : String.format(Locale.ROOT, "%02d:%02d", seconds / 60, seconds % 60));
        }
        float baseline = y - paint.ascent();
        canvas.drawText(timeText, x, baseline, paint);
        canvas.drawText(flags + " " + board.getMinesBlocked() + "/" + board.getMinesNumber(),
                x, baseline + lineHeight, paint);
        canvas.drawText(layer + " " + (game.getLevel() + 1) + "/" + game.getNumLevels(),
                x, baseline + lineHeight * 2, paint);
    }
}
