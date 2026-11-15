package cos.premy.mines.graphics;

import android.app.*;
import android.content.*;
import android.graphics.Bitmap;
import android.os.*;
import android.view.*;
import android.view.accessibility.*;
import android.widget.*;
import cos.premy.mines.*;
import cos.premy.mines.online.*;
import org.json.*;
import java.io.*;
import java.lang.reflect.*;
import java.util.*;

/** Debug instrumentation, not an exported app component or network oracle.
 * Desktop test driver supplies UI actions through an ADB-owned file. Output is public state only.
 */
public final class OnlineChecks extends Instrumentation {
 private OnlineActivity activity;private Bundle args;private File output;private boolean done;
 @Override public void onCreate(Bundle a){super.onCreate(a);args=a;start();}
 @Override public void onStart(){output=new File(getTargetContext().getFilesDir(),"qa-online");output.mkdirs();
  try{String origin=args.getString("origin","http://127.0.0.1:18769");
   launch(origin);String last="";long until=SystemClock.elapsedRealtime()+1800000;
   while(!done&&SystemClock.elapsedRealtime()<until){try{
    File f=new File(args.getString("commands"));JSONObject cmd=new JSONObject(read(f));String id=cmd.getString("id");
    if(!id.equals(last)){JSONObject result=new JSONObject().put("id",id);try{execute(cmd);result.put("ok",true);}catch(Throwable ex){result.put("ok",false).put("error",ex.toString());}
     result.put("state",snapshot());write(new File(output,"result.json"),result.toString());last=id;}
   }catch(Exception ignored){}SystemClock.sleep(100);}
   Bundle b=new Bundle();b.putString("stream","Online UI driver stopped\n");finish(Activity.RESULT_OK,b);
  }catch(Throwable ex){Bundle b=new Bundle();b.putString("stream",ex.toString());finish(Activity.RESULT_CANCELED,b);}
 }
 private Object field(Object o,String n){try{Field f=o.getClass().getDeclaredField(n);f.setAccessible(true);return f.get(o);}catch(Exception ex){throw new IllegalStateException(ex);}}
 private OnlineBoardPanel panel(){return (OnlineBoardPanel)field(activity,"board");}
 private BoardViewport viewport(){return (BoardViewport)field(panel(),"viewport");}
 private BoardRenderer renderer(){return (BoardRenderer)field(viewport(),"renderer");}
 private void launch(String origin){activity=(OnlineActivity)startActivitySync(new Intent(getTargetContext(),OnlineActivity.class).putExtra("qaOnlineOrigin",origin).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));waitForIdleSync();SystemClock.sleep(400);}
 private void execute(JSONObject c)throws Exception{String op=c.getString("op");
  if(op.equals("login")){runOnMainSync(()->{((EditText)field(activity,"email")).setText(c.optString("email"));((EditText)field(activity,"password")).setText(c.optString("password"));});clickText("密码登录","Sign in with password");}
  else if(op.equals("click"))clickText(c.getString("zh"),c.optString("en",c.getString("zh")));
  else if(op.equals("input")){String value=c.getString("text");runOnMainSync(()->{AccessibilityNodeInfo root=getUiAutomation().getRootInActiveWindow();input(root,value);});}
  else if(op.equals("select"))select(c.getInt("cell"));
  else if(op.equals("choose")){List<AccessibilityNodeInfo> spinners=new ArrayList<>();findClass(getUiAutomation().getRootInActiveWindow(),"android.widget.Spinner",spinners);if(!spinners.get(c.getInt("index")).performAction(AccessibilityNodeInfo.ACTION_CLICK))throw new AssertionError("Spinner not clickable");SystemClock.sleep(150);clickText(c.getString("text"),c.optString("en",c.getString("text")));}
  else if(op.equals("perf"))performance(c.optInt("seconds",720));
  else if(op.equals("home")){getTargetContext().startActivity(new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK));}
  else if(op.equals("resume")){getTargetContext().startActivity(new Intent(getTargetContext(),OnlineActivity.class).putExtra("qaOnlineOrigin",args.getString("origin","http://127.0.0.1:18769")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK|Intent.FLAG_ACTIVITY_SINGLE_TOP));SystemClock.sleep(600);}
  else if(op.equals("recreate")){ActivityMonitor monitor=addMonitor(OnlineActivity.class.getName(),null,false);runOnMainSync(()->activity.recreate());Activity next=waitForMonitorWithTimeout(monitor,12000);removeMonitor(monitor);if(!(next instanceof OnlineActivity))throw new AssertionError("Recreation failed");activity=(OnlineActivity)next;SystemClock.sleep(600);}
  else if(op.equals("pinch"))pinch();
  else if(op.equals("shot")){Bitmap b=getUiAutomation().takeScreenshot();try(FileOutputStream out=new FileOutputStream(new File(output,c.optString("name","screen")+".png"))){b.compress(Bitmap.CompressFormat.PNG,100,out);}finally{b.recycle();}}
  else if(op.equals("back"))sendKeyDownUpSync(KeyEvent.KEYCODE_BACK);
  else if(op.equals("stop"))done=true;
  else if(!op.equals("state"))throw new IllegalArgumentException("Unknown UI operation");
  waitForIdleSync();SystemClock.sleep(c.optInt("wait",250));
 }
 private void clickText(String zh,String en){long until=SystemClock.elapsedRealtime()+6000;while(SystemClock.elapsedRealtime()<until){AccessibilityNodeInfo root=getUiAutomation().getRootInActiveWindow();if(root!=null){for(String name:new String[]{zh,en})for(AccessibilityNodeInfo n:root.findAccessibilityNodeInfosByText(name)){if(!n.isEnabled())continue;CharSequence text=n.getText();if(text!=null&&(text.toString().equals(name)||text.toString().startsWith(name+"\n"))&&n.performAction(AccessibilityNodeInfo.ACTION_CLICK))return;}}SystemClock.sleep(150);}throw new AssertionError("Button not available: "+zh);}
 private boolean input(AccessibilityNodeInfo node,String value){if(node==null)return false;if(node.isEditable()){Bundle b=new Bundle();b.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE,value);return node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT,b);}for(int i=0;i<node.getChildCount();i++)if(input(node.getChild(i),value))return true;return false;}
 private void findClass(AccessibilityNodeInfo node,String name,List<AccessibilityNodeInfo> out){if(node==null)return;if(name.contentEquals(node.getClassName()))out.add(node);for(int i=0;i<node.getChildCount();i++)findClass(node.getChild(i),name,out);}
 private void performance(int seconds)throws Exception{
  if(seconds<600||seconds>900)throw new IllegalArgumentException("Performance sample must last 10–15 minutes");frame();BoardRenderer r=renderer();long start=SystemClock.elapsedRealtime(),frames=(long)field(r,"frames");JSONArray samples=new JSONArray();PowerManager power=(PowerManager)getTargetContext().getSystemService(Context.POWER_SERVICE);
  runOnMainSync(()->viewport().setRenderMode(android.opengl.GLSurfaceView.RENDERMODE_CONTINUOUSLY));long checkpoint=0;
  try{while(SystemClock.elapsedRealtime()-start<seconds*1000L){int[] p=new int[2];runOnMainSync(()->viewport().getLocationOnScreen(p));float x=p[0]+viewport().getWidth()*.45f,y=p[1]+viewport().getHeight()*.5f;long down=SystemClock.uptimeMillis();for(int step=0;step<12;step++){int kind=step==0?MotionEvent.ACTION_DOWN:step==11?MotionEvent.ACTION_UP:MotionEvent.ACTION_MOVE;MotionEvent ev=MotionEvent.obtain(down,SystemClock.uptimeMillis(),kind,x+step*6,y+step*2,0);sendPointerSync(ev);ev.recycle();SystemClock.sleep(20);}SystemClock.sleep(550);long elapsed=SystemClock.elapsedRealtime()-start;
   if(elapsed>=checkpoint){checkpoint+=60000;JSONObject sample=new JSONObject().put("elapsed_ms",elapsed).put("rendered_frames",(long)field(r,"frames")-frames).put("pss_kb",android.os.Debug.getPss()).put("thermal",Build.VERSION.SDK_INT>=29?power.getCurrentThermalStatus():-1).put("worst_render_cpu_ms",((long)field(r,"worstNanos"))/1000000.0);samples.put(sample);write(new File(output,"perf.json"),samples.toString());}
  }}finally{runOnMainSync(()->viewport().setRenderMode(android.opengl.GLSurfaceView.RENDERMODE_WHEN_DIRTY));}
  long elapsed=SystemClock.elapsedRealtime()-start;samples.put(new JSONObject().put("elapsed_ms",elapsed).put("rendered_frames",(long)field(r,"frames")-frames).put("cadence_fps",((long)field(r,"frames")-frames)*1000.0/elapsed).put("pss_kb",android.os.Debug.getPss()).put("thermal",Build.VERSION.SDK_INT>=29?power.getCurrentThermalStatus():-1).put("note","GLES rendering cadence under continuous stress; not a display-present FPS measurement"));write(new File(output,"perf.json"),samples.toString());
 }
 private JSONObject snapshot()throws Exception{final JSONObject[] out={null};runOnMainSync(()->{try{JSONObject j=new JSONObject().put("room",field(activity,"room")).put("uid",field(activity,"uid")).put("loading",field(activity,"loading"));Object m=field(activity,"match");if(m!=null)j.put("match",new JSONObject(m.toString()));if(field(activity,"roomState")!=null)j.put("lobby",new JSONObject(field(activity,"roomState").toString()));if(panel()!=null){Bundle b=new Bundle();panel().save(b);JSONObject cam=new JSONObject();for(String k:b.keySet())cam.put(k,b.get(k));j.put("view",cam);j.put("selected",field(panel(),"selected"));GameStatus s=(GameStatus)field(panel(),"status");j.put("blastAge",s.explosion.elapsed());j.put("soundEnabled",field(field(panel(),"sound"),"enabled"));}out[0]=j;}catch(Exception ex){throw new IllegalStateException(ex);}});return out[0];}
 private void frame(){long until=SystemClock.elapsedRealtime()+10000;while(SystemClock.elapsedRealtime()<until){if(panel()!=null&&renderer().drawn!=null&&renderer().drawn==renderer().next){SystemClock.sleep(30);return;}SystemClock.sleep(30);}throw new AssertionError("No stable GLES frame");}
 private void select(int id){int n=((JSONObject)field(activity,"match")).optInt("size"),z=id/(n*n);while((int)field(panel(),"layer")!=z){clickText("›","›");frame();}frame();BoardRenderer.Frame f=renderer().drawn;float[] m=f.camera.viewProjection;int cx=id%n,cy=id/n%n;float x=f.scene.x(cx),y=BoardScene.layerY(z)+BoardScene.top(f.scene.cell(cx,cy)),zz=f.scene.z(cy),w=m[3]*x+m[7]*y+m[11]*zz+m[15],px=(m[0]*x+m[4]*y+m[8]*zz+m[12])/w,py=(m[1]*x+m[5]*y+m[9]*zz+m[13])/w;int[] p=new int[2];runOnMainSync(()->viewport().getLocationOnScreen(p));touch(p[0]+(px+1)*f.camera.width/2,p[1]+(1-py)*f.camera.height/2);if((int)field(panel(),"selected")!=id)throw new AssertionError("Projected pick mismatch "+id);}
 private void touch(float x,float y){long began=SystemClock.uptimeMillis();for(int action:new int[]{MotionEvent.ACTION_DOWN,MotionEvent.ACTION_UP}){MotionEvent e=MotionEvent.obtain(began,SystemClock.uptimeMillis(),action,x,y,0);sendPointerSync(e);e.recycle();SystemClock.sleep(30);}waitForIdleSync();}
 private void pinch(){frame();int[] p=new int[2];runOnMainSync(()->viewport().getLocationOnScreen(p));float cx=p[0]+viewport().getWidth()*.5f,cy=p[1]+viewport().getHeight()*.5f;long began=SystemClock.uptimeMillis();
  for(int step=0;step<23;step++){int count=step==0||step==22?1:2,action=step==0?0:step==1?5|(1<<8):step==21?6|(1<<8):step==22?1:2;float radius=60+Math.min(step,20)*3,shift=Math.max(0,step-10)*3;MotionEvent.PointerProperties[] props=new MotionEvent.PointerProperties[count];MotionEvent.PointerCoords[] coords=new MotionEvent.PointerCoords[count];for(int i=0;i<count;i++){props[i]=new MotionEvent.PointerProperties();props[i].id=i;props[i].toolType=MotionEvent.TOOL_TYPE_FINGER;coords[i]=new MotionEvent.PointerCoords();coords[i].x=cx+(i==0?-radius:radius)+shift;coords[i].y=cy;coords[i].pressure=1;coords[i].size=1;}MotionEvent e=MotionEvent.obtain(began,SystemClock.uptimeMillis(),action,count,props,coords,0,0,1,1,0,0,InputDevice.SOURCE_TOUCHSCREEN,0);sendPointerSync(e);e.recycle();SystemClock.sleep(20);}waitForIdleSync();frame();}
 private String read(File file)throws IOException{try(InputStream in=new FileInputStream(file);ByteArrayOutputStream out=new ByteArrayOutputStream()){byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1)out.write(b,0,n);return out.toString("UTF-8");}}
 private void write(File file,String data)throws IOException{try(FileOutputStream out=new FileOutputStream(file)){out.write(data.getBytes("UTF-8"));}}
}
