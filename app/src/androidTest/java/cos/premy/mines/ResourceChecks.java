package cos.premy.mines;

import android.app.Activity;
import android.app.Instrumentation;
import android.content.Context;
import android.content.res.Configuration;
import android.os.Bundle;
import android.os.LocaleList;

import java.util.Locale;

/** Exercises localized resources on Android without modifying any device language settings. */
public final class ResourceChecks extends Instrumentation {
    @Override
    public void onCreate(Bundle arguments) {
        super.onCreate(arguments);
        start();
    }

    @Override
    public void onStart() {
        Bundle result = new Bundle();
        try {
            check("zh-CN,en-US", "三维扫雷", "设置");
            check("zh-Hant-TW,en-US", "三维扫雷", "设置");
            check("en-US,zh-CN", "Mines3D", "Settings");
            check("ja-JP,zh-TW", "Mines3D", "Settings");
            check("zh-HK,en-US", "三维扫雷", "设置");
            result.putString("stream", "\n5 injected system-language resource checks passed.\n");
            finish(Activity.RESULT_OK, result);
        } catch (RuntimeException | AssertionError failure) {
            result.putString("stream", "\nFAILED: " + failure + "\n");
            finish(Activity.RESULT_CANCELED, result);
        }
    }

    private void check(String tags, String name, String settings) {
        Configuration config = new Configuration();
        config.setLocales(LocaleList.forLanguageTags(tags));
        Context context = LocalizedActivity.withPrimaryLanguage(getTargetContext(), config);
        if (!name.equals(context.getString(R.string.app_name))
                || !settings.equals(context.getString(R.string.options))) {
            throw new AssertionError(tags + ": " + context.getString(R.string.app_name));
        }
        String stats = context.getString(R.string.game_ended_stats, 1, 2, 3, 4);
        if (!stats.contains("1") || !stats.contains("2") || !stats.contains("3") || !stats.contains("4")) {
            throw new AssertionError(tags + ": " + stats);
        }
        Locale primary = LocaleList.forLanguageTags(tags).get(0);
        if (("en".equals(primary.getLanguage()) || "zh".equals(primary.getLanguage()))
                && !name.equals(getTargetContext().createConfigurationContext(config)
                    .getString(R.string.app_name))) {
            throw new AssertionError("Host label fallback: " + tags);
        }
    }
}
