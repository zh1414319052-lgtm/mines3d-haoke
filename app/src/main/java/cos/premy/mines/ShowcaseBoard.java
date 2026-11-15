package cos.premy.mines;
import android.os.Bundle;

/** QA-only playable copy of the approved Blender comparison layout. */
public final class ShowcaseBoard {
    public static Bundle state(){
        byte[] cells=new byte[50];
        int[][][] mines={{{4,1},{1,0},{2,2},{3,4}},{{0,1},{2,1},{4,4},{1,3}}};
        int[][][] open={{{0,0},{0,1},{0,2},{1,1},{1,2},{2,0},{3,0},{3,1},{4,0}},{{0,0},{1,0},{2,0},{1,1},{2,2},{3,1}}};
        for(int z=0;z<2;z++){for(int[] c:mines[z])cells[z*25+(4-c[1])*5+c[0]]=4;for(int[] c:open[z])cells[z*25+(4-c[1])*5+c[0]]=2;}
        Bundle b=new Bundle();b.putBoolean("generated",true);b.putByteArray("cells",cells);b.putInt("layer",0);b.putBoolean("3d.focus",true);return b;
    }
}
