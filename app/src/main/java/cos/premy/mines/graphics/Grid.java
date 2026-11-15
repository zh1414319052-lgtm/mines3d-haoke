package cos.premy.mines.graphics;

import android.graphics.Canvas;
import android.graphics.Paint;

import cos.premy.mines.GameStatus;
import cos.premy.mines.data.BoardMoves;
import cos.premy.mines.data.MinesContainer;
import cos.premy.mines.data.MineCoord;

/**
 * Created by premy on 07.11.2017.
 */

public class Grid extends AbstractDrawable {
    private final BoardMoves moves;
    private final MineField[][][] mineFields;

    private final int N;
    private final int M;

    private final Paint paintLine;

    public Grid(MinesContainer container, GameStatus gameStatus){
        super(gameStatus);
        moves = new BoardMoves(container, gameStatus);

        N = container.getHeight();
        M = container.getWidth();
        mineFields = new MineField[gameStatus.getNumLevels()][N][M];

        gameStatus.addLevelSwitchListener(status -> {
            for(int i = 0; i != mineFields.length; i++){
                for(int ii = 0; ii != N; ii++){
                    for(int iii = 0; iii != M; iii++){
                        MineField prevLevelMine = mineFields[gameStatus.getLastLevel()][ii][iii];
                        mineFields[i][ii][iii].setPreviousMineField(prevLevelMine);
                    }
                }
            }
        });

        paintLine = new Paint();
        paintLine.setAntiAlias(true);
        paintLine.setARGB(255,255,255,255);
        paintLine.setStrokeWidth(4F);

        for(int i = 0; i != mineFields.length; i++){
            for(int ii = 0; ii != N; ii++){
                for(int iii = 0; iii != M; iii++){
                    mineFields[i][ii][iii] = new MineField(container.getMine(i, ii, iii), gameStatus, i);
                }
            }
        }

    }

    @Override
    public void draw(Canvas canvas) {
        for(int i = 0; i != N + 1; i++) {
            int line = y + BoardCoordinates.edge(i, height, N);
            canvas.drawLine(x, line, x + width, line, paintLine);
        }

        for(int i = 0; i != M + 1; i++){
            int line = x + BoardCoordinates.edge(i, width, M);
            canvas.drawLine(line, y, line, y + height, paintLine);
        }

        int level = gameStatus.getLevel();
        for(int i = 0; i != N; i++){
            for(int ii = 0; ii != M; ii++){
                mineFields[level][i][ii].draw(canvas);
            }
        }

    }

    @Override
    public void setPosition(int x, int width, int y, int height) {
        super.setPosition(x, width, y, height);
        for(int i = 0; i != mineFields.length; i++){
            for(int ii = 0; ii != N; ii++){
                for(int iii = 0; iii != M; iii++){
                    int left = BoardCoordinates.edge(iii, width, M);
                    int top = BoardCoordinates.edge(ii, height, N);
                    mineFields[i][ii][iii].setPosition(x + left,
                            BoardCoordinates.edge(iii + 1, width, M) - left, y + top,
                            BoardCoordinates.edge(ii + 1, height, N) - top);
                }
            }
        }
    }

    @Override
    public void sendVerifiedTap(int x, int y) {}

    @Override
    public void sendVerifiedLongTap(int x, int y) {
        int column = BoardCoordinates.indexAt(x - this.x, width, M);
        int row = BoardCoordinates.indexAt(y - this.y, height, N);
        int level = gameStatus.getLevel();
        if (moves.toggleFlag(new MineCoord(column, row, level))) {
            mineFields[level][row][column].refreshAppearance();
        }
    }

    @Override
    public void sendVerifiedDoubleTap(int x, int y) {
        int column = BoardCoordinates.indexAt(x - this.x, width, M);
        int row = BoardCoordinates.indexAt(y - this.y, height, N);
        int level = gameStatus.getLevel();
        for (MineCoord cell : moves.open(new MineCoord(column, row, level))) {
            mineFields[cell.z][cell.y][cell.x].refreshAppearance();
        }
    }
}
