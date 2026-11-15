package cos.premy.mines.data;

import cos.premy.mines.GameStatus;
import cos.premy.mines.MyHappyException;

/**
 * Created by premy on 07.11.2017.
 */

public class MinesContainer {
    private final int height;
    private final int width;
    private final int numLevels;
    private final int minesNumber;
    private int minesBlocked;
    /**
     * Increased only if user block correct mine. Not the false one.
     */
    private int minesOkBlocked;
    private int minesOpened;
    private final Mine[][][] mines;
    private boolean factorized;
    private BoardDefinition definition;
    public int wrongFlagActions;
    private static final MineStatus[] CELL_STATES = {
            MineStatus.UNBLOCKED, MineStatus.BLOCKED, MineStatus.OPENED
    };

    public MinesContainer(int N, int M, int numLevels, int minesNumber, int minesBlocked, int minesOkBlocked, int minesOpened){
        this.numLevels = numLevels;
        this.height = N;
        this.width = M;
        this.minesNumber = minesNumber;
        this.minesBlocked = minesBlocked;
        this.minesOkBlocked = minesOkBlocked;
        this.minesOpened = minesOpened;
        definition = new BoardDefinition(BoardDefinition.CLASSIC,N,numLevels,minesNumber,0,System.nanoTime(),"");

        mines = new Mine[numLevels][N][M];
        for(int i = 0; i != numLevels; i++){
            for(int ii = 0; ii != N; ii++){
                for(int iii = 0; iii != M; iii++){
                    mines[i][ii][iii] = new Mine();
                }
            }
        }
        initListeners();
        factorized = false;
    }

    public MinesContainer(int N, int M, int numLevels, int minesNumber){
        this(N, M, numLevels, minesNumber, 0, 0, 0);
    }

    public int getOkBlockedMines(){
        return minesOkBlocked;
    }

    public int getMinesOpened(){
        return minesOpened;
    }

    public int getMinesBlocked(){
        return minesBlocked;
    }

    public int getMinesNumber(){
        return minesNumber;
    }
    public BoardDefinition definition(){return definition;}
    public void configure(BoardDefinition value){if(factorized)throw new IllegalStateException("Generated board");definition=value;}
    public boolean present(int z,int y,int x){return z>=0&&z<numLevels&&y>=0&&y<height&&x>=0&&x<width&&definition.present[definition.index(x,y,z)];}
    public void generate(MineCoord safe){
        if(factorized)return;
        boolean[] layout=definition.mineLayout(definition.index(safe.x,safe.y,safe.z));
        try{for(int i=0;i<layout.length;i++){MineCoord c=definition.coord(i);getMine(c.z,c.y,c.x).setIsReal(layout[i]);}}
        catch(MyHappyException e){throw new IllegalStateException(e);}
        setFactorized();
        wrongFlagActions=minesBlocked-minesOkBlocked;
    }

    private void initListeners() {
        for (int i = 0; i != numLevels; i++) {
            for (int ii = 0; ii != height; ii++) {
                for (int iii = 0; iii != width; iii++) {
                    mines[i][ii][iii].addMineStatusChangedListener(new MineStatusChangedListener() {
                        @Override
                        public void onOpen(GameStatus status, Mine mine) {
                            if(mine.getIsReal()){
                                status.endGame(false);
                            } else{
                                minesOpened++;
                                checkWin(status);
                            }
                        }

                        @Override
                        public void onBlock(GameStatus status, Mine mine) {
                            if(mine.getIsReal()){
                                minesOkBlocked++;
                            }
                            minesBlocked++;
                            if(factorized&&!mine.getIsReal())wrongFlagActions++;
                            checkWin(status);
                        }

                        @Override
                        public void onUnblock(GameStatus status, Mine mine) {
                            if(mine.getIsReal()){
                                minesOkBlocked--;
                            }
                            minesBlocked--;
                            checkWin(status);
                        }
                    });
                }
            }
        }
    }

