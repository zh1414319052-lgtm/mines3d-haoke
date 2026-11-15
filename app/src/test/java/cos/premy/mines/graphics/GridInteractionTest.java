package cos.premy.mines.graphics;

import android.content.Context;
import android.content.SharedPreferences;

import org.junit.Test;

import cos.premy.mines.GameStatus;
import cos.premy.mines.data.BoardMoves;
import cos.premy.mines.data.MineCoord;
import cos.premy.mines.data.MineStatus;
import cos.premy.mines.data.MinesContainer;

import static org.junit.Assert.*;
import static org.mockito.Mockito.*;

public class GridInteractionTest {
    private GameStatus status(boolean flood) {
        return status(flood, 3);
    }

    private GameStatus status(boolean flood, int layers) {
        Context context = mock(Context.class);
        SharedPreferences settings = mock(SharedPreferences.class);
        when(context.getSharedPreferences("cos.premy.mines.settings", Context.MODE_PRIVATE))
                .thenReturn(settings);
        when(settings.getBoolean("flood", false)).thenReturn(flood);
        return new GameStatus(context, layers, 0, 0, 0);
    }

    @Test
    public void everyPaintedPixelSelectsExactlyItsCellAcrossAllBoardSizes() {
        for (int n : new int[]{5, 8, 10, 12, 15}) {
            for (int i = 0; i < n; i++) {
                int left = BoardCoordinates.edge(i, 103, n);
                int right = BoardCoordinates.edge(i + 1, 103, n);
                for (int x = left; x < right; x++) {
                    assertEquals(i, BoardCoordinates.indexAt(x, 103, n));
                }
            }
            assertEquals(-1, BoardCoordinates.indexAt(103, 103, n));
        }
    }

    @Test
    public void firstRevealOnAnInternalLineOpensOneSafeCellOnTheSelectedLayer() {
        GameStatus game = status(false);
        MinesContainer board = new MinesContainer(5, 5, 3, 9);
        Grid grid = new Grid(board, game);
        grid.setPosition(10, 103, 20, 101);
        game.incrementLevel();
        grid.sendLongTap(30, 40);
        assertEquals(1, board.getMinesBlocked());
        grid.sendDoubleTap(30, 40);
        assertFalse(board.getFactorized());
        grid.sendLongTap(30, 40);
        grid.sendDoubleTap(113, 40);
        assertFalse(board.getFactorized());
        grid.sendDoubleTap(30, 40);
        assertTrue(game.stillPlaying());
        assertFalse(board.isRealMine(1, 1, 1));
        assertEquals(MineStatus.OPENED, board.getMine(1, 1, 1).getStatus());
        assertEquals(1, board.getMinesOpened());
    }

    @Test
    public void autoExpansionCrossesLayersWithoutOpeningFlagsOrMines() throws Exception {
        GameStatus game = status(true);
        MinesContainer board = new MinesContainer(5, 5, 3, 1);
        board.getMine(2, 4, 4).setIsReal(true);
        Grid grid = new Grid(board, game);
        grid.setPosition(10, 103, 20, 101);
        grid.sendLongTap(31, 21);
        board.setFactorized();
        grid.sendDoubleTap(11, 21);
        assertEquals(MineStatus.OPENED, board.getMine(1, 0, 0).getStatus());
        assertEquals(MineStatus.BLOCKED, board.getMine(0, 0, 1).getStatus());
        assertEquals(MineStatus.UNBLOCKED, board.getMine(2, 4, 4).getStatus());
        assertEquals(73, board.getMinesOpened());
        assertTrue(game.stillPlaying());
    }

    @Test
    public void savedBoardRestoresCluesCountersAndFlagsPlacedBeforeGeneration() throws Exception {
        GameStatus game = status(false);
        MinesContainer original = new MinesContainer(5, 5, 3, 2);
        original.getMine(2, 0, 0).setGameStatus(MineStatus.BLOCKED, game);
        MinesContainer ungenerate = MinesContainer.restore(5, 3, 2, false, original.saveCells());
        assertNotNull(ungenerate);
        assertFalse(ungenerate.getFactorized());
        assertEquals(1, ungenerate.getMinesBlocked());

        original.getMine(2, 0, 0).setIsReal(true);
        original.getMine(1, 0, 1).setIsReal(true);
        original.setFactorized();
        original.getMine(1, 0, 0).setGameStatus(MineStatus.OPENED, game);
        assertEquals(1, original.getOkBlockedMines());
        MinesContainer restored = MinesContainer.restore(5, 3, 2, true, original.saveCells());
        assertNotNull(restored);
        assertArrayEquals(original.saveCells(), restored.saveCells());
        assertEquals(2, restored.getMine(1, 0, 0).getNeighbors());
        assertEquals(1, restored.getMinesOpened());
        assertEquals(1, restored.getOkBlockedMines());
        restored.getMine(1, 0, 1).setGameStatus(MineStatus.BLOCKED, game);
        assertTrue(game.hasUserWon());
        assertNull(MinesContainer.restore(5, 3, 2, true, new byte[2]));
    }

