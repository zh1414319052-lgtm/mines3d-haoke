package cos.premy.mines.graphics;
import android.os.Bundle;
import android.view.View;
import cos.premy.mines.GameStatus;
interface PlayableViewport {
 View view();void setStatus(GameStatus status);void setScene(BoardScene scene);void setInputActive(boolean active);
 void resetCamera();void restoreCamera(Bundle state);void saveCamera(Bundle state);void onResume();void onPause();void effectChanged();
}