    private void checkWin(GameStatus status) {
        if(definition.routeWin()){
            boolean[] opened=new boolean[definition.present.length];
            for(int i=0;i<opened.length;i++){MineCoord c=definition.coord(i);opened[i]=present(c.z,c.y,c.x)&&getMine(c.z,c.y,c.x).getStatus()==MineStatus.OPENED&&!getMine(c.z,c.y,c.x).getIsReal();}
            if(factorized&&definition.connected(opened))status.endGame(true);
            return;
        }
        if (factorized && minesOkBlocked == minesBlocked && minesOkBlocked == minesNumber) {
            status.endGame(true);
        }
    }

    private void setMineNeighbors(int z, int y, int x){
        Mine thisMine = mines[z][y][x];
        for(int id:definition.neighbors(definition.index(x,y,z))){MineCoord c=definition.coord(id);thisMine.setNeighborCoord(c);if(getMine(c.z,c.y,c.x).getIsReal())thisMine.setNeighborMineCoord(c);}
    }


    public boolean isRealMine(int z, int y, int x){
        return mines[z][y][x].getIsReal();
    }

    public int getHeight() {
        return height;
    }

    public int getWidth(){
        return width;
    }

    public int getNumLevels(){
        return numLevels;
    }

    public Mine getMine(int z, int y, int x){
        return mines[z][y][x];
    }

    public void setFactorized(){
        if (factorized) return;
        for(int i = 0; i != numLevels; i++){
            for(int ii = 0; ii != height; ii++){
                for(int iii = 0; iii != width; iii++){
                    setMineNeighbors(i,ii,iii);
                    Mine mine = mines[i][ii][iii];
                    mine.setFactorized();
                    if (mine.getIsReal() && mine.getStatus() == MineStatus.BLOCKED) {
                        minesOkBlocked++;
                    }
                }
            }
        }
        factorized = true;
    }

    public boolean getFactorized() {
        return factorized;
    }

    /** One byte per cell; preserves both board generation and the player's visible progress. */
    public byte[] saveCells() {
        byte[] cells = new byte[height * width * numLevels];
        int index = 0;
        for (Mine[][] layer : mines) for (Mine[] row : layer) for (Mine mine : row) {
            int state = mine.getStatus() == MineStatus.BLOCKED ? 1
                    : mine.getStatus() == MineStatus.OPENED ? 2 : 0;
            cells[index] = (byte) (definition.present[index] ? state | (mine.getIsReal() ? 4 : 0) : 8);index++;
        }
        return cells;
    }

    public static MinesContainer restore(int size, int layers, int total, boolean generated, byte[] cells) {
        return restore(new BoardDefinition(BoardDefinition.CLASSIC,size,layers,total,0,System.nanoTime(),""),generated,cells);
    }
    public static MinesContainer restore(BoardDefinition def,boolean generated,byte[] cells){
        int size=def.size,layers=def.layers,total=def.mines;
        if (cells == null || cells.length != size * size * layers) return null;
        int realCount = 0;
        int checkIndex=0;
        for (byte cell : cells) {
            if(!def.present[checkIndex++]){if(cell!=8)return null;continue;}
            if ((cell & ~7) != 0 || (cell & 3) >= CELL_STATES.length) return null;
            if ((cell & 4) != 0) realCount++;
            if (!generated && ((cell & 4) != 0 || (cell & 3) == 2)) return null;
        }
        if (generated && realCount != total) return null;
        MinesContainer board = new MinesContainer(size, size, layers, total);
        board.configure(def);
        int index = 0;
        try {
            for (Mine[][] layer : board.mines) for (Mine[] row : layer) for (Mine mine : row) {
                int cell = cells[index++];
                MineStatus state = CELL_STATES[cell & 3];
                mine.setIsReal((cell & 4) != 0);
                mine.setStatus(state);
                if (state == MineStatus.BLOCKED) board.minesBlocked++;
                if (state == MineStatus.OPENED && !mine.getIsReal()) board.minesOpened++;
            }
        } catch (MyHappyException impossible) {
            throw new IllegalStateException("Restoring a new board", impossible);
        }
        if (generated) board.setFactorized();
        return board;
    }
}
