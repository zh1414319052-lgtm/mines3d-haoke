package cos.premy.mines.graphics;

import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.widget.FrameLayout;
import android.widget.Toast;

import cos.premy.mines.GameStatus;
import cos.premy.mines.LoadedGame;
import cos.premy.mines.LocalizedActivity;
import cos.premy.mines.R;
import cos.premy.mines.ReviewReminder;
import cos.premy.mines.SystemBarsPadding;
import cos.premy.mines.ShowcaseBoard;
import cos.premy.mines.GameSetup;
import cos.premy.mines.SessionStore;
import cos.premy.mines.MineTheme;
import cos.premy.mines.data.BoardDefinition;

public class GameActivity extends LocalizedActivity {
    private LoadedGame game;
    private MinesView minesView;
    private Game3dPanel game3d;
    private FrameLayout boardRoot;
    private boolean started, resumed;
    private AlertDialog result;
    private float previousRecord = -1;
    private boolean newRecord;
    private boolean inspecting;
    private final Runnable resultTask=this::showResultWhenReady;

    public static Intent newIntent(Context context, int size, int layers, int mines) {
        return newIntent(context,GameSetup.create(BoardDefinition.CLASSIC,size,layers,mines,0));
    }
    public static Intent newIntent(Context context,BoardDefinition definition){Bundle b=new Bundle();GameSetup.save(definition,b);return new Intent(context,GameActivity.class).putExtras(b);}

    public static boolean supports3d(Context context) {
        return Game3dPanel.supported(context);
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Intent intent = getIntent();
        if(savedInstanceState==null&&intent.getBooleanExtra("resumeSession",false))savedInstanceState=SessionStore.read(this);
        Bundle config=savedInstanceState!=null&&savedInstanceState.containsKey("definitionVersion")?savedInstanceState:intent.getExtras();
        int size = config==null?0:config.getInt("size",0);
        int layers = config==null?0:config.getInt("layers",0);
        int mines = config==null?0:config.getInt("mines",0);
        if (size < 5 || size > 15 || layers < 2 || layers > 8
                || mines <= 0 || mines >= size * size * layers) {
            finish();
            return;
        }
        if(savedInstanceState==null && intent.getBooleanExtra("showcase",false)
                && (getApplicationInfo().flags & android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE)!=0){
            size=5;layers=2;mines=8;savedInstanceState=ShowcaseBoard.state();
        }
        try{game = new LoadedGame(this, GameSetup.read(config,size,layers,mines), savedInstanceState);}
        catch(IllegalArgumentException corrupt){Toast.makeText(this,MineTheme.tr(this,"存档版本不兼容，请从首页重新开局。","This save is incompatible. Start a new game from the menu."),Toast.LENGTH_LONG).show();finish();return;}
        inspecting=savedInstanceState!=null&&savedInstanceState.getBoolean("inspecting");
        if (savedInstanceState != null && !game.status.stillPlaying()) {
            previousRecord = savedInstanceState.getFloat("previousRecord", -1);
            newRecord = savedInstanceState.getBoolean("newRecord");
        }
        setTitle(R.string.app_name);
        setContentView(R.layout.activity_game);
        SystemBarsPadding.apply(this);
        boardRoot = findViewById(R.id.game_board);
        if (supports3d(this)) {
            game3d = new Game3dPanel(this, game, savedInstanceState, this::fallbackAfterRenderFailure,this::checkpoint);
            boardRoot.addView(game3d, boardLayout());
        } else {
            showFlatBoard();
        }
        game.status.addGameEndedListener(this::gameEnded);
    }

