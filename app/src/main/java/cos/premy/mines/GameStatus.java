package cos.premy.mines;

import android.content.Context;
import android.content.SharedPreferences;
import android.os.SystemClock;

import java.util.Vector;

/**
 * Created by premy on 07.11.2017.
 */

public class GameStatus {
    public final ExplosionState explosion = new ExplosionState();
    static final String SETTINGS = "cos.premy.mines.settings";
    static final boolean DEFAULT_NUMBER_CLUES = true;
    private final GameClock clock;
    private boolean gameOver;
    private boolean hasUserWon;
    private int level;
    private int lastLevel;
    private final Vector<LevelSwitchListener> levelSwitchListenerVector;
    private final int numLevels;
    private final Vector<GameEndedListener> gameEndedListenerVector;

    private final SharedPreferences sharedPref;

    public GameStatus(Context context, int numLevels, int level, long elapsed, int outcome) {
        sharedPref = context.getSharedPreferences(SETTINGS, Context.MODE_PRIVATE);
        this.numLevels = numLevels;
        clock = new GameClock(elapsed);
        gameOver = outcome != 0;
        hasUserWon = outcome == 1;
        this.level = Math.max(0, Math.min(numLevels - 1, level));
        lastLevel = this.level;
        levelSwitchListenerVector = new Vector<>();
        gameEndedListenerVector = new Vector<>();

    }

    public static int preferredLayers(Context context) {
        return Math.max(2, Math.min(8, context.getSharedPreferences(SETTINGS, Context.MODE_PRIVATE)
                .getInt("numLevels", 2)));
    }

    public int getNumLevels(){
        return numLevels;
    }

    public boolean getNumberType(){
        return sharedPref.getBoolean("numberType", DEFAULT_NUMBER_CLUES);
    }

    public boolean getColored(){
        return sharedPref.getBoolean("colored", false);
    }

    public boolean getFlood() { return sharedPref.getBoolean("flood", false); }

    public void endGame(boolean hasUserWon){
        if (gameOver) return;
        gameOver = true;
        this.hasUserWon = hasUserWon;
        clock.pause(SystemClock.elapsedRealtime());
        for(GameEndedListener listener : gameEndedListenerVector){
            listener.gameEnded(this);
        }
    }

    public void incrementLevel(){
        lastLevel = level;
        level = (level + 1) % numLevels;
        for(LevelSwitchListener listener : levelSwitchListenerVector){
            listener.levelSwitched(this);
        }
    }

    public void decrementLevel(){
        lastLevel = level;
        level = (numLevels + level - 1) % numLevels;
        for(LevelSwitchListener listener : levelSwitchListenerVector){
            listener.levelSwitched(this);
        }
    }

    public int getLevel(){
        return level;
    }
    public void setLevel(int value){int target=Math.max(0,Math.min(numLevels-1,value));if(target==level)return;lastLevel=level;level=target;for(LevelSwitchListener l:levelSwitchListenerVector)l.levelSwitched(this);}

    public boolean stillPlaying() {
        return !gameOver;
    }

    public void resume() {
        if (stillPlaying()) clock.resume(SystemClock.elapsedRealtime());
        explosion.active(true);
    }

    public void pause() {
        clock.pause(SystemClock.elapsedRealtime());
        explosion.active(false);
    }

    public long elapsedMillis() {
        return clock.elapsed(SystemClock.elapsedRealtime());
    }

    public int outcome() {
        return gameOver ? (hasUserWon ? 1 : 2) : 0;
    }

    public boolean hasUserWon(){
        return hasUserWon;
    }

    public void addLevelSwitchListener(LevelSwitchListener listener){
        levelSwitchListenerVector.add(listener);
    }

    public void addGameEndedListener(GameEndedListener listener){
        gameEndedListenerVector.add(listener);
    }

    public int getLastLevel() {
        return lastLevel;
    }
    public boolean reduceEffects() { return sharedPref.getBoolean("reducedEffects",false); }
    public void triggerExplosion(cos.premy.mines.data.MineCoord cell){explosion.trigger(cell);}
}
