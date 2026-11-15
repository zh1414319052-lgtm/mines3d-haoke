package cos.premy.mines.graphics;
import android.content.res.AssetManager;
import cos.premy.mines.data.MineCoord;
import java.io.FileInputStream;
import java.util.Arrays;
import org.junit.Test;
import static org.junit.Assert.*;
import static org.mockito.Mockito.*;
public class MineAssetTest {
 private MineArt art()throws Exception{AssetManager a=mock(AssetManager.class);when(a.open("mine/scene.m3d")).thenAnswer(inv->new FileInputStream("src/main/assets/mine/scene.m3d"));return new MineArt(a);}
 @Test public void packagedGeometryUsesMobileLodAndExactVisiblePicking()throws Exception{MineArt art=art();for(int size:new int[]{5,15}){byte[] cells=new byte[size*size];Arrays.fill(cells,BoardScene.CLOSED);BoardScene scene=new BoardScene(size,size,8,3,true,false,true,-1,-1,cells);MineMesh mesh=new MineMesh(art);for(float yaw:new float[]{36,89,179,269,315}){BoardCamera camera=new BoardCamera(scene,1080,1400,yaw,43,1);int walls=(camera.eyePosition()[0]<0?1:0)|(camera.eyePosition()[2]<0?2:0);mesh.update(scene,Math.round(yaw/90)%4,walls);assertTrue(mesh.cells.count>0);if(size==15)assertTrue(mesh.cells.count<400000);for(int[] point:new int[][]{{0,0},{size-1,0},{0,size-1},{size-1,size-1},{size/2,size/2}}){float[] p=project(camera,scene.x(point[0]),BoardScene.layerY(3)+.432f,scene.z(point[1]));MineCoord pick=camera.pickVisible(scene,p[0],p[1],art,mesh);assertNotNull("size="+size+" yaw="+yaw+" cell="+Arrays.toString(point),pick);assertEquals(point[0],pick.x);assertEquals(point[1],pick.y);}}}}
 private float[] project(BoardCamera camera,float x,float y,float z){float[] m=camera.viewProjection;float w=m[3]*x+m[7]*y+m[11]*z+m[15];return new float[]{((m[0]*x+m[4]*y+m[8]*z+m[12])/w+1)*camera.width/2,(1-(m[1]*x+m[5]*y+m[9]*z+m[13])/w)*camera.height/2};}
}
