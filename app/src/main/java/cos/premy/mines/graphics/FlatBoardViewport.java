package cos.premy.mines.graphics;
import android.content.Context;
import android.graphics.*;
import android.os.Bundle;
import android.view.*;
import cos.premy.mines.GameStatus;
import cos.premy.mines.MineTheme;
import cos.premy.mines.data.MineCoord;

/** Renderer failure preserves the same session, selection buttons, scans and hints. */
final class FlatBoardViewport extends View implements PlayableViewport {
 private BoardScene scene;private final BoardViewport.Selection selection;private final BoardTouch touch;private boolean active;private final Paint paint=new Paint(3);private float left,top,step;
 FlatBoardViewport(Context c,BoardViewport.Selection selection){super(c);this.selection=selection;touch=new BoardTouch(ViewConfiguration.get(c).getScaledTouchSlop());paint.setTypeface(MineTheme.font(c));}
 public View view(){return this;}public void setStatus(GameStatus s){}public void setScene(BoardScene s){scene=s;touch.cancel();invalidate();}public void setInputActive(boolean a){active=a;touch.cancel();}public void resetCamera(){}public void restoreCamera(Bundle b){}public void saveCamera(Bundle b){}public void onResume(){}public void onPause(){touch.cancel();}public void effectChanged(){invalidate();}
 @Override protected void onDraw(Canvas canvas){super.onDraw(canvas);canvas.drawColor(MineTheme.BACK);if(scene==null)return;step=Math.min((getWidth()-24f)/scene.width,(getHeight()-48f)/scene.height);left=(getWidth()-step*scene.width)/2;top=(getHeight()-step*scene.height)/2;
  for(int row=0;row<scene.height;row++)for(int col=0;col<scene.width;col++){byte value=scene.cell(col,row);if(value==BoardScene.VOID)continue;float x=left+col*step,y=top+row*step;RectF rect=new RectF(x+2,y+2,x+step-2,y+step-2);paint.setStyle(Paint.Style.FILL);paint.setColor(value<=6?0xffbfdae0:0xff244152);canvas.drawRoundRect(rect,4,4,paint);paint.setColor(value==BoardScene.FLAG?MineTheme.GOLD:value==BoardScene.HIT?0xffe96537:0xff112632);paint.setTextSize(step*.43f);paint.setTextAlign(Paint.Align.CENTER);String label=value<=6?Integer.toString(value):"";canvas.drawText(label,x+step/2,y+step*.66f,paint);if(value==BoardScene.FLAG){paint.setStrokeWidth(step*.05f);canvas.drawLine(x+step*.38f,y+step*.24f,x+step*.38f,y+step*.78f,paint);Path flag=new Path();flag.moveTo(x+step*.38f,y+step*.25f);flag.lineTo(x+step*.73f,y+step*.38f);flag.lineTo(x+step*.38f,y+step*.5f);flag.close();canvas.drawPath(flag,paint);}else if(value==BoardScene.HIT){canvas.drawCircle(x+step/2,y+step/2,step*.14f,paint);paint.setStrokeWidth(step*.04f);for(int ray=0;ray<8;ray++){double a=ray*Math.PI/4;canvas.drawLine(x+step/2+(float)Math.cos(a)*step*.18f,y+step/2+(float)Math.sin(a)*step*.18f,x+step/2+(float)Math.cos(a)*step*.29f,y+step/2+(float)Math.sin(a)*step*.29f,paint);}}
   int id=(scene.layer*scene.height+row)*scene.width+col;boolean selected=scene.selectedX==col&&scene.selectedY==row;
   if(selected||scene.hintSources.get(id)||scene.hintTarget==id||id==scene.entry||id==scene.exit){paint.setStyle(Paint.Style.STROKE);paint.setStrokeWidth(4);paint.setColor(selected?MineTheme.CYAN:id==scene.entry?0xff68cf94:MineTheme.GOLD);canvas.drawRoundRect(rect,4,4,paint);}
  }
 }
 @Override public boolean onTouchEvent(MotionEvent e){if(!active)return false;switch(e.getActionMasked()){case MotionEvent.ACTION_DOWN:touch.down(e.getX(),e.getY());break;case MotionEvent.ACTION_MOVE:touch.drag(e.getX(),e.getY());break;case MotionEvent.ACTION_POINTER_DOWN:case MotionEvent.ACTION_POINTER_UP:touch.multiplePointers();break;case MotionEvent.ACTION_CANCEL:touch.cancel();break;case MotionEvent.ACTION_UP:if(touch.up(e.getX(),e.getY())&&scene!=null&&step>0){int x=(int)Math.floor((e.getX()-left)/step),y=(int)Math.floor((e.getY()-top)/step);selection.select(x>=0&&x<scene.width&&y>=0&&y<scene.height&&scene.cell(x,y)!=BoardScene.VOID?new MineCoord(x,y,scene.layer):null);}break;}return true;}
}

