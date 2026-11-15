package cos.premy.mines.graphics;

/** Shared visible geometry and templates; no hidden mine data is accepted here. */
final class MineMesh {
    final MineArt.Buffer environment=new MineArt.Buffer(), cells=new MineArt.Buffer(), ghosts=new MineArt.Buffer();
    private final MineArt art;
    MineMesh(MineArt art){this.art=art;}
    void update(BoardScene scene,int turn) {
        update(scene,turn,turn==1?2:turn==2?3:turn==3?1:0);
    }
    void update(BoardScene scene,int turn,int walls){
        environment.clear();cells.clear();ghosts.clear();
        float sx=scene.width/5f,sz=scene.height/5f;
        append(environment,"environment",0,0,0,sx,1,sz,0,scene,walls);
        float y=BoardScene.layerY(scene.layer);
        if(scene.layer>0)append(environment,"support",0,y,0,sx,1,sz,0,null,0);
        for(int row=0;row<scene.height;row++) for(int col=0;col<scene.width;col++) {
            byte value=scene.cell(col,row);if(value==BoardScene.VOID)continue;
            float x=scene.x(col),z=scene.z(row);
            String part=value==BoardScene.HIT?"damaged":value<=6?"opened":"closed";
            if(scene.width>=10&&value!=BoardScene.HIT)part+="_lod";
            append(cells,part,x,y,z,1,1,1,0,null,0);
            if(value==BoardScene.FLAG)append(cells,"flag",x,y,z,1,1,1,0,null,0);
            if(value>0 && value<=6){
                if(scene.numberClues)append(cells,"digit"+value,x,y+.126f,z,1,1,1,turn,null,0);
                else for(int n=0;n<value;n++){float offset=(n-(value-1)*.5f)*.11f;flat(cells,x+offset-.018f,y+.127f,z-.23f,x+offset+.018f,z+.23f,.025f,.08f,.1f);}
                if(scene.colorClues){float[][] colors={{.04f,.38f,.7f},{.03f,.35f,.12f},{.8f,.14f,.06f},{.48f,.12f,.64f},{.52f,.28f,.02f},{.02f,.4f,.4f}};float[] c=colors[value-1];border(cells,x,y+.128f,z,.4f,.035f,c[0],c[1],c[2]);}
            }
            if(value==0)flat(cells,x-.035f,y+.126f,z-.035f,x+.035f,z+.035f,.08f,.19f,.21f);
            if(scene.selectedX==col && scene.selectedY==row)border(cells,x,y+BoardScene.top(value)+.018f,z,.482f,.025f,.18f,.87f,.88f);
            int id=(scene.layer*scene.height+row)*scene.width+col;
            if(scene.owners.containsKey(id)){
                int owner=scene.owners.get(id);float[] c=BoardScene.PLAYER_COLORS[owner%6];
                // Short colored ownership bar complements the flag, player number and name in HUD.
                flat(cells,x-.29f,y+BoardScene.top(value)+.024f,z+.31f,x+.29f,z+.37f,c[0],c[1],c[2]);
            }
            if(scene.route.get(id)&&value<=6)border(cells,x,y+.131f,z,.34f,.025f,.85f,.47f,.08f);
            if(scene.hintSources.get(id)||scene.hintTarget==id)border(cells,x,y+BoardScene.top(value)+.02f,z,.41f,.025f,1,.6f,.08f);
            if(id==scene.entry||id==scene.exit){boolean start=id==scene.entry;border(cells,x,y+BoardScene.top(value)+.022f,z,.38f,.04f,start?.05f:1,start?.8f:.42f,.12f);}
        }
        if(!scene.focused)for(int layer=0;layer<scene.layers;layer++)if(layer!=scene.layer){
            float h=BoardScene.layerY(layer);
            append(ghosts,"support",0,h,0,sx,1,sz,0,null,0);
            for(int row=0;row<scene.height;row++)for(int col=0;col<scene.width;col++) {
                if(!scene.present(layer,row,col))continue;
                float x=scene.x(col),z=scene.z(row);
                border(ghosts,x,h+.43f,z,.455f,.025f,.16f,.29f,.36f);
                flat(ghosts,x-.43f,h+.425f,z-.43f,x+.43f,z+.43f,.025f,.06f,.08f);
            }
        }
    }
    void append(MineArt.Buffer out,String part,float x,float y,float z,float sx,float sy,float sz,int turn,BoardScene environmentScene,int cameraTurn) {
        float[] a=art.parts.get(part);if(a==null)return;
        out.reserve(a.length);
        for(int i=0;i<a.length;i+=30) {
            if(environmentScene!=null) {
                float cx=(a[i]+a[i+10]+a[i+20])/3,cy=(a[i+1]+a[i+11]+a[i+21])/3,cz=(a[i+2]+a[i+12]+a[i+22])/3;
                // Cut away the wall facing the player when rotating behind the diorama.
                if(cy>.15f && (((cameraTurn&1)!=0 && cx<-2.45f) || ((cameraTurn&2)!=0 && cz<-2.35f)))continue;
            }
            for(int v=0;v<3;v++) {
                int j=i+v*10;float px=a[j],py=a[j+1],pz=a[j+2],nx=a[j+3],ny=a[j+4],nz=a[j+5];
                if(environmentScene!=null && py>0)py*=1+(environmentScene.layers-2)*.42f;
                float rx=rotateX(px,pz,turn),rz=rotateZ(px,pz,turn);
                out.vertex(x+rx*sx,y+py*sy,z+rz*sz,rotateX(nx,nz,turn),ny,rotateZ(nx,nz,turn),a[j+6],a[j+7],a[j+8],a[j+9]);
            }
        }
    }
    static float rotateX(float x,float z,int t){return t==1?z:t==2?-x:t==3?-z:x;}
    void spinning(MineArt.Buffer out,String part,float x,float y,float z,float scale,float angle){
        float[] a=art.parts.get(part);if(a==null)return;out.reserve(a.length);
        float co=(float)Math.cos(angle),si=(float)Math.sin(angle),cx=(float)Math.cos(angle*.73),sx=(float)Math.sin(angle*.73);
        for(int j=0;j<a.length;j+=10){float px=a[j]*co+a[j+2]*si,pz=-a[j]*si+a[j+2]*co,py=a[j+1];float nx=a[j+3]*co+a[j+5]*si,nz=-a[j+3]*si+a[j+5]*co,ny=a[j+4];out.vertex(x+px*scale,y+(py*cx-pz*sx)*scale,z+(py*sx+pz*cx)*scale,nx,ny*cx-nz*sx,ny*sx+nz*cx,a[j+6],a[j+7],a[j+8],a[j+9]);}
    }
    static float rotateZ(float x,float z,int t){return t==1?-x:t==2?-z:t==3?x:z;}
    static void border(MineArt.Buffer b,float x,float y,float z,float h,float t,float r,float g,float blue){
        flat(b,x-h,y,z-h,x+h,z-h+t,r,g,blue);flat(b,x-h,y,z+h-t,x+h,z+h,r,g,blue);
        flat(b,x-h,y,z-h+t,x-h+t,z+h-t,r,g,blue);flat(b,x+h-t,y,z-h+t,x+h,z+h-t,r,g,blue);
    }
    static void flat(MineArt.Buffer b,float x0,float y,float z0,float x1,float z1,float r,float g,float blue){
        for(float[] p:new float[][]{{x0,z0},{x1,z0},{x1,z1},{x0,z0},{x1,z1},{x0,z1}})b.vertex(p[0],y,p[1],0,1,0,r,g,blue,4);
    }
}
