package cos.premy.mines.graphics;

/** Shared integer partition for rendering and selecting cells, with no gaps or overlaps. */
final class BoardCoordinates {
    static int edge(int index, int span, int cells) {
        return index * span / cells;
    }

    static int indexAt(int offset, int span, int cells) {
        if (offset < 0 || offset >= span) return -1;
        return ((offset + 1) * cells - 1) / span;
    }
}
