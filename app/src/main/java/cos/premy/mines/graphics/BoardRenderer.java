package cos.premy.mines.graphics;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.opengl.GLES20;
import android.opengl.GLSurfaceView;
import android.opengl.GLUtils;
import android.util.Log;
import java.io.InputStream;
import java.util.Random;
import javax.microedition.khronos.egl.EGLConfig;
import javax.microedition.khronos.opengles.GL10;

/** GLES2 rendering of the approved mine assets; immutable snapshots cross the UI/GL boundary. */
final class BoardRenderer implements GLSurfaceView.Renderer {
    private static final String TAG="Mines3D";
    private static final String VERTEX=
        "uniform mat4 camera;attribute vec3 position;attribute vec3 normal;attribute vec3 color;attribute float material;"
        +"varying vec3 wp;varying vec3 wn;varying vec3 albedo;varying float mat;"
        +"void main(){wp=position;wn=normal;albedo=color;mat=material;gl_Position=camera*vec4(position,1.0);}";
    private static final String FRAGMENT=
        "precision mediump float;varying vec3 wp;varying vec3 wn;varying vec3 albedo;varying float mat;"
        +"uniform sampler2D rock;uniform sampler2D steel;uniform vec3 eye;uniform vec3 flash;uniform float power;uniform float opacity;uniform vec3 bounds;"
        +"vec3 tone(vec3 x){return pow(clamp((x*(2.51*x+.03))/(x*(2.43*x+.59)+.14),0.0,1.0),vec3(.4545));}"
        +"void main(){vec3 n=normalize(wn);vec3 c=albedo;"
        +"if(mat>.5&&mat<2.5){vec3 w=pow(abs(n),vec3(4.0));w/=max(.001,w.x+w.y+w.z);"
        +"vec2 a=wp.yz*.63,b=wp.xz*.63,d=wp.xy*.63;vec3 tex;"
        +"if(mat<1.5)tex=texture2D(rock,a).rgb*w.x+texture2D(rock,b).rgb*w.y+texture2D(rock,d).rgb*w.z;"
        +"else tex=texture2D(steel,a).rgb*w.x+texture2D(steel,b).rgb*w.y+texture2D(steel,d).rgb*w.z;"
        +"c=pow(tex,vec3(2.2));}"
        +"if(mat>3.5){gl_FragColor=vec4(pow(max(c,vec3(0.0)),vec3(.4545)),opacity);return;}"
        +"if(mat>2.5){gl_FragColor=vec4(tone(c*3.3),opacity);return;}"
        +"vec3 light=vec3(.10,.14,.19)+vec3(.64,.83,1.04)*max(0.0,dot(n,normalize(vec3(1.0,6.0,2.0))))"
        +"+vec3(.22,.33,.50)*max(0.0,dot(n,normalize(vec3(-4.0,3.0,-2.0))))"
        +"+vec3(.28,.20,.13)*max(0.0,dot(n,normalize(vec3(5.0,4.0,1.0))));"
        +"for(int i=0;i<2;i++){vec3 lp=vec3((i==0?-1.0:1.0)*(bounds.x*.5+.03),bounds.y+.73,-bounds.z*.5+.35);vec3 v=lp-wp;"
        +"light+=vec3(1.0,.46,.13)*max(0.0,dot(n,normalize(v)))*3.0/(.7+dot(v,v));}"
        +"vec3 fv=flash-wp;light+=vec3(1.0,.57,.24)*max(0.0,dot(n,normalize(fv)))*power/(.18+dot(fv,fv));"
        +"vec3 view=normalize(eye-wp),halfway=normalize(view+normalize(vec3(1.0,6.0,2.0)));"
        +"float spec=pow(max(0.0,dot(n,halfway)),mat>1.5?32.0:8.0)*(mat>1.5?.12:.025);"
        +"vec3 lit=c*light+vec3(.55,.7,.85)*spec;"
        +"gl_FragColor=vec4(tone(lit),opacity);}";
    private static final String DUST_V=
        "uniform mat4 camera;attribute vec3 position;attribute vec2 uv;varying vec2 coord;"
        +"void main(){coord=uv;gl_Position=camera*vec4(position,1.0);}";
    private static final String DUST_F=
        "precision mediump float;uniform sampler2D smoke;uniform float opacity;uniform float frame0;uniform float frame1;uniform float blendFrame;varying vec2 coord;"
        +"vec2 atlas(float f){return (vec2(mod(f,4.0),floor(f/4.0))+clamp(coord,vec2(.002),vec2(.998)))*.25;}"
        +"void main(){vec4 c=mix(texture2D(smoke,atlas(frame0)),texture2D(smoke,atlas(frame1)),blendFrame);gl_FragColor=vec4(c.rgb,c.a*opacity);}";
    static final class Frame {
        final BoardScene scene;final BoardCamera camera;final int turn,walls;
        final float effect;final boolean reduced;
        Frame(BoardScene s,BoardCamera c,int t,float effect,boolean reduced){scene=s;camera=c;turn=t;walls=(c.eyePosition()[0]<0?1:0)|(c.eyePosition()[2]<0?2:0);this.effect=effect;this.reduced=reduced;}
    }
    volatile Frame next,drawn;
    private final Context context;
    private final Runnable onFailure;
    private MineArt art;private MineMesh mesh;
    private BoardScene meshedScene;private int meshedTurn,meshedWalls;
    private int program,dustProgram,rockTexture,steelTexture,dustTexture;
    private int width,height;private final MineArt.Buffer particles=new MineArt.Buffer();
    private final java.nio.FloatBuffer dust=MineArt.Buffer.allocate(30);
    private BoardScene particleScene;private float particleTime=-1;
    private long frames,startNanos,worstNanos;private long[] frameBuckets=new long[5];
    BoardRenderer(Context context,Runnable failure){this.context=context.getApplicationContext();onFailure=failure;}
    @Override public void onSurfaceCreated(GL10 gl,EGLConfig config){
        drawn=null;meshedScene=null;GLES20.glClearColor(.004f,.009f,.014f,1);GLES20.glDepthFunc(GLES20.GL_LEQUAL);
        GLES20.glBlendFunc(GLES20.GL_SRC_ALPHA,GLES20.GL_ONE_MINUS_SRC_ALPHA);
        try{
            if(art==null){art=new MineArt(context.getAssets());mesh=new MineMesh(art);}
            program=link(VERTEX,FRAGMENT);dustProgram=link(DUST_V,DUST_F);
            rockTexture=texture("rock_basecolor.png",true);steelTexture=texture("steel_basecolor.png",true);dustTexture=texture("dust_atlas.png",false);
            Log.i(TAG,"MINE_ART_READY GLES="+GLES20.glGetString(GLES20.GL_VERSION)+" renderer="+GLES20.glGetString(GLES20.GL_RENDERER));
        }catch(Exception ex){program=0;Log.e(TAG,"Mine renderer initialization failed",ex);onFailure.run();}
    }
    @Override public void onSurfaceChanged(GL10 gl,int w,int h){width=w;height=h;drawn=null;GLES20.glViewport(0,0,w,h);}
    @Override public void onDrawFrame(GL10 gl){
        long began=System.nanoTime();Frame f=next;
        GLES20.glClear(GLES20.GL_COLOR_BUFFER_BIT|GLES20.GL_DEPTH_BUFFER_BIT);
        if(program==0||f==null||width<=0||height<=0||f.camera.width!=width||f.camera.height!=height)return;
        if(f.scene!=meshedScene||f.turn!=meshedTurn||f.walls!=meshedWalls){mesh.update(f.scene,f.turn,f.walls);meshedScene=f.scene;meshedTurn=f.turn;meshedWalls=f.walls;}
        GLES20.glUseProgram(program);uniformMatrix(program,f.camera);
        GLES20.glUniform3fv(GLES20.glGetUniformLocation(program,"eye"),1,f.camera.eyePosition(),0);
        GLES20.glUniform3f(GLES20.glGetUniformLocation(program,"bounds"),f.scene.width,BoardScene.layerY(f.scene.layer),f.scene.height);
        float[] hit=f.scene.hitPosition();
        GLES20.glUniform3f(GLES20.glGetUniformLocation(program,"flash"),hit[0],hit[1]+.72f,hit[2]);
        float p=f.effect>=0&&f.effect<.45f?(float)(18.0*Math.exp(-f.effect*15)):0;
        GLES20.glUniform1f(GLES20.glGetUniformLocation(program,"power"),p*(f.reduced?.12f:1));
        bind(rockTexture,0,program,"rock");bind(steelTexture,1,program,"steel");
        GLES20.glEnable(GLES20.GL_DEPTH_TEST);GLES20.glDepthMask(true);GLES20.glDisable(GLES20.GL_BLEND);
        draw(mesh.environment,1);
        if(!f.scene.focused){GLES20.glEnable(GLES20.GL_BLEND);GLES20.glDepthMask(false);draw(mesh.ghosts,.23f);GLES20.glDepthMask(true);GLES20.glDisable(GLES20.GL_BLEND);}
        draw(mesh.cells,1);
        if(f.effect>=0){makeParticles(f.scene,hit,f.effect);
            if(!f.reduced&&f.effect<.25f){float t=f.effect,core=t<.04167f?.3f+.7f*t/.04167f:t<.125f?1-.3f*(t-.04167f)/.08333f:t<.20833f?.7f-.55f*(t-.125f)/.08333f:.15f*(1-(t-.20833f)/.04167f);mesh.append(particles,"ignition",hit[0],hit[1]+.52f,hit[2],core,core,core,0,null,0);}
            draw(particles,1);if(f.effect<6)drawDust(f,hit);}
        drawn=f;
        long cost=System.nanoTime()-began;worstNanos=Math.max(worstNanos,cost);frames++;
        frameBuckets[cost<16666667?0:cost<33333334?1:cost<50000000?2:cost<100000000?3:4]++;
        if(startNanos==0)startNanos=began;
        if(frames%300==0)Log.i(TAG,"FRAME_STATS count="+frames+" drawCpuWorstMs="+(worstNanos/1e6)+" buckets16_33_50_100_slow="+java.util.Arrays.toString(frameBuckets));
    }
    private void draw(MineArt.Buffer b,float alpha){
        if(b.count==0)return;
        GLES20.glUniform1f(GLES20.glGetUniformLocation(program,"opacity"),alpha);
        attribute(program,"position",3,0,40,b.data);attribute(program,"normal",3,3,40,b.data);
        attribute(program,"color",3,6,40,b.data);attribute(program,"material",1,9,40,b.data);
        GLES20.glDrawArrays(GLES20.GL_TRIANGLES,0,b.count);
    }
    cos.premy.mines.data.MineCoord pick(Frame frame,float x,float y){return frame==drawn&&frame==next&&art!=null?frame.camera.pickVisible(frame.scene,x,y,art,mesh):null;}
    private void makeParticles(BoardScene scene,float[] hit,float t){
        if(scene==particleScene&&t>=6&&particleTime>=6)return;
        particleScene=scene;particleTime=t;
        particles.clear();Random r=new Random(20261112);
        for(int i=0;i<36;i++){
            float a=r.nextFloat()*6.283185f,speed=1+r.nextFloat()*2.2f;
            float vx=(float)Math.cos(a)*speed,vz=(float)Math.sin(a)*speed,vy=2.6f+r.nextFloat()*2.6f;
            float x=hit[0]+(r.nextFloat()-.5f)*.46f,z=hit[2]+(r.nextFloat()-.5f)*.46f,y=hit[1]+.4f;
            float spin=r.nextFloat()*6,scale=.6f+r.nextFloat()*.7f;
            float dt=1f/60;int steps=Math.min(360,(int)(Math.min(t,6)*60));
            for(int step=0;step<steps;step++){
                vy-=9.81f*dt;float oldX=x,oldZ=z;x+=vx*dt;y+=vy*dt;z+=vz*dt;
                float surface=hit[1]-1.36f;
                if(Math.abs(x)<scene.width*.5f+.58f&&Math.abs(z)<scene.height*.5f+.5f)surface=hit[1]-.365f;
                int col=(int)Math.floor(x+scene.width*.5f),row=(int)Math.floor(z+scene.height*.5f);
                if(col>=0&&col<scene.width&&row>=0&&row<scene.height&&scene.cell(col,row)!=BoardScene.VOID)
                    surface=hit[1]+BoardScene.top(scene.cell(col,row));
                float rail=scene.width*.5f+.18f;
                if(Math.abs(oldX)<rail&&Math.abs(x)>=rail&&Math.abs(z)<scene.height*.5f+.25f&&y>hit[1]-.2f&&y<hit[1]+.35f){x=oldX;vx=-vx*.45f;}
                if(Math.abs(oldZ)<scene.height*.5f+.18f&&Math.abs(z)>=scene.height*.5f+.18f&&Math.abs(x)<rail&&y>hit[1]-.2f&&y<hit[1]+.35f){z=oldZ;vz=-vz*.45f;}
                float postX=2.79f*scene.width/5f,postZ=scene.height/5f,hx=.09f*scene.width/5f,hz=.115f*scene.height/5f;
                if(Math.abs(x-postX)<hx+.025f&&Math.abs(z-postZ)<hz+.025f&&y>-.25f&&y<1.45f*(1+(scene.layers-2)*.42f)){
                    x=postX+(oldX<postX?-hx-.03f:hx+.03f);vx=-vx*.42f;vz*=.68f;vy*=.86f;
                }
                if(y<surface+.025f){y=surface+.025f;vy=Math.abs(vy)*.22f;vx*=.73f;vz*=.73f;if(vy<.15f)vy=0;}
            }
            mesh.spinning(particles,i<14?"fragment0":i%2==0?"fragment16":"fragment25",x,y,z,scale,Math.min(t,1.8f)*spin);
        }
    }
    private void drawDust(Frame f,float[] hit){
        float t=f.effect;if(t<.06f)return;
        float fade=Math.min(1,(t-.06f)*8);
        GLES20.glEnable(GLES20.GL_BLEND);GLES20.glDepthMask(false);GLES20.glUseProgram(dustProgram);uniformMatrix(dustProgram,f.camera);bind(dustTexture,0,dustProgram,"smoke");
        float[] right=f.camera.rightVector(),up=f.camera.upVector();
        float frame=Math.min(15,t/6*15);int first=(int)frame;
        GLES20.glUniform1f(GLES20.glGetUniformLocation(dustProgram,"frame0"),first);
        GLES20.glUniform1f(GLES20.glGetUniformLocation(dustProgram,"frame1"),Math.min(15,first+1));
        GLES20.glUniform1f(GLES20.glGetUniformLocation(dustProgram,"blendFrame"),frame-first);
        {
            float radius=2.75f,cx=hit[0],cy=hit[1]+1.2f,cz=hit[2];
            dust.clear();for(float[] q:new float[][]{{-1,-1,0,1},{1,-1,1,1},{1,1,1,0},{-1,-1,0,1},{1,1,1,0},{-1,1,0,0}}){
                dust.put(cx+radius*(right[0]*q[0]+up[0]*q[1])).put(cy+radius*(right[1]*q[0]+up[1]*q[1])).put(cz+radius*(right[2]*q[0]+up[2]*q[1])).put(q[2]).put(q[3]);
            }
            attribute(dustProgram,"position",3,0,20,dust);attribute(dustProgram,"uv",2,3,20,dust);
            GLES20.glUniform1f(GLES20.glGetUniformLocation(dustProgram,"opacity"),fade);GLES20.glDrawArrays(GLES20.GL_TRIANGLES,0,6);
        }
        GLES20.glDepthMask(true);GLES20.glDisable(GLES20.GL_BLEND);GLES20.glUseProgram(program);
    }
    private int texture(String name,boolean repeat)throws Exception{
        Bitmap bitmap;BitmapFactory.Options options=new BitmapFactory.Options();options.inPremultiplied=false;try(InputStream in=context.getAssets().open("mine/"+name)){bitmap=BitmapFactory.decodeStream(in,null,options);}
        if(bitmap==null)throw new IllegalStateException("Unreadable texture "+name);
        int[] id=new int[1];GLES20.glGenTextures(1,id,0);GLES20.glBindTexture(GLES20.GL_TEXTURE_2D,id[0]);
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D,GLES20.GL_TEXTURE_MIN_FILTER,GLES20.GL_LINEAR_MIPMAP_LINEAR);
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D,GLES20.GL_TEXTURE_MAG_FILTER,GLES20.GL_LINEAR);
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D,GLES20.GL_TEXTURE_WRAP_S,repeat?GLES20.GL_REPEAT:GLES20.GL_CLAMP_TO_EDGE);
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D,GLES20.GL_TEXTURE_WRAP_T,repeat?GLES20.GL_REPEAT:GLES20.GL_CLAMP_TO_EDGE);
        GLUtils.texImage2D(GLES20.GL_TEXTURE_2D,0,bitmap,0);GLES20.glGenerateMipmap(GLES20.GL_TEXTURE_2D);bitmap.recycle();return id[0];
    }
    private static void bind(int texture,int unit,int p,String name){GLES20.glActiveTexture(GLES20.GL_TEXTURE0+unit);GLES20.glBindTexture(GLES20.GL_TEXTURE_2D,texture);GLES20.glUniform1i(GLES20.glGetUniformLocation(p,name),unit);}
    private static void uniformMatrix(int p,BoardCamera c){GLES20.glUniformMatrix4fv(GLES20.glGetUniformLocation(p,"camera"),1,false,c.viewProjection,0);}
    private static void attribute(int p,String name,int size,int offset,int stride,java.nio.FloatBuffer data){int id=GLES20.glGetAttribLocation(p,name);if(id<0)return;data.position(offset);GLES20.glEnableVertexAttribArray(id);GLES20.glVertexAttribPointer(id,size,GLES20.GL_FLOAT,false,stride,data);}
    private static int link(String vs,String fs){int v=compile(GLES20.GL_VERTEX_SHADER,vs),f=compile(GLES20.GL_FRAGMENT_SHADER,fs),p=GLES20.glCreateProgram();GLES20.glAttachShader(p,v);GLES20.glAttachShader(p,f);GLES20.glLinkProgram(p);GLES20.glDeleteShader(v);GLES20.glDeleteShader(f);int[] ok=new int[1];GLES20.glGetProgramiv(p,GLES20.GL_LINK_STATUS,ok,0);if(ok[0]==0)throw new IllegalStateException(GLES20.glGetProgramInfoLog(p));return p;}
    private static int compile(int type,String source){int s=GLES20.glCreateShader(type);GLES20.glShaderSource(s,source);GLES20.glCompileShader(s);int[] ok=new int[1];GLES20.glGetShaderiv(s,GLES20.GL_COMPILE_STATUS,ok,0);if(ok[0]==0)throw new IllegalStateException(GLES20.glGetShaderInfoLog(s));return s;}
}
