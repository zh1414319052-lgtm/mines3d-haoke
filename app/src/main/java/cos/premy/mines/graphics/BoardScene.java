package cos.premy.mines.graphics;

import cos.premy.mines.LoadedGame;
import cos.premy.mines.data.Mine;
import cos.premy.mines.data.MineCoord;
import cos.premy.mines.data.MineStatus;

/** Immutable visible board data. Unopened mines are never sent to the renderer. */
final class BoardScene {
    static final byte CLOSED = 7;
    static final byte FLAG = 8;
    static final byte HIT = 9;
    static final byte VOID = 10;
    static final float HALF_CELL = .455f;
    static final float BASE = -.06f;
    static final float LAYER_GAP = 1.50f;

    final int width, height, layers, layer;
    final boolean focused, colorClues, numberClues;
    final int selectedX, selectedY;
    private final byte[] cells;
    private boolean[] mask;
    int entry=-1,exit=-1,hintTarget=-1;
    java.util.BitSet hintSources=new java.util.BitSet();
    java.util.BitSet route=new java.util.BitSet();
    int blastCell=-1;
    java.util.Map<Integer,Integer> owners=new java.util.HashMap<>();
    static final float[][] PLAYER_COLORS={{.1f,.8f,.9f},{1f,.55f,.13f},{.55f,.39f,1f},{.3f,.85f,.35f},{1f,.3f,.55f},{.95f,.82f,.25f}};

    static BoardScene online(int size,int layers,int layer,boolean focus,int selected,byte[] publicCells,java.util.BitSet connected){
        byte[] cells=new byte[size*size];boolean[] mask=new boolean[publicCells.length];
        for(int i=0;i<publicCells.length;i++)mask[i]=publicCells[i]!=VOID;
        System.arraycopy(publicCells,layer*size*size,cells,0,cells.length);
        BoardScene scene=new BoardScene(size,size,layers,layer,focus,true,true,selected<0?-1:selected%size,selected<0?-1:selected/size%size,cells);
        scene.mask=mask;scene.route=(java.util.BitSet)connected.clone();return scene;
    }

    BoardScene(int width, int height, int layers, int layer, boolean focused,
               boolean colorClues, boolean numberClues, int selectedX, int selectedY, byte[] cells) {
        this.width = width;
        this.height = height;
        this.layers = layers;
        this.layer = layer;
        this.focused = focused;
        this.colorClues = colorClues;
        this.numberClues = numberClues;
        this.selectedX = selectedX;
        this.selectedY = selectedY;
        this.cells = cells;
    }

    static BoardScene read(LoadedGame game, boolean focused, MineCoord selected) {
        int width = game.board.getWidth();
        int height = game.board.getHeight();
        int layer = game.status.getLevel();
        byte[] cells = new byte[width * height];
        for (int row = 0; row < height; row++) {
            for (int column = 0; column < width; column++) {
                Mine cell = game.board.getMine(layer, row, column);
                byte value = CLOSED;
                if (!game.board.present(layer,row,column))value=VOID;
                else if (cell.getStatus() == MineStatus.BLOCKED) value = FLAG;
                else if (cell.getStatus() == MineStatus.OPENED) {
                    value = cell.getIsReal() ? HIT : (byte) cell.getNeighbors();
                }
                cells[row * width + column] = value;
            }
        }
        BoardScene scene=new BoardScene(width, height, game.board.getNumLevels(), layer, focused,
                game.status.getColored(), game.status.getNumberType(),
                selected == null ? -1 : selected.x, selected == null ? -1 : selected.y, cells);
        scene.mask=game.definition.present.clone();
        if(game.definition.routeWin()){scene.entry=game.definition.start;scene.exit=game.definition.exit;}
        scene.hintTarget=game.hintTarget;scene.hintSources=(java.util.BitSet)game.hintSources.clone();
        return scene;
    }

    byte cell(int column, int row) { return cells[row * width + column]; }
    float x(int column) { return column + .5f - width * .5f; }
    float z(int row) { return row + .5f - height * .5f; }
    static float layerY(int level) { return level * LAYER_GAP; }
    static float top(byte cell) { return cell == CLOSED || cell == FLAG ? .431f : cell == HIT ? .06f : .123f; }
    boolean present(int level,int row,int column) { return mask==null||mask[(level*height+row)*width+column]; }
    float[] hitPosition() {
        if(blastCell>=0 && blastCell/(width*height)==layer)return new float[]{x(blastCell%width),layerY(layer),z(blastCell/width%height)};
        for(int row=0;row<height;row++)for(int col=0;col<width;col++)if(cell(col,row)==HIT)
            return new float[]{x(col),layerY(layer),z(row)};
        return new float[]{0,layerY(layer),0};
    }
}
