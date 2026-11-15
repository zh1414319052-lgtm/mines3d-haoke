package cos.premy.mines.graphics;

import android.app.ActivityManager;
import android.content.Context;
import android.content.pm.ConfigurationInfo;
import android.content.res.ColorStateList;
import android.content.res.Configuration;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.graphics.drawable.StateListDrawable;
import android.os.Build;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup.LayoutParams;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.util.Locale;

import cos.premy.mines.LoadedGame;
import cos.premy.mines.MineSound;
import cos.premy.mines.MineTheme;
import cos.premy.mines.data.BoardDefinition;
import cos.premy.mines.data.LogicSolver;
import android.app.AlertDialog;
import android.widget.Toast;
import cos.premy.mines.R;
import cos.premy.mines.data.BoardMoves;
import cos.premy.mines.data.Mine;
import cos.premy.mines.data.MineCoord;
import cos.premy.mines.data.MineStatus;

final class Game3dPanel extends LinearLayout {
    private static final int SCREEN = 0xff0a121d;
    private static final int PANEL = 0xff101d2b;
    private static final int TEXT = 0xffedf5fd;
    private static final int MUTED = 0xffa2b8ca;
    private static final int BORDER = 0xff344c63;
    private static final int ACCENT = 0xffa1e5fd;

    private final LoadedGame game;
    private final BoardMoves moves;
    private final PlayableViewport viewport;
    private final TextView layer, flags, time, selectedLabel;
    private final Button overview, focus, open, flag;
    private final Runnable ticker = this::refreshTime;
    private boolean focused;
    private boolean active;
    private MineCoord selected;
    private final MineSound sound;
    private final Runnable checkpoint;
    private TextView objective;
    private Button hint,scan;

    static boolean supported(Context context) {
        ActivityManager manager = (ActivityManager) context.getSystemService(Context.ACTIVITY_SERVICE);
        ConfigurationInfo info = manager == null ? null : manager.getDeviceConfigurationInfo();
        return info != null && info.reqGlEsVersion >= 0x20000;
    }

