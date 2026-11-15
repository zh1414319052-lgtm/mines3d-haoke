package cos.premy.mines.generator;

import java.util.Random;

import cos.premy.mines.MyHappyException;
import cos.premy.mines.data.MinesContainer;

/**
 * Created by premy on 07.11.2017.
 */

public class RandomMinesGenerator implements MinesGenerator {
    @Override
    public void populateNewProblem(MinesContainer container, int level, int n, int m) {
        container.generate(new cos.premy.mines.data.MineCoord(m,n,level));
    }
}
