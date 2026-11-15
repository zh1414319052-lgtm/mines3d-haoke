package cos.premy.mines.graphics;

import cos.premy.mines.data.MineCoord;

/** Perspective projection and hit testing share this camera and the rendered block bounds. */
final class BoardCamera {
    static final float DEFAULT_YAW = 36;
    static final float DEFAULT_PITCH = 43;
    private static final float TAN_V = .364f; // 40 degrees vertical field of view
    private static final float NEAR = .25f;
    private static final float FAR = 260f;

    final int width, height;
    final float[] viewProjection = new float[16];
    private final float[] right = new float[3], up = new float[3], back = new float[3], eye = new float[3];
    private final float tanH;

    BoardCamera(BoardScene board, int width, int height, float yaw, float pitch, float zoom) {
        this(board,width,height,yaw,pitch,zoom,0,0);
    }
    BoardCamera(BoardScene board,int width,int height,float yaw,float pitch,float zoom,float panX,float panZ){
        this.width = Math.max(1, width);
        this.height = Math.max(1, height);
        tanH = TAN_V * this.width / this.height;

        double ry = Math.toRadians(yaw);
        double rp = Math.toRadians(pitch);
        float sy = (float) Math.sin(ry), cy = (float) Math.cos(ry);
        float sp = (float) Math.sin(rp), cp = (float) Math.cos(rp);
        right[0] = cy;
        right[2] = -sy;
        up[0] = -sy * sp;
        up[1] = cp;
        up[2] = -cy * sp;
        back[0] = sy * cp;
        back[1] = sp;
        back[2] = cy * cp;

        float low = BoardScene.layerY(board.focused ? board.layer : 0) - 1.2f;
        float high = BoardScene.layerY(board.focused ? board.layer : board.layers - 1) + 1.7f;
        float center = (low + high) * .5f;
        float edgeX = board.width * .5f + .85f;
        float edgeZ = board.height * .5f + .85f;
        float fit = 0;
        float closest = 0;
        for (float x : new float[]{-edgeX, edgeX}) {
            for (float z : new float[]{-edgeZ, edgeZ}) {
                for (float y : new float[]{low - center, high - center}) {
                    float depth = dot(back, x, y, z);
                    float projected = Math.max(Math.abs(dot(right, x, y, z)) / tanH,
                            Math.abs(dot(up, x, y, z)) / TAN_V);
                    fit = Math.max(fit, depth + 1.13f * projected);
                    closest = Math.max(closest, depth);
                }
            }
        }
        float distance = Math.max(closest + .7f, fit / zoom);
        eye[0] = back[0] * distance+panX;
        eye[1] = center + back[1] * distance;
        eye[2] = back[2] * distance+panZ;
        makeMatrix();
    }

    MineCoord pick(BoardScene board, float pixelX, float pixelY) {
        if (pixelX < 0 || pixelY < 0 || pixelX >= width || pixelY >= height) return null;
        float x = (2 * pixelX / width - 1) * tanH;
        float y = (1 - 2 * pixelY / height) * TAN_V;
        float[] direction = {
                -back[0] + right[0] * x + up[0] * y,
                -back[1] + right[1] * x + up[1] * y,
                -back[2] + right[2] * x + up[2] * y
        };
        float layerY = BoardScene.layerY(board.layer);
        float nearest = FAR;
        int hitX = -1, hitY = -1;
        for (int row = 0; row < board.height; row++) {
            for (int column = 0; column < board.width; column++) {
                if(board.cell(column,row)==BoardScene.VOID)continue;
                float cx = board.x(column), cz = board.z(row);
                float half = BoardScene.HALF_CELL;
                float entry = intersects(direction, cx - half, layerY + BoardScene.BASE, cz - half,
                        cx + half, layerY + BoardScene.top(board.cell(column, row)), cz + half);
                if (entry < nearest) {
                    nearest = entry;
                    hitX = column;
                    hitY = row;
                }
            }
        }
        return hitX == -1 ? null : new MineCoord(hitX, hitY, board.layer);
    }