    Game3dPanel(Context context, LoadedGame game, Bundle state, Runnable onRenderFailure,Runnable checkpoint) {
        this(context,game,state,onRenderFailure,checkpoint,false);
    }
    Game3dPanel(Context context,LoadedGame game,Bundle state,Runnable onRenderFailure,Runnable checkpoint,boolean flat){
        super(context);
        this.game = game;
        this.checkpoint=checkpoint;
        sound = new MineSound(context);
        moves = new BoardMoves(game.board, game.status);
        setBackgroundColor(SCREEN);
        Configuration config = getResources().getConfiguration();
        boolean sideRail = config.orientation == Configuration.ORIENTATION_LANDSCAPE
                && config.screenWidthDp >= 520;
        setOrientation(sideRail ? HORIZONTAL : VERTICAL);

        if (state != null) {
            focused = state.getBoolean("3d.focus");
            int x = state.getInt("3d.selectedX", -1), y = state.getInt("3d.selectedY", -1);
            if (x >= 0 && x < game.board.getWidth() && y >= 0 && y < game.board.getHeight()) {
                selected = new MineCoord(x, y, game.status.getLevel());
            }
        }
        viewport = flat?new FlatBoardViewport(context,this::select):new BoardViewport(context, this::select, onRenderFailure);
        viewport.setStatus(game.status);
        viewport.view().setId(R.id.board_viewport);
        viewport.view().setContentDescription(flat?t("平面兼容棋盘","Flat compatibility board"):context.getString(R.string.board_scene_3d));
        viewport.restoreCamera(state);

        LinearLayout top = strip();
        objective=text(13,MineTheme.GOLD);objective.setId(R.id.board_objective);objective.setPadding(0,0,0,dp(7));top.addView(objective,fullWidth());
        LinearLayout layers = row();
        Button previous = button(R.string.layer_back_arrow, R.id.board_previous, false);
        previous.setContentDescription(context.getString(R.string.previous_layer));
        previous.setOnClickListener(v -> changeLayer(false));
        Button next = button(R.string.layer_next_arrow, R.id.board_next, false);
        next.setContentDescription(context.getString(R.string.next_layer));
        next.setOnClickListener(v -> changeLayer(true));
        layer = text(17, TEXT);
        layer.setId(R.id.board_layer);
        layer.setGravity(Gravity.CENTER);
        layers.addView(previous, new LinearLayout.LayoutParams(dp(48), LayoutParams.WRAP_CONTENT));
        layers.addView(layer, new LinearLayout.LayoutParams(0, LayoutParams.WRAP_CONTENT, 1));
        layers.addView(next, new LinearLayout.LayoutParams(dp(48), LayoutParams.WRAP_CONTENT));
        top.addView(layers, fullWidth());

        LinearLayout modes = row();
        overview = button(R.string.board_overview, R.id.board_overview, false);
        overview.setOnClickListener(v -> setFocused(false));
        focus = button(R.string.board_focus, R.id.board_focus, false);
        focus.setOnClickListener(v -> setFocused(true));
        Button reset = button(R.string.board_reset_camera, R.id.board_reset, false);
        reset.setOnClickListener(v -> viewport.resetCamera());
        addWeighted(modes, overview, 0);
        addWeighted(modes, focus, 6);
        addWeighted(modes, reset, 6);
        LinearLayout.LayoutParams modeParams = fullWidth();
        modeParams.topMargin = dp(7);
        top.addView(modes, modeParams);

        LinearLayout bottom = strip();
        LinearLayout stats = row();
        time = text(14, MUTED);
        time.setId(R.id.board_time);
        flags = text(14, MUTED);
        flags.setId(R.id.board_flags);
        flags.setGravity(Gravity.END | Gravity.CENTER_VERTICAL);
        stats.addView(time, new LinearLayout.LayoutParams(0, LayoutParams.WRAP_CONTENT, 1));
        stats.addView(flags, new LinearLayout.LayoutParams(0, LayoutParams.WRAP_CONTENT, 1));
        bottom.addView(stats, fullWidth());

        selectedLabel = text(14, TEXT);
        selectedLabel.setId(R.id.board_selected);
        selectedLabel.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams labelParams = fullWidth();
        labelParams.topMargin = dp(7);
        labelParams.bottomMargin = dp(8);
        bottom.addView(selectedLabel, labelParams);
        LinearLayout actions = row();
        open = button(R.string.board_open, R.id.board_open, true);
        open.setOnClickListener(v -> {
            if (selected != null && !moves.open(selected).isEmpty()) {
                game.clearHint();
                if(game.status.explosion.cell!=null)sound.startBlast(game.status.explosion);else sound.play("open");
                updateScene();viewport.effectChanged();
            }
        });
        flag = button(R.string.board_add_flag, R.id.board_flag, false);
        flag.setOnClickListener(v -> {
            if (selected != null && moves.toggleFlag(selected)) {game.clearHint();sound.play("flag");updateScene();}
        });
        addWeighted(actions, open, 0);
        addWeighted(actions, flag, 8);
        bottom.addView(actions, fullWidth());
        if(BoardDefinition.SCAN.equals(game.definition.mode)){
            scan=button(R.string.board_open,R.id.board_scan,false);scan.setOnClickListener(v->{int[] split=game.scan(selected);if(split==null){Toast.makeText(getContext(),t("请选择已开的数字格；每局最多扫描两次。","Select an opened number. Each game has two scans."),Toast.LENGTH_SHORT).show();return;}sound.play("select");MineTheme.dialog(new AlertDialog.Builder(getContext()).setTitle(t("扫描结果","Scan result")).setMessage(t("本层雷数：","Mines on this deck: ")+split[0]+t("\n相邻上下层雷数：","\nMines on adjacent decks: ")+split[1]+t("\n扫描不指出具体雷位。","\nThe scan does not reveal mine positions.")).setPositiveButton(R.string.close_dialog,null).create());updateScene();});LinearLayout.LayoutParams p=fullWidth();p.topMargin=dp(7);bottom.addView(scan,p);
        }
        if(BoardDefinition.PUZZLE.equals(game.definition.mode)||BoardDefinition.ESCAPE.equals(game.definition.mode)||BoardDefinition.DAILY.equals(game.definition.mode)){
            hint=button(R.string.board_open,R.id.board_hint,false);hint.setOnClickListener(v->hint());LinearLayout.LayoutParams p=fullWidth();p.topMargin=dp(7);bottom.addView(hint,p);
        }

        if (sideRail) {
            ScrollView scroll = new ScrollView(context);
            scroll.setFillViewport(true);
            scroll.setBackgroundColor(PANEL);
            LinearLayout rail = new LinearLayout(context);
            rail.setOrientation(VERTICAL);
            rail.setGravity(Gravity.CENTER_VERTICAL);
            rail.addView(top, fullWidth());
            rail.addView(bottom, fullWidth());
            scroll.addView(rail, new ScrollView.LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT));
            int railWidth = Math.max(208, Math.min(288, config.screenWidthDp * 2 / 5));
            addView(scroll, new LinearLayout.LayoutParams(dp(railWidth), LayoutParams.MATCH_PARENT));
            addView(viewport.view(), new LinearLayout.LayoutParams(0, LayoutParams.MATCH_PARENT, 1));
        } else {
            addView(top, fullWidth());
            addView(viewport.view(), new LinearLayout.LayoutParams(LayoutParams.MATCH_PARENT, 0, 1));
            addView(bottom, fullWidth());
        }
        updateScene();
    }

    void startSurface() { viewport.onResume(); }
    void stopSurface() { viewport.onPause(); }

    void setActive(boolean active) {
        this.active = active;
        if(active)sound.resume(game.status.explosion);else sound.pause();
        viewport.setInputActive(active);
        refreshTime();
    }

    void save(Bundle state) {
        state.putBoolean("3d.focus", focused);
        if (selected != null) {
            state.putInt("3d.selectedX", selected.x);
            state.putInt("3d.selectedY", selected.y);
        }
        viewport.saveCamera(state);
    }

    private void changeLayer(boolean next) {
        if (!active) return;
        selected = null;
        if (next) game.status.decrementLevel();
        else game.status.incrementLevel();
        sound.play("layer");
        updateScene();
    }

    private void setFocused(boolean value) {
        if (focused == value) return;
        focused = value;
        updateScene();
    }

    private void select(MineCoord cell) {
        if (!game.status.stillPlaying()) return;
        selected = cell;
        if(cell!=null)sound.play("select");
        updateScene();
    }

    private void updateScene() {
        layer.setText("B"+(game.status.getNumLevels()-game.status.getLevel())+" / "+game.status.getNumLevels()+t(" 层"," decks"));
        String title=MineTheme.mode(getContext(),game.definition.mode);
        if(game.definition.routeWin())title+=" · "+MineTheme.level(getContext(),game.definition.mode,game.definition.level)+"\n"+t(new String[]{"相邻层同坐标相通：绿框入口 → 橙框出口","比较不同下行位置，用数字选择安全路线","上、下层被裂隙分开，借中层缺口绕行"}[game.definition.level],new String[]{"Same position connects decks: green entry → amber exit","Compare descent points; use clues to choose a route","Cross the middle-deck gap to bypass the broken decks"}[game.definition.level]);
        else if(BoardDefinition.DAILY.equals(game.definition.mode))title+=" · "+game.definition.day;
        else if(BoardDefinition.PUZZLE.equals(game.definition.mode)||BoardDefinition.FAULT.equals(game.definition.mode))title+=" · "+MineTheme.level(getContext(),game.definition.mode,game.definition.level);
        objective.setText(title);
        flags.setText(getContext().getString(R.string.board_flag_count,
                game.board.getMinesBlocked(), game.board.getMinesNumber()));
        overview.setSelected(!focused);
        focus.setSelected(focused);
        Mine mine = selected == null ? null : game.board.getMine(selected.z, selected.y, selected.x);
        boolean playing = game.status.stillPlaying();
        if(scan!=null){scan.setText(t("扫描 · 剩余 ","Scan · ")+game.scansLeft+" / 2");scan.setEnabled(playing&&mine!=null&&mine.getStatus()==MineStatus.OPENED&&mine.getNeighbors()>0);}
        if(hint!=null){hint.setText(game.pendingHint==null?t("推理提示","Reasoning hint"):t("解释金框线索","Explain highlighted clues"));hint.setEnabled(playing);}
        open.setEnabled(playing && mine != null && mine.getStatus() == MineStatus.UNBLOCKED);
        flag.setEnabled(playing && mine != null && mine.getStatus() != MineStatus.OPENED);
        flag.setText(mine != null && mine.getStatus() == MineStatus.BLOCKED
                ? R.string.board_remove_flag : R.string.board_add_flag);
        selectedLabel.setText(mine == null ? getContext().getString(R.string.board_select_hint)
                : getContext().getString(R.string.board_selected_cell,
                        selected.y + 1, selected.x + 1, cellDescription(mine)));
        viewport.setScene(BoardScene.read(game, focused, selected));
        refreshTime();
        checkpoint.run();
    }
    private String t(String zh,String en){return MineTheme.tr(getContext(),zh,en);}
    private void hint(){
        if(game.pendingHint==null){
            if(!game.beginHint()){Toast.makeText(getContext(),t("当前没有可证明的单步结论。可先查看其他层；提示不会猜测雷位。","No provable next move. Check other decks; hints never guess."),Toast.LENGTH_LONG).show();return;}
            int source=game.hintSources.nextSetBit(0);MineCoord c=game.definition.coord(source<0?game.hintTarget:source);game.status.setLevel(c.z);selected=c;focused=true;updateScene();
            selectedLabel.setText(t("已标出相关格；点击下方按钮查看推理。","Related cells highlighted. Tap below for the reasoning."));return;
        }
        LogicSolver.Hint h=game.pendingHint;MineCoord target=game.definition.coord(h.cell);StringBuilder sources=new StringBuilder();
        for(int id=h.sources.nextSetBit(0);id>=0;id=h.sources.nextSetBit(id+1)){MineCoord c=game.definition.coord(id);if(sources.length()>0)sources.append(" · ");sources.append("B").append(game.definition.layers-c.z).append(" R").append(c.y+1).append(" C").append(c.x+1);}
        String body=(sources.length()==0?t("根据剩余地雷总数，","Using the remaining mine total, "):t("相关数字格：","Number cells: ")+sources+"\n")
                +(h.subset?t("相减排除重复邻格后，","After subtracting the shared neighbours, "):t("扣除已由线索证明的雷后，","After accounting for mines already proved by clues, "))
                +h.unknown+t(" 个候选格中还有 "," candidates contain ")+h.remaining+t(" 个雷。\n"," mines.\n")
                +"B"+(game.definition.layers-target.z)+" R"+(target.y+1)+" C"+(target.x+1)
                +(h.mine?t(" 必须是雷，可以插旗。"," must be a mine. Place a flag."):t(" 必定安全，可取消误旗后开格。"," is safe. Remove any flag and open it."));
        MineTheme.dialog(new AlertDialog.Builder(getContext()).setTitle(t("推理依据","Why this follows")).setMessage(body).setPositiveButton(t("定位结论格","Locate the cell"),(d,w)->{game.status.setLevel(target.z);selected=target;focused=true;updateScene();}).setNegativeButton(R.string.close_dialog,null).create());
    }

    private String cellDescription(Mine mine) {
        if (mine.getStatus() == MineStatus.UNBLOCKED) return getContext().getString(R.string.board_cell_closed);
        if (mine.getStatus() == MineStatus.BLOCKED) return getContext().getString(R.string.board_cell_flagged);
        if (mine.getIsReal()) return getContext().getString(R.string.board_cell_mine);
        return getContext().getString(R.string.board_cell_clue, mine.getNeighbors());
    }

    private void refreshTime() {
        removeCallbacks(ticker);
        long elapsed = game.status.elapsedMillis();
        long seconds = elapsed / 1000;
        String display = seconds >= 3600
                ? String.format(Locale.ROOT, "%d:%02d:%02d", seconds / 3600, seconds / 60 % 60, seconds % 60)
                : String.format(Locale.ROOT, "%02d:%02d", seconds / 60, seconds % 60);
        time.setText(getContext().getString(R.string.board_elapsed, display));
        if (active && game.status.stillPlaying()) postDelayed(ticker, 1000 - elapsed % 1000);
    }

    @Override
    protected void onDetachedFromWindow() {
        removeCallbacks(ticker);
        sound.release();
        super.onDetachedFromWindow();
    }

    private LinearLayout strip() {
        LinearLayout view = new LinearLayout(getContext());
        view.setOrientation(VERTICAL);
        view.setBackgroundColor(PANEL);
        view.setPadding(dp(12), dp(9), dp(12), dp(9));
        return view;
    }

    private LinearLayout row() {
        LinearLayout view = new LinearLayout(getContext());
        view.setGravity(Gravity.CENTER_VERTICAL);
        return view;
    }

    private TextView text(float size, int color) {
        TextView view = new TextView(getContext());
        view.setTextSize(size);
        view.setTextColor(color);
        view.setTypeface(MineTheme.font(getContext()));
        return view;
    }

    private Button button(int label, int id, boolean primary) {
        Button view = new Button(getContext());
        view.setId(id);
        view.setText(label);
        view.setTypeface(MineTheme.font(getContext()));
        view.setTextSize(14);
        view.setAllCaps(false);
        view.setMinWidth(0);
        view.setMinimumWidth(0);
        view.setMinHeight(dp(48));
        view.setMinimumHeight(dp(48));
        view.setPadding(dp(4), dp(4), dp(4), dp(4));
        int[][] states = {{-android.R.attr.state_enabled}, {android.R.attr.state_selected}, {}};
        int[] colors = {0xff8196a8, ACCENT, primary ? 0xff102333 : TEXT};
        view.setTextColor(new ColorStateList(states, colors));
        StateListDrawable background = new StateListDrawable();
        background.addState(states[0], rounded(0xff182738, 0xff26394b));
        background.addState(states[1], rounded(0xff203b50, 0xff78cbe8));
        background.addState(states[2], rounded(primary ? ACCENT : 0xff1b2c3d, primary ? ACCENT : BORDER));
        if (Build.VERSION.SDK_INT >= 21) {
            view.setStateListAnimator(null);
            view.setBackground(new RippleDrawable(ColorStateList.valueOf(0x38ffffff),
                    background, rounded(Color.WHITE, Color.WHITE)));
        } else {
            view.setBackground(background);
        }
        return view;
    }

    private GradientDrawable rounded(int fill, int border) {
        GradientDrawable shape = new GradientDrawable();
        shape.setColor(fill);
        shape.setCornerRadius(dp(9));
        shape.setStroke(dp(1), border);
        return shape;
    }

    private void addWeighted(LinearLayout row, View view, int margin) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, LayoutParams.WRAP_CONTENT, 1);
        params.leftMargin = dp(margin);
        row.addView(view, params);
    }

    private LinearLayout.LayoutParams fullWidth() {
        return new LinearLayout.LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT);
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
