package cos.premy.mines.graphics;

import android.content.res.AssetManager;
import java.io.BufferedInputStream;
import java.io.DataInputStream;
import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.FloatBuffer;
import java.util.LinkedHashMap;
import java.util.Map;

/** Triangle templates exported from the approved .blend, in Android world axes. */
final class MineArt {
    static final int STRIDE = 10;
    final Map<String,float[]> parts = new LinkedHashMap<>();
    MineArt(AssetManager assets) throws IOException {
        try (DataInputStream in = new DataInputStream(new BufferedInputStream(assets.open("mine/scene.m3d")))) {
            if (in.readInt() != 0x4d334432) throw new IOException("Unknown mine art format");
            int count=in.readInt();
            if(count<1 || count>64) throw new IOException("Invalid part count");
            for(int i=0;i<count;i++) {
                int length=in.readInt();if(length<1 || length>80)throw new IOException("Invalid part name");
                byte[] bytes=new byte[length];in.readFully(bytes);
                String name=new String(bytes,java.nio.charset.StandardCharsets.UTF_8);
                int vertices=in.readInt();if(vertices<0 || vertices>2000000)throw new IOException("Invalid vertex count");
                float[] data=new float[vertices*STRIDE];
                for(int v=0;v<data.length;v++){data[v]=in.readFloat();if(Float.isNaN(data[v])||Float.isInfinite(data[v]))throw new IOException("Nonfinite geometry");}
                parts.put(name,data);
            }
        }
        for(String name:new String[]{"environment","closed","opened","flag","damaged","digit1","fragment0","ignition"})
            if(!parts.containsKey(name))throw new IOException("Missing art: "+name);
    }
    static final class Buffer {
        FloatBuffer data=allocate(30000);int count;
        void clear(){data.clear();count=0;}
        void reserve(int extra){if(data.remaining()<extra){FloatBuffer b=allocate(Math.max(data.capacity()*2,data.position()+extra));data.flip();b.put(data);data=b;}}
        void vertex(float x,float y,float z,float nx,float ny,float nz,float r,float g,float b,float material){
            reserve(STRIDE);data.put(x).put(y).put(z).put(nx).put(ny).put(nz).put(r).put(g).put(b).put(material);count++;
        }
        static FloatBuffer allocate(int n){return ByteBuffer.allocateDirect(n*4).order(ByteOrder.nativeOrder()).asFloatBuffer();}
    }
}
