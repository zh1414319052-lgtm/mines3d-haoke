package cos.premy.mines.graphics;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.FloatBuffer;

/** World-space meshes. Camera-only moves reuse these buffers. */
final class BoardMesh {
    private static final int CLOSED_TOP = 0xff4e789b;
    private static final int OPEN_TOP = 0xff203546;
    private static final int FLAG_TOP = 0xff796032;
    private static final int HIT_TOP = 0xffa7434e;
    private static final int[] CLUE_COLORS = {
            0xffa7c0d3, 0xff9fe0ff, 0xff97ecc0, 0xffffbf9e,
            0xffc2b8ff, 0xffffd58f, 0xfffeaecd
    };
    private static final int[] DIGITS = {0, 6, 91, 79, 102, 109, 125};
    private static final float[][] SEGMENTS = {
            {-.14f, -.32f, .14f, -.255f}, {.145f, -.247f, .205f, -.035f},
            {.145f, .035f, .205f, .247f}, {-.14f, .255f, .14f, .32f},
            {-.205f, .035f, -.145f, .247f}, {-.205f, -.247f, -.145f, -.035f},
            {-.14f, -.034f, .14f, .034f}
    };

    final Vertices blocks = new Vertices(24000);
    final Vertices ghost = new Vertices(4096);

    void update(BoardScene scene, int quarterTurn) {
        blocks.clear();
        ghost.clear();
        float y = BoardScene.layerY(scene.layer);
        float w = scene.width * .5f;
        float h = scene.height * .5f;
        box(-w - .12f, y - .20f, -h - .12f, w + .12f, y - .07f, h + .12f, 0xff30465c);
        for (int row = 0; row < scene.height; row++) {
            for (int column = 0; column < scene.width; column++) {
                byte value = scene.cell(column, row);
                float x = scene.x(column), z = scene.z(row);
                float top = y + BoardScene.top(value);
                float half = BoardScene.HALF_CELL;
                int color = value == BoardScene.CLOSED ? CLOSED_TOP
                        : value == BoardScene.FLAG ? FLAG_TOP : value == BoardScene.HIT ? HIT_TOP : OPEN_TOP;
                box(x - half, y + BoardScene.BASE, z - half, x + half, top, z + half, color);
                boolean selected = scene.selectedX == column && scene.selectedY == row;
                if (selected || value >= BoardScene.CLOSED) {
                    border(x, top + .002f, z, half - .009f, selected ? .047f : .016f,
                            selected ? 0xffa9f4ff : shade(color, 1.24f));
                }
                mark(value, x, top + .005f, z, quarterTurn, scene);
            }
        }
        if (!scene.focused) {
            for (int layer = 0; layer < scene.layers; layer++) {
                if (layer == scene.layer) continue;
                ghostLayer(scene, layer, w, h);
            }
            for (float x : new float[]{-w - .12f, w + .12f}) {
                for (float z : new float[]{-h - .12f, h + .12f}) {
                    line(x, -.12f, z, x, BoardScene.layerY(scene.layers - 1) + .39f, z, 0x4d6389a4);
                }
            }
        }
    }

    private void ghostLayer(BoardScene scene, int layer, float w, float h) {
        float top = BoardScene.layerY(layer) + BoardScene.top(BoardScene.CLOSED);
        float bottom = BoardScene.layerY(layer) - .12f;
        float x0 = -w - .12f, x1 = w + .12f, z0 = -h - .12f, z1 = h + .12f;
        int edge = layer == scene.layer + 1 || layer == scene.layer - 1 ? 0xb27eafcb : 0x827895ad;
        rectangle(x0, top, z0, x1, z1, edge);
        rectangle(x0, bottom, z0, x1, z1, 0x6a55738b);
        for (float x : new float[]{x0, x1}) for (float z : new float[]{z0, z1}) {
            line(x, bottom, z, x, top, z, edge);
        }
        for (int i = 1; i < scene.width; i++) {
            float x = -w + i;
            line(x, top, -h, x, top, h, 0x4c6389a4);
        }
        for (int i = 1; i < scene.height; i++) {
            float z = -h + i;
            line(-w, top, z, w, top, z, 0x4c6389a4);
        }
    }

    private void mark(byte value, float x, float y, float z, int turn, BoardScene scene) {
        if (value == BoardScene.FLAG) {
            symbolRect(x, y, z, turn, -.19f, -.30f, -.125f, .29f, 0xffffe29e);
            symbolTriangle(x, y, z, turn, -.125f, -.30f, .27f, -.19f, -.125f, -.035f, 0xffffcf68);
            symbolRect(x, y, z, turn, -.27f, .25f, .03f, .30f, 0xffffe29e);
        } else if (value == BoardScene.HIT) {
            symbolTriangle(x, y, z, turn, -.28f, -.20f, -.20f, -.28f, .28f, .20f, 0xffffe4e6);
            symbolTriangle(x, y, z, turn, -.28f, -.20f, .28f, .20f, .20f, .28f, 0xffffe4e6);
            symbolTriangle(x, y, z, turn, .28f, -.20f, .20f, -.28f, -.28f, .20f, 0xffffe4e6);
            symbolTriangle(x, y, z, turn, .28f, -.20f, -.28f, .20f, -.20f, .28f, 0xffffe4e6);
        } else if (value == 0) {
            flat(x - .045f, y, z - .045f, x + .045f, z + .045f, 0xff648699);
        } else if (value < BoardScene.CLOSED) {
            int color = scene.colorClues ? CLUE_COLORS[value] : 0xffe0f2ff;
            if (scene.numberClues) {
                for (int i = 0; i < SEGMENTS.length; i++) {
                    if ((DIGITS[value] & (1 << i)) == 0) continue;
                    float[] s = SEGMENTS[i];
                    symbolRect(x, y, z, turn, s[0], s[1], s[2], s[3], color);
                }
            } else {
                for (int i = 0; i < value; i++) {
                    float left = (i - (value - 1) * .5f) * .108f - .028f;
                    symbolRect(x, y, z, turn, left, -.25f, left + .056f, .25f, color);
                }
            }
        }
    }