    private FrameLayout.LayoutParams boardLayout() {
        return new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT);
    }

    private void showFlatBoard() {
        Bundle state=new Bundle();game.save(state);
        game3d=new Game3dPanel(this,game,state,()->{},this::checkpoint,true);
        boardRoot.addView(game3d,boardLayout());game3d.setActive(resumed);
    }

    private void fallbackAfterRenderFailure() {
        if (game3d == null || isFinishing() || isDestroyed()) return;
        Bundle state=new Bundle();game.save(state);game3d.save(state);
        game3d.setActive(false);
        if (started) game3d.stopSurface();
        boardRoot.removeView(game3d);
        game3d = null;
        game3d=new Game3dPanel(this,game,state,()->{},this::checkpoint,true);boardRoot.addView(game3d,boardLayout());game3d.setActive(resumed);
        Toast.makeText(this, R.string.board_renderer_fallback, Toast.LENGTH_LONG).show();
    }

    @Override
    protected void onStart() {
        super.onStart();
        started = true;
        if (game3d != null) game3d.startSurface();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (game == null) return;
        resumed = true;
        game.status.resume();
        if (game3d != null) game3d.setActive(true);
        if (minesView != null) minesView.setActive(true);
        if (!game.status.stillPlaying()) showResultWhenReady();
    }

    @Override
    protected void onPause() {
        if (game != null) {
            resumed = false;
            boardRoot.removeCallbacks(resultTask);
            game.status.pause();
            if (game3d != null) game3d.setActive(false);
            if (minesView != null) minesView.setActive(false);
            checkpoint();
        }
        super.onPause();
    }

    @Override
    protected void onStop() {
        started = false;
        if (game3d != null) game3d.stopSurface();
        super.onStop();
    }

    @Override
    protected void onSaveInstanceState(Bundle state) {
        super.onSaveInstanceState(state);
        if (game != null) {
            game.save(state);
            if (game3d != null) game3d.save(state);
            state.putFloat("previousRecord", previousRecord);
            state.putBoolean("newRecord", newRecord);
            state.putBoolean("inspecting", inspecting);
        }
    }
    private void checkpoint(){if(game==null)return;Bundle state=new Bundle();game.save(state);if(game3d!=null)game3d.save(state);state.putBoolean("inspecting",inspecting);state.putFloat("previousRecord",previousRecord);state.putBoolean("newRecord",newRecord);SessionStore.save(this,state);}

    @Override
    protected void onDestroy() {
        if (result != null) {
            result.setOnDismissListener(null);
            result.dismiss();
        }
        super.onDestroy();
    }

    private void gameEnded(GameStatus status) {
        String preferenceName = GameSetup.recordKey(game.definition);
        SharedPreferences records = getSharedPreferences(preferenceName, MODE_PRIVATE);
        previousRecord = records.getFloat("lowestTime", -1);
        double elapsed = status.elapsedMillis() / 1000.0;
        if (status.hasUserWon()) {
            ReviewReminder.setReadyForReview(this);
            newRecord = previousRecord < 0 || previousRecord > elapsed;
            if (newRecord) records.edit().putFloat("lowestTime", (float) elapsed).apply();
            getSharedPreferences("mine-records",0).edit().putBoolean(game.definition.mode+"."+game.definition.level,true).apply();
        }
        records.edit().putLong("lastElapsed",status.elapsedMillis()).putInt("lastWrongFlags",game.board.wrongFlagActions).putInt("lastHints",game.hintsUsed).putInt("lastOutcome",status.outcome()).apply();
        showResultWhenReady();
    }

    private void showResultWhenReady(){
        if(!resumed||inspecting||isFinishing())return;
        boardRoot.removeCallbacks(resultTask);
        long remaining=game.status.explosion.cell==null?0:6000-game.status.explosion.elapsed();
        if(remaining>0){boardRoot.postDelayed(resultTask,Math.min(remaining,500));return;}
        showResult();
    }

    private void showResult() {
        if (result != null || isFinishing()) return;
        boolean won = game.status.hasUserWon();
        StringBuilder message = new StringBuilder(getString(won
                ? R.string.you_have_won : R.string.you_have_lost));
        message.append(getString(R.string.game_ended_stats, game.board.getOkBlockedMines(),
                game.board.getMinesBlocked(), game.board.getMinesOpened(), game.board.getMinesNumber()));
        message.append(getString(R.string.game_time, game.status.elapsedMillis() / 1000.0));
        if(game.definition.routeWin()&&won)message.append(MineTheme.tr(this,"\n入口与最底层出口已连通。","\nThe entrance is connected to the deepest exit."));
        message.append(MineTheme.tr(this,"\n误标次数：","\nIncorrect flag placements: ")).append(game.board.wrongFlagActions).append(MineTheme.tr(this," · 提示："," · Hints: ")).append(game.hintsUsed);
        if(BoardDefinition.DAILY.equals(game.definition.mode))message.append("\n").append(game.definition.day).append(MineTheme.tr(this," · 重试保持同图"," · Retry keeps this board"));
        if (newRecord) message.append(getString(R.string.new_record));
        if (previousRecord >= 0) message.append(getString(R.string.last_record, previousRecord));
        result = new AlertDialog.Builder(this)
                .setTitle(won ? R.string.game_won : R.string.game_over)
                .setMessage(message.toString())
                .setPositiveButton(R.string.play_again, (dialog,which)->retry())
                .setNegativeButton(R.string.back_to_mine_menu,(dialog,which)->finish())
                .setNeutralButton(R.string.inspect_board,(dialog,which)->inspecting=true)
                .create();
        result.setOnDismissListener(dialog -> result=null);
        MineTheme.dialog(result);
    }
    private void retry(){BoardDefinition d=game.definition;if(!d.fixedStart())d=GameSetup.create(d.mode,d.size,d.layers,d.mines,d.level);Intent retry=newIntent(this,d);if(getIntent().getBooleanExtra("showcase",false))retry.putExtra("showcase",true);finish();startActivity(retry);}

}
