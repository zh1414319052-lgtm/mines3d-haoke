package cos.premy.mines.data;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

import cos.premy.mines.GameStatus;
import cos.premy.mines.generator.RandomMinesGenerator;

/** Applies the same moves for the flat and 3D boards. */
public final class BoardMoves {
    private final MinesContainer board;
    private final GameStatus status;

    public BoardMoves(MinesContainer board, GameStatus status) {
        this.board = board;
        this.status = status;
    }

    public boolean toggleFlag(MineCoord cell) {
        if (cell==null||!status.stillPlaying() || cell.z != status.getLevel()||!board.present(cell.z,cell.y,cell.x)) return false;
        Mine mine = board.getMine(cell.z, cell.y, cell.x);
        if (mine.getStatus() == MineStatus.OPENED) return false;
        mine.setGameStatus(mine.getStatus() == MineStatus.BLOCKED
                ? MineStatus.UNBLOCKED : MineStatus.BLOCKED, status);
        return true;
    }

    public List<MineCoord> open(MineCoord cell) {
        if (cell==null||!status.stillPlaying() || cell.z != status.getLevel()||!board.present(cell.z,cell.y,cell.x)) return Collections.emptyList();
        Mine mine = board.getMine(cell.z, cell.y, cell.x);
        if (mine.getStatus() != MineStatus.UNBLOCKED) return Collections.emptyList();
        if (!board.getFactorized()) {
            board.generate(cell);
        }
        List<MineCoord> changed = new ArrayList<>();
        if(mine.getIsReal()) status.triggerExplosion(cell);
        mine.setGameStatus(MineStatus.OPENED, status);
        changed.add(cell);
        if (mine.getIsReal() || mine.getNeighbors() != 0 || !(status.getFlood()||board.definition().autoFlood())||board.definition().routeWin()) return changed;

        ArrayDeque<MineCoord> queue = new ArrayDeque<>(mine.getAllNeighborCoords());
        while (!queue.isEmpty() && status.stillPlaying()) {
            MineCoord neighbor = queue.removeFirst();
            Mine candidate = board.getMine(neighbor.z, neighbor.y, neighbor.x);
            if (candidate.getStatus() != MineStatus.UNBLOCKED || candidate.getIsReal()) continue;
            candidate.setGameStatus(MineStatus.OPENED, status);
            changed.add(neighbor);
            if (candidate.getNeighbors() == 0) queue.addAll(candidate.getAllNeighborCoords());
        }
        return changed;
    }
}