    @Test
    public void boardFitsInPortraitSquareAndLandscapeWithoutOverlappingControls() {
        for (int[] size : new int[][]{{320, 640}, {320, 320}, {640, 320}, {480, 320}}) {
            MinesLayoutComputor layout = new MinesLayoutComputor(size[0], size[1], 12, 48, 22);
            assertTrue(layout.gridX >= 0 && layout.gridY >= 0 && layout.gridSize > 0);
            assertTrue(layout.gridX + layout.gridSize <= size[0]);
            assertTrue(layout.gridY + layout.gridSize <= size[1]);
            if (layout.landscape) assertTrue(layout.buttonX + layout.buttonWidth < layout.gridX);
            else assertTrue(layout.buttonY + layout.buttonHeight < layout.gridY);
        }
    }

    @Test
    public void defaultGameWinsOnlyWhenAllMinesAreFlaggedAndNoFlagIsWrong() {
        GameStatus game = status(false, 2);
        MinesContainer board = new MinesContainer(5, 5, 2, 7);
        BoardMoves moves = new BoardMoves(board, game);
        MineCoord safe = new MineCoord(2, 2, 0);
        MineCoord wrong = new MineCoord(0, 0, 0);
        assertTrue(moves.toggleFlag(wrong));
        assertEquals(1, moves.open(safe).size());
        assertFalse(board.isRealMine(safe.z, safe.y, safe.x));
        if (board.isRealMine(wrong.z, wrong.y, wrong.x)) {
            assertTrue(moves.toggleFlag(wrong));
            for (int i = 1; i < 25; i++) {
                if (i != 12 && !board.isRealMine(0, i / 5, i % 5)) {
                    wrong = new MineCoord(i % 5, i / 5, 0);
                    break;
                }
            }
            assertTrue(moves.toggleFlag(wrong));
        }
        for (int z = 0; z < 2; z++) {
            assertEquals(z, game.getLevel());
            for (int row = 0; row < 5; row++) for (int column = 0; column < 5; column++) {
                if (board.isRealMine(z, row, column)) {
                    assertTrue(moves.toggleFlag(new MineCoord(column, row, z)));
                }
            }
            game.incrementLevel();
        }
        assertTrue(game.stillPlaying());
        assertTrue(moves.toggleFlag(wrong));
        assertEquals(1, game.outcome());
        assertFalse(moves.toggleFlag(wrong));
    }

    @Test
    public void defaultGameLosesWhenAMineIsOpenedAndRejectsFurtherMoves() {
        GameStatus game = status(false, 2);
        MinesContainer board = new MinesContainer(5, 5, 2, 7);
        BoardMoves moves = new BoardMoves(board, game);
        assertEquals(1, moves.open(new MineCoord(2, 2, 0)).size());
        for (int z = 0; z < 2; z++) {
            for (int row = 0; row < 5; row++) for (int column = 0; column < 5; column++) {
                if (board.isRealMine(z, row, column)) {
                    assertEquals(1, moves.open(new MineCoord(column, row, z)).size());
                    assertEquals(2, game.outcome());
                    assertTrue(moves.open(new MineCoord(0, 0, z)).isEmpty());
                    return;
                }
            }
            game.incrementLevel();
        }
        fail("Expected a mine on a 5x5x2 board with seven mines");
    }

    @Test
    public void middleLayerClueUsesSixOrthogonalNeighborsAndExcludesDiagonals() throws Exception {
        MinesContainer board = new MinesContainer(5, 5, 3, 7);
        int[][] mines = {{1, 2, 1}, {1, 2, 3}, {1, 1, 2}, {1, 3, 2},
                {0, 2, 2}, {2, 2, 2}, {0, 1, 2}};
        for (int[] pos : mines) board.getMine(pos[0], pos[1], pos[2]).setIsReal(true);
        board.setFactorized();
        assertEquals(6, board.getMine(1, 2, 2).getNeighbors());
    }

    @Test
    public void maximumHardBoardKeepsItsMineCountAndIgnoresASelectionFromTheOldLayer() {
        GameStatus game = status(false, 8);
        MinesContainer board = new MinesContainer(15, 15, 8, 540);
        BoardMoves moves = new BoardMoves(board, game);
        MineCoord stale = new MineCoord(0, 0, 0);
        game.decrementLevel();
        assertFalse(moves.toggleFlag(stale));
        assertTrue(moves.open(stale).isEmpty());
        assertFalse(board.getFactorized());
        MineCoord corner = new MineCoord(14, 14, 7);
        assertEquals(1, moves.open(corner).size());
        assertFalse(board.isRealMine(corner.z, corner.y, corner.x));
        int mineCount = 0;
        for (int z = 0; z < 8; z++) for (int row = 0; row < 15; row++) {
            for (int column = 0; column < 15; column++) {
                if (board.isRealMine(z, row, column)) mineCount++;
            }
        }
        assertEquals(540, mineCount);
    }
}