    private float intersects(float[] direction, float x0, float y0, float z0,
                             float x1, float y1, float z1) {
        float entry = NEAR;
        float exit = FAR;
        for (int axis = 0; axis < 3; axis++) {
            float low = axis == 0 ? x0 : axis == 1 ? y0 : z0;
            float high = axis == 0 ? x1 : axis == 1 ? y1 : z1;
            float delta = direction[axis];
            if (Math.abs(delta) < 1e-6f) {
                if (eye[axis] < low || eye[axis] > high) return FAR;
            } else {
                float a = (low - eye[axis]) / delta;
                float b = (high - eye[axis]) / delta;
                entry = Math.max(entry, Math.min(a, b));
                exit = Math.min(exit, Math.max(a, b));
                if (entry > exit) return FAR;
            }
        }
        return entry;
    }
    /** Exact visible triangles refine the broad cell bounds; opaque supports occlude input. */
    MineCoord pickVisible(BoardScene board,float px,float py,MineArt art,MineMesh mesh){
        if(px<0||py<0||px>=width||py>=height)return null;
        float u=(2*px/width-1)*tanH,v=(1-2*py/height)*TAN_V;
        float[] ray={-back[0]+right[0]*u+up[0]*v,-back[1]+right[1]*u+up[1]*v,-back[2]+right[2]*u+up[2]*v};
        float nearest=FAR;MineCoord selected=null;float h=BoardScene.layerY(board.layer);
        for(int row=0;row<board.height;row++)for(int col=0;col<board.width;col++){
            byte value=board.cell(col,row);if(value==BoardScene.VOID)continue;float x=board.x(col),z=board.z(row);
            if(intersects(ray,x-.5f,h-.12f,z-.5f,x+.5f,h+(value==BoardScene.FLAG?1.5f:BoardScene.top(value)+.02f),z+.5f)>=nearest)continue;
            String part=value==BoardScene.HIT?"damaged":value<=6?"opened":"closed";if(board.width>=10&&value!=BoardScene.HIT)part+="_lod";
            float t=triangles(art.parts.get(part),ray,x,h,z,nearest);
            if(value==BoardScene.FLAG)t=triangles(art.parts.get("flag"),ray,x,h,z,t);
            if(t<nearest){nearest=t;selected=new MineCoord(col,row,board.layer);}
        }
        if(selected!=null){java.nio.FloatBuffer a=mesh.environment.data;for(int j=0;j<mesh.environment.count*10;j+=30){float t=triangle(ray,a.get(j),a.get(j+1),a.get(j+2),a.get(j+10),a.get(j+11),a.get(j+12),a.get(j+20),a.get(j+21),a.get(j+22));if(t<nearest-.015f)return null;}}
        return selected;
    }
    private float triangles(float[] a,float[] ray,float x,float y,float z,float nearest){if(a==null)return nearest;for(int j=0;j<a.length;j+=30){float t=triangle(ray,a[j]+x,a[j+1]+y,a[j+2]+z,a[j+10]+x,a[j+11]+y,a[j+12]+z,a[j+20]+x,a[j+21]+y,a[j+22]+z);nearest=Math.min(nearest,t);}return nearest;}
    private float triangle(float[] d,float ax,float ay,float az,float bx,float by,float bz,float cx,float cy,float cz){
        float e1x=bx-ax,e1y=by-ay,e1z=bz-az,e2x=cx-ax,e2y=cy-ay,e2z=cz-az;
        float hx=d[1]*e2z-d[2]*e2y,hy=d[2]*e2x-d[0]*e2z,hz=d[0]*e2y-d[1]*e2x,det=e1x*hx+e1y*hy+e1z*hz;
        if(Math.abs(det)<.000001f)return FAR;float inv=1/det,sx=eye[0]-ax,sy=eye[1]-ay,sz=eye[2]-az,u=(sx*hx+sy*hy+sz*hz)*inv;if(u<0||u>1)return FAR;
        float qx=sy*e1z-sz*e1y,qy=sz*e1x-sx*e1z,qz=sx*e1y-sy*e1x,v=(d[0]*qx+d[1]*qy+d[2]*qz)*inv;if(v<0||u+v>1)return FAR;float t=(e2x*qx+e2y*qy+e2z*qz)*inv;return t>=NEAR?t:FAR;
    }

    private void makeMatrix() {
        float depthScale = (FAR + NEAR) / (FAR - NEAR);
        for (int i = 0; i < 3; i++) {
            viewProjection[i * 4] = right[i] / tanH;
            viewProjection[i * 4 + 1] = up[i] / TAN_V;
            viewProjection[i * 4 + 2] = -depthScale * back[i];
            viewProjection[i * 4 + 3] = -back[i];
        }
        viewProjection[12] = -dot(right, eye[0], eye[1], eye[2]) / tanH;
        viewProjection[13] = -dot(up, eye[0], eye[1], eye[2]) / TAN_V;
        viewProjection[14] = depthScale * dot(back, eye[0], eye[1], eye[2])
                - 2 * FAR * NEAR / (FAR - NEAR);
        viewProjection[15] = dot(back, eye[0], eye[1], eye[2]);
    }

    private static float dot(float[] v, float x, float y, float z) {
        return v[0] * x + v[1] * y + v[2] * z;
    }
    float[] eyePosition(){return eye;}
    float[] rightVector(){return right;}
    float[] upVector(){return up;}
}