    private void box(float x0, float y0, float z0, float x1, float y1, float z1, int c) {
        flat(x0, y1, z0, x1, z1, c);
        quad(x0, y0, z0, x0, y0, z1, x0, y1, z1, x0, y1, z0, shade(c, .62f));
        quad(x1, y0, z0, x1, y0, z1, x1, y1, z1, x1, y1, z0, shade(c, .69f));
        quad(x0, y0, z0, x1, y0, z0, x1, y1, z0, x0, y1, z0, shade(c, .75f));
        quad(x0, y0, z1, x1, y0, z1, x1, y1, z1, x0, y1, z1, shade(c, .79f));
    }

    private void border(float x, float y, float z, float half, float t, int c) {
        flat(x - half, y, z - half, x + half, z - half + t, c);
        flat(x - half, y, z + half - t, x + half, z + half, c);
        flat(x - half, y, z - half + t, x - half + t, z + half - t, c);
        flat(x + half - t, y, z - half + t, x + half, z + half - t, c);
    }

    private void flat(float x0, float y, float z0, float x1, float z1, int c) {
        quad(x0, y, z0, x1, y, z0, x1, y, z1, x0, y, z1, c);
    }

    private void symbolRect(float x, float y, float z, int turn,
                            float x0, float z0, float x1, float z1, int color) {
        symbolTriangle(x, y, z, turn, x0, z0, x1, z0, x1, z1, color);
        symbolTriangle(x, y, z, turn, x0, z0, x1, z1, x0, z1, color);
    }

    private void symbolTriangle(float x, float y, float z, int turn, float x0, float z0,
                                float x1, float z1, float x2, float z2, int color) {
        symbolVertex(x, y, z, turn, x0, z0, color);
        symbolVertex(x, y, z, turn, x1, z1, color);
        symbolVertex(x, y, z, turn, x2, z2, color);
    }

    private void symbolVertex(float x, float y, float z, int turn, float dx, float dz, int color) {
        switch (turn) {
            case 1: blocks.add(x + dz, y, z - dx, color); break;
            case 2: blocks.add(x - dx, y, z - dz, color); break;
            case 3: blocks.add(x - dz, y, z + dx, color); break;
            default: blocks.add(x + dx, y, z + dz, color);
        }
    }

    private void quad(float ax, float ay, float az, float bx, float by, float bz,
                      float cx, float cy, float cz, float dx, float dy, float dz, int color) {
        blocks.add(ax, ay, az, color);
        blocks.add(bx, by, bz, color);
        blocks.add(cx, cy, cz, color);
        blocks.add(ax, ay, az, color);
        blocks.add(cx, cy, cz, color);
        blocks.add(dx, dy, dz, color);
    }

    private void rectangle(float x0, float y, float z0, float x1, float z1, int color) {
        line(x0, y, z0, x1, y, z0, color);
        line(x1, y, z0, x1, y, z1, color);
        line(x1, y, z1, x0, y, z1, color);
        line(x0, y, z1, x0, y, z0, color);
    }

    private void line(float x, float y, float z, float x2, float y2, float z2, int color) {
        ghost.add(x, y, z, color);
        ghost.add(x2, y2, z2, color);
    }

    private static int shade(int c, float f) {
        int red = Math.min(255, (int) ((c >> 16 & 255) * f));
        int green = Math.min(255, (int) ((c >> 8 & 255) * f));
        int blue = Math.min(255, (int) ((c & 255) * f));
        return 0xff000000 | red << 16 | green << 8 | blue;
    }

    static final class Vertices {
        static final int STRIDE = 7;
        FloatBuffer buffer;

        Vertices(int count) {
            buffer = allocate(count * STRIDE);
        }

        void clear() { buffer.clear(); }
        int count() { return buffer.position() / STRIDE; }

        void add(float x, float y, float z, int argb) {
            if (buffer.remaining() < STRIDE) {
                FloatBuffer larger = allocate(buffer.capacity() * 2);
                buffer.flip();
                larger.put(buffer);
                buffer = larger;
            }
            buffer.put(x).put(y).put(z)
                    .put((argb >> 16 & 255) / 255f).put((argb >> 8 & 255) / 255f)
                    .put((argb & 255) / 255f).put((argb >>> 24) / 255f);
        }

        private static FloatBuffer allocate(int floats) {
            return ByteBuffer.allocateDirect(floats * 4).order(ByteOrder.nativeOrder()).asFloatBuffer();
        }
    }
}
