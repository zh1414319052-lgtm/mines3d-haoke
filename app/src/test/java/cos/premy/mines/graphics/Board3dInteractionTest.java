package cos.premy.mines.graphics;

import org.junit.Test;

import java.util.Arrays;

import cos.premy.mines.data.MineCoord;

import static org.junit.Assert.*;

public class Board3dInteractionTest {
    @Test
    public void projectionAndPickingAgreeAcrossAllVisibleTilesAndAngles() {
        for (int size : new int[]{5, 15}) {
            for (boolean focus : new boolean[]{false, true}) {
                BoardScene scene = closedBoard(size, size == 5 ? 2 : 8, size == 5 ? 1 : 3, focus);
                for (int[] viewport : new int[][]{{720, 1180}, {1180, 610}}) {
                    for (float yaw : new float[]{36, 104, 192, 311}) {
                        BoardCamera camera = new BoardCamera(scene, viewport[0], viewport[1], yaw, 43, 1);
                        for (int row = 0; row < size; row++) {
                            for (int column = 0; column < size; column++) {
                                float[] point = project(camera, scene.x(column),
                                        BoardScene.layerY(scene.layer) + BoardScene.top(BoardScene.CLOSED),
                                        scene.z(row));
                                MineCoord hit = camera.pick(scene, point[0], point[1]);
                                assertNotNull("Cell " + column + "," + row + " at yaw " + yaw, hit);
                                assertEquals(column, hit.x);
                                assertEquals(row, hit.y);
                                assertEquals(scene.layer, hit.z);
                            }
                        }
                    }
                }
            }
        }
    }

    @Test
    public void activeLayerAloneCanBePickedAtOverlappingScreenCoordinates() {
        BoardScene scene = closedBoard(15, 8, 2, false);
        BoardCamera camera = new BoardCamera(scene, 920, 1100, 36, 43, 1);
        float[] point = project(camera, scene.x(8),
                BoardScene.layerY(2) + BoardScene.top(BoardScene.CLOSED), scene.z(8));
        MineCoord hit = camera.pick(scene, point[0], point[1]);
        assertNotNull(hit);
        assertEquals(2, hit.z);
        assertNull(camera.pick(scene, -1, point[1]));
        assertNull(camera.pick(scene, point[0], camera.height));
    }

    @Test
    public void nearestVisibleBlockWinsWhenAClosedNeighborCoversAnOpenedBlock() {
        byte[] cells = new byte[25];
        cells[4 * 5 + 2] = BoardScene.CLOSED;
        BoardScene scene = new BoardScene(5, 5, 2, 0, true, false, true, -1, -1, cells);
        BoardCamera camera = new BoardCamera(scene, 720, 1040, 0, 23, 2);
        float[] point = project(camera, scene.x(2), BoardScene.layerY(0) + .095f, scene.z(3) + .31f);
        MineCoord hit = camera.pick(scene, point[0], point[1]);
        assertNotNull(hit);
        assertEquals(2, hit.x);
        assertEquals(4, hit.y);
    }

    @Test
    public void overviewBuildsEightLayersAndFocusDropsEveryGuide() {
        BoardMesh mesh = new BoardMesh();
        mesh.update(closedBoard(15, 8, 4, false), 0);
        int active = mesh.blocks.count();
        assertTrue(active >= 15 * 15 * 30);
        assertEquals(7 * (24 + (14 + 14) * 2) + 8, mesh.ghost.count());
        mesh.update(closedBoard(15, 8, 4, true), 3);
        assertEquals(active, mesh.blocks.count());
        assertEquals(0, mesh.ghost.count());
    }

    @Test
    public void onlyUninterruptedTapsCanSelect() {
        BoardTouch touch = new BoardTouch(10);
        touch.down(50, 50);
        assertFalse(touch.drag(55, 52));
        assertTrue(touch.up(56, 51));

        touch.down(50, 50);
        assertTrue(touch.drag(77, 61));
        assertEquals(27, touch.dx, 0);
        assertFalse(touch.up(50, 50));

        touch.down(50, 50);
        touch.multiplePointers();
        assertFalse(touch.drag(95, 50));
        assertFalse(touch.up(50, 50));

        touch.down(50, 50);
        touch.cancel();
        assertFalse(touch.up(50, 50));
    }

    private static BoardScene closedBoard(int size, int layers, int active, boolean focused) {
        byte[] cells = new byte[size * size];
        Arrays.fill(cells, BoardScene.CLOSED);
        return new BoardScene(size, size, layers, active, focused, false, true, -1, -1, cells);
    }

    private static float[] project(BoardCamera camera, float x, float y, float z) {
        float[] m = camera.viewProjection;
        float w = m[3] * x + m[7] * y + m[11] * z + m[15];
        float sx = (m[0] * x + m[4] * y + m[8] * z + m[12]) / w;
        float sy = (m[1] * x + m[5] * y + m[9] * z + m[13]) / w;
        return new float[]{(sx + 1) * camera.width / 2, (1 - sy) * camera.height / 2};
    }
}
