package cos.premy.mines.graphics;

import android.annotation.SuppressLint;
import android.content.Context;
import android.opengl.GLSurfaceView;
import android.os.Bundle;
import android.view.MotionEvent;
import android.view.ViewConfiguration;

import cos.premy.mines.data.MineCoord;
import cos.premy.mines.GameStatus;

final class BoardViewport extends GLSurfaceView implements PlayableViewport {
    public android.view.View view(){return this;}
    interface Selection {
        void select(MineCoord cell);
    }

    private final BoardRenderer renderer;
    private final BoardTouch touch;
    private final float sensitivity;
    private final Selection selection;
    private BoardScene scene;
    private boolean active;
    private float yaw = BoardCamera.DEFAULT_YAW;
    private float pitch = BoardCamera.DEFAULT_PITCH;
    private float zoom = 1;
    private float panX,panZ,multiX,multiY,multiSpan;
    private GameStatus status;
    private final Runnable animate = () -> { submit(); scheduleEffect(); };

    BoardViewport(Context context, Selection selection, Runnable onFailure) {
        super(context);
        this.selection = selection;
        sensitivity = .30f / getResources().getDisplayMetrics().density;
        touch = new BoardTouch(ViewConfiguration.get(context).getScaledTouchSlop());
        setEGLContextClientVersion(2);
        setEGLConfigChooser(true);
        setPreserveEGLContextOnPause(true);
        renderer = new BoardRenderer(context, () -> post(onFailure));
        setRenderer(renderer);
        setRenderMode(RENDERMODE_WHEN_DIRTY);
    }

    public void setScene(BoardScene scene) {
        // Remote cell updates must not interrupt an ongoing orbit/pinch. Layer/view changes do.
        if(this.scene==null||this.scene.layer!=scene.layer||this.scene.focused!=scene.focused||this.scene.width!=scene.width)touch.cancel();
        this.scene = scene;
        submit();
    }

    public void setInputActive(boolean active) {
        this.active = active;
        if (!active) touch.cancel();
        removeCallbacks(animate);
        if(active) { submit(); scheduleEffect(); }
    }

    public void resetCamera() {
        touch.cancel();
        yaw = BoardCamera.DEFAULT_YAW;
        pitch = BoardCamera.DEFAULT_PITCH;
        zoom = 1;
        panX=panZ=0;
        submit();
    }

    public void restoreCamera(Bundle state) {
        if (state == null) return;
        yaw = clamp(state.getFloat("3d.yaw", BoardCamera.DEFAULT_YAW), 0, 360);
        pitch = clamp(state.getFloat("3d.pitch", BoardCamera.DEFAULT_PITCH), 23, 83);
        zoom = clamp(state.getFloat("3d.zoom", 1), .72f, 4f);
        panX=clamp(state.getFloat("3d.panX"),-8,8);panZ=clamp(state.getFloat("3d.panZ"),-8,8);
    }

    public void saveCamera(Bundle state) {
        state.putFloat("3d.yaw", yaw);
        state.putFloat("3d.pitch", pitch);
        state.putFloat("3d.zoom", zoom);
        state.putFloat("3d.panX",panX);state.putFloat("3d.panZ",panZ);
    }

    @Override
    protected void onSizeChanged(int w, int h, int oldw, int oldh) {
        super.onSizeChanged(w, h, oldw, oldh);
        touch.cancel();
        submit();
    }

    @SuppressLint("ClickableViewAccessibility") // The scene selects a spatial cell; actions use native buttons.
    @Override
    public boolean onTouchEvent(MotionEvent event) {
        if (!active) return false;
        float x = event.getX(), y = event.getY();
        switch (event.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
                multiSpan=0;
                touch.down(x, y);
                return true;
            case MotionEvent.ACTION_POINTER_DOWN:
                multiSpan=0;
                touch.multiplePointers();
                return true;
            case MotionEvent.ACTION_POINTER_UP:
                multiSpan=0;
                touch.multiplePointers();
                return true;
            case MotionEvent.ACTION_MOVE:
                if(event.getPointerCount()==2&&scene!=null){
                    float mx=(event.getX(0)+event.getX(1))*.5f,my=(event.getY(0)+event.getY(1))*.5f;
                    float span=(float)Math.hypot(event.getX(1)-event.getX(0),event.getY(1)-event.getY(0));
                    float dx=multiSpan>0?mx-multiX:0,dy=multiSpan>0?my-multiY:0;
                    if(multiSpan>1&&span>1)zoom=clamp(zoom*span/multiSpan,.72f,4f);
                    multiX=mx;multiY=my;multiSpan=span;
                    float co=(float)Math.cos(Math.toRadians(yaw)),si=(float)Math.sin(Math.toRadians(yaw)),factor=scene.width*1.6f/Math.max(1,getWidth())/zoom;
                    panX=clamp(panX-(dx*co+dy*si)*factor,-scene.width*.6f,scene.width*.6f);panZ=clamp(panZ+(dx*si-dy*co)*factor,-scene.height*.6f,scene.height*.6f);submit();return true;
                }
                if (touch.drag(x, y)) {
                    yaw = (yaw - touch.dx * sensitivity + 360) % 360;
                    if (yaw < 0) yaw += 360;
                    pitch = clamp(pitch + touch.dy * sensitivity, 23, 83);
                    submit();
                }
                return true;
            case MotionEvent.ACTION_UP:
                if (touch.up(x, y)) {
                    BoardRenderer.Frame frame = renderer.drawn;
                    if (frame != null && frame == renderer.next) {
                        selection.select(renderer.pick(frame,x,y));
                    }
                }
                return true;
            case MotionEvent.ACTION_CANCEL:
                touch.cancel();
                return true;
            default:
                return true;
        }
    }

    private void submit() {
        if (scene == null || getWidth() <= 0 || getHeight() <= 0) return;
        float effect = status != null && status.explosion.cell != null ? status.explosion.elapsed()/1000f : -1;
        if(status!=null&&status.explosion.cell!=null&&status.explosion.cell.z!=scene.layer)effect=-1;
        boolean reduced=status!=null&&status.reduceEffects();
        float shake=effect>=0&&effect<.3f&&!reduced?(float)(Math.sin(effect*91)*.45*Math.exp(-effect*13)):0;
        BoardCamera camera = new BoardCamera(scene, getWidth(), getHeight(), yaw+shake, pitch+shake*.6f, zoom,panX,panZ);
        int turn = Math.round(yaw / 90) % 4;
        renderer.next = new BoardRenderer.Frame(scene, camera, turn, effect, reduced);
        requestRender();
    }
    public void setStatus(GameStatus status){this.status=status;}
    private void scheduleEffect(){removeCallbacks(animate);if(active&&status!=null&&status.explosion.animating())postOnAnimation(animate);}
    public void effectChanged(){submit();scheduleEffect();}
    @Override protected void onDetachedFromWindow(){removeCallbacks(animate);super.onDetachedFromWindow();}

    private static float clamp(float value, float low, float high) {
        return Math.max(low, Math.min(high, value));
    }
}
