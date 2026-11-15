package cos.premy.mines.graphics;

/** Fits a square board and keeps the status and layer controls outside the playable area. */
final class MinesLayoutComputor {
    final boolean landscape;
    final int gridX, gridY, gridSize;
    final int buttonX, buttonY, buttonWidth, buttonHeight;
    final int statusX, statusY;

    MinesLayoutComputor(int width, int height, int gap, int minControlSize, int textHeight) {
        landscape = width > height;
        int statusHeight = textHeight * 3;
        if (landscape) {
            int rail = Math.min(width / 3, Math.max(minControlSize * 3, textHeight * 8));
            gridSize = Math.max(0, Math.min(width - rail - gap * 3, height - gap * 2));
            int left = Math.max(gap, (width - rail - gap - gridSize) / 2);
            statusX = buttonX = left;
            buttonWidth = rail;
            buttonHeight = Math.max(0, Math.min(minControlSize * 2, height - statusHeight - 3 * gap));
            statusY = Math.max(gap, (height - statusHeight - gap - buttonHeight) / 2);
            buttonY = statusY + statusHeight + gap;
            gridX = left + rail + gap;
            gridY = (height - gridSize) / 2;
        } else {
            buttonHeight = Math.max(0, Math.min(minControlSize, height / 4));
            gridSize = Math.max(0, Math.min(width - gap * 2,
                    height - statusHeight - buttonHeight - gap * 4));
            buttonWidth = gridSize;
            statusX = buttonX = gridX = (width - gridSize) / 2;
            statusY = Math.max(gap, (height - statusHeight - buttonHeight - gridSize - gap * 2) / 2);
            buttonY = statusY + statusHeight + gap;
            gridY = buttonY + buttonHeight + gap;
        }
    }
}
